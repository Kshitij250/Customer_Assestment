"""
Multi-provider financial document analyzer (Groq primary, Gemini fallback).

Kept as `groq_client.py` (not renamed) so main.py's existing import
(`from services.groq_client import extract_financial_summary, extract_full_analysis`)
doesn't need to change -- only the internals moved from the raw Groq SDK to
LiteLLM, which gives one interface across providers.

Two-stage design (matches the UI: quick summary first, "Full Analysis" button
reveals the rest):
  1. extract_financial_summary() - fast, cheap, structured JSON for the
     dashboard cards (Total Revenue, Net Profit, EBITDA, margins, EPS,
     Total Assets/Liabilities, Net Worth, Current Assets/Liabilities,
     Debt-to-Equity) + 4-6 key insights.
  2. extract_full_analysis() - deeper pass: multi-year Standalone /
     Consolidated tables (Key Financial Summary, Key Ratios, Operational
     Metrics), strengths, red flags, growth outlook, auditor remarks.
     The schema here is intentionally shaped to match exactly what the
     Streamlit frontend renders (`financial_scope.standalone/consolidated`
     with `years` + row lists) -- earlier versions of this prompt asked for
     a different shape (`ratios`/`trend_analysis`/`liabilities_breakdown`)
     that the frontend never read, so the Full Analysis tables always
     rendered empty even when the model responded successfully.

Both prompts force strict JSON output and forbid the model from inventing
numbers it didn't see in the source text -- this is the single biggest
failure mode with financial-doc LLM extraction (hallucinated figures that
*look* plausible). The prompt explicitly tells the model to use null for
anything not found, rather than estimate.

PROVIDER STRATEGY
------------------
1. Try Groq first (openai/gpt-oss-120b by default -- fast, cheap, 131k-token
   context). Good for the large majority of annual reports / balance sheets.
2. If Groq raises ANY exception -- rate limit, a deprecated/retired model,
   a transient outage, a context-length error, whatever -- fall back to
   Gemini (1M-token context), which also happens to comfortably swallow
   documents too large for Groq's budget without any manual chunking.
3. Each provider gets a couple of quick retries first (short backoff) before
   we give up on it and move to the next -- a single transient 503/rate
   limit shouldn't immediately sacrifice the whole request.

Requires: pip install litellm
Env vars: GROQ_API_KEY, GEMINI_API_KEY (get one free at
          https://aistudio.google.com/apikey), optionally GROQ_MODEL /
          GEMINI_MODEL to override the defaults below.
"""

import os
import json
import time
import logging

from litellm import completion

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────
#  PROVIDER CONFIG
# ──────────────────────────────────────────────────────────────────────────
# Groq: primary. NOTE -- llama-3.3-70b-versatile was deprecated by Groq on
# 2026-06-17; openai/gpt-oss-120b is Groq's own recommended replacement
# (same 131k context, ~1/4 the price).
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MODEL_ID = f"groq/{GROQ_MODEL}"
GROQ_CHAR_LIMIT = 90_000  # ~22-25k tokens: safe margin under Groq's context + per-minute token budget

# Gemini: fallback. 1M-token context comfortably fits a full annual report
# without chunking. Model naming under Gemini 3 shifts fairly often --
# check https://ai.google.dev/gemini-api/docs/models if this 404s later.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
GEMINI_MODEL_ID = f"gemini/{GEMINI_MODEL}"
GEMINI_CHAR_LIMIT = 3_500_000  # generous cap, comfortably under the 1M-token window

# Full analysis (multi-year, multi-scope tables + narrative fields) needs a
# much larger output budget than the quick summary -- 2000 tokens was
# nowhere near enough and caused the JSON to get cut off mid-object.
SUMMARY_MAX_TOKENS = int(os.getenv("SUMMARY_MAX_TOKENS", "3000"))
FULL_ANALYSIS_MAX_TOKENS = int(os.getenv("FULL_ANALYSIS_MAX_TOKENS", "8000"))

# Quick retries per-provider before moving to the next one in the chain --
# a single transient 503/rate-limit shouldn't sacrifice the whole request.
RETRIES_PER_PROVIDER = 2
RETRY_BACKOFF_SECONDS = 3


SUMMARY_SYSTEM_PROMPT = """You are a financial analyst extracting structured data from Indian company annual reports and balance sheets.

STRICT RULES:
1. Only report figures that are explicitly present in the provided text. NEVER estimate, infer, or hallucinate a number.
2. If a figure is not found in the text, set its value to null. Do not guess.
3. All monetary figures (total_revenue, net_profit, ebitda, total_assets, total_liabilities, net_worth, current_assets, current_liabilities) must be normalized to "₹ X Cr" or "₹ X Lakh Cr" exactly as stated in the source (preserve the unit used in the document; do not silently convert units).
4. "eps" is a PER-SHARE figure, not a Cr figure -- format it as "₹ X" (e.g. "₹ 126.95"), never with "Cr".
5. "operating_profit_margin_pct" and "net_profit_margin_pct" are plain numbers as strings with NO "%" sign (e.g. "11.5", not "11.5%") -- the UI adds the "%" itself.
6. "debt_to_equity" is a plain ratio number as a string with no unit (e.g. "0.41").
7. YoY % changes must only be included if the prior-year comparative figure is explicitly present in the text. Otherwise set yoy_pct to null.
8. This document may be an Annual Report (revenue/profit-focused) OR a Balance Sheet (assets/liabilities-focused) -- only some of the fields below will typically be found in any single document. That is expected: set the rest to null rather than guessing.
9. Output ONLY valid JSON matching the schema below. No markdown, no commentary, no preamble, no trailing text.
10. Key insights must be specific and numeric where possible (cite the actual figures), not generic statements like "the company performed well."
11. If the text appears to be missing financial statements entirely (e.g. only contains a cover page or directors' message), set all numeric fields to null and add an insight noting the limitation.

JSON schema:
{
  "company_name": string | null,
  "report_period": string | null,
  "financials": {
    "total_revenue": {"value": string | null, "yoy_pct": number | null},
    "net_profit": {"value": string | null, "yoy_pct": number | null},
    "ebitda": {"value": string | null, "yoy_pct": number | null},
    "operating_profit_margin_pct": {"value": string | null, "yoy_pct": number | null},
    "net_profit_margin_pct": {"value": string | null, "yoy_pct": number | null},
    "eps": {"value": string | null, "yoy_pct": number | null},
    "total_assets": {"value": string | null, "yoy_pct": number | null},
    "total_liabilities": {"value": string | null, "yoy_pct": number | null},
    "net_worth": {"value": string | null, "yoy_pct": number | null},
    "current_assets": {"value": string | null, "yoy_pct": number | null},
    "current_liabilities": {"value": string | null, "yoy_pct": number | null},
    "debt_to_equity": {"value": string | null, "yoy_pct": number | null}
  },
  "key_insights": [string, ...]   // 4 to 6 specific, evidence-based bullet points
}"""

FULL_ANALYSIS_SYSTEM_PROMPT = """You are a senior credit/equity research analyst producing a detailed, multi-year financial due-diligence breakdown of an Indian company from its annual report / balance sheet text.

STRICT RULES:
1. Use ONLY figures explicitly present in the supplied text. Never fabricate, estimate, or infer a number.
2. Preserve the original currency unit as stated (Cr / Lakh Cr) -- do not convert.
3. Extract MULTI-YEAR tables exactly as they appear in the source (e.g. FY24/FY23/FY22 columns). The "years" list must use the EXACT column labels from the source table (e.g. "FY 24 (A)", "FY23", "2023-24"), left-to-right in the same order as the source.
4. If the document reports BOTH Standalone and Consolidated financials, populate both `standalone` and `consolidated` with their own tables. If only one scope is present in the source, set the other to null -- never duplicate one scope's numbers into the other.
5. For each row, "values" is an object keyed by the exact year label, e.g. {"FY 24 (A)": "57,434", "FY 23 (A)": "53,399"}. Omit a row entirely if that line item isn't present in the source for this scope -- do not invent a row full of nulls.
6. Keep every free-text field CONCISE -- one short sentence per item. Do not write long paragraphs; this output must stay compact so it doesn't get cut off.
7. "red_flags" must only include items with explicit textual evidence (auditor qualification, contingent liability disclosure, a disclosed declining trend, etc.) -- not speculation. "strengths" must be similarly evidence-backed. Both may be an empty list if nothing qualifies -- do not pad with generic filler.
8. Output ONLY valid JSON per the schema below. No prose outside the JSON, no markdown fences, no commentary.

JSON schema:
{
  "financial_scope": {
    "standalone": {
      "years": [string, ...],
      "key_financial_summary": [
        {"particular": string, "values": {<year label>: string, ...}}
      ],
      "key_ratios": [
        {"particular": string, "values": {<year label>: string, ...}}
      ],
      "operational_metrics": [
        {"particular": string, "values": {<year label>: string, ...}}
      ]
    },
    "consolidated": { /* same shape as standalone */ } | null
  },
  "strengths": [string, ...],
  "red_flags": [string, ...],
  "growth_outlook": string | null,
  "auditor_remarks": string | null
}

Typical row names to look for (include only the ones actually present in the source, do not invent the rest):
- key_financial_summary: "Revenue from operations", "EBITDA", "Other Income", "Depreciation", "Finance Costs", "PBT", "PAT", "Share Capital", "Reserves & Surplus", "Net Worth"
- key_ratios: "EBITDA Margin (%)", "PAT Margin (%)", "Interest Coverage Ratio", "Debt : Equity Ratio", "Current Ratio", "Debt : EBITDA", "ROE (%)", "ROA (%)"
- operational_metrics: "Inventory / Sales (Days)", "Debtors / Sales (Days)", "Payables / Sales (Days)", "Cash as % of long-term debt", "Debt-Total Asset Ratio", "Total Outside liabilities / Total Net worth"

If NEITHER standalone nor consolidated multi-year tables can be found anywhere in the source text, set both to null -- do not fabricate placeholder tables."""


def _call_model(model_id: str, system_prompt: str, document_text: str, char_limit: int,
                 temperature: float, max_tokens: int) -> str:
    if model_id.startswith("groq/") and not os.getenv("GROQ_API_KEY"):
        raise RuntimeError("GROQ_API_KEY is not set in environment/.env")
    if model_id.startswith("gemini/") and not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is not set in environment/.env")

    last_error = None
    for attempt in range(1, RETRIES_PER_PROVIDER + 1):
        try:
            resp = completion(
                model=model_id,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            "Extracted text from the financial document follows. "
                            "Page markers like [Page N] indicate source location. "
                            "Tables that could be detected have already been reformatted "
                            "as clean Markdown tables for you.\n\n"
                            f"{document_text[:char_limit]}"
                        ),
                    },
                ],
            )
            return resp.choices[0].message.content
        except Exception as e:
            last_error = e
            if attempt < RETRIES_PER_PROVIDER:
                logger.warning("Model %s attempt %d/%d failed, retrying in %ds: %s",
                                model_id, attempt, RETRIES_PER_PROVIDER, RETRY_BACKOFF_SECONDS, e)
                time.sleep(RETRY_BACKOFF_SECONDS)
            else:
                raise last_error


def _chat_json(system_prompt: str, document_text: str, max_tokens: int, temperature: float = 0.1) -> dict:
    """
    Tries Groq first (fast, cheap). Falls back to Gemini (1M-token context)
    if Groq raises for any reason -- rate limit, a retired model, a
    transient outage, etc. Gemini's huge context also means genuinely large
    documents succeed here even if they'd have been too big for Groq's
    budget, with no manual chunking needed.
    """
    raw = None
    used_model = None
    last_error = None

    for model_id, char_limit in [(GROQ_MODEL_ID, GROQ_CHAR_LIMIT), (GEMINI_MODEL_ID, GEMINI_CHAR_LIMIT)]:
        try:
            raw = _call_model(model_id, system_prompt, document_text, char_limit, temperature, max_tokens)
            used_model = model_id
            break
        except Exception as e:
            logger.warning("Provider %s failed after retries, trying next: %s", model_id, e)
            last_error = e
            continue

    if raw is None:
        return {"error": "all_providers_failed", "detail": str(last_error)}

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "model_returned_invalid_json", "raw": raw, "model_used": used_model}

    if isinstance(result, dict):
        result["_model_used"] = used_model  # informational only; harmless extra key for debugging
    return result


def extract_financial_summary(document_text: str) -> dict:
    return _chat_json(SUMMARY_SYSTEM_PROMPT, document_text, max_tokens=SUMMARY_MAX_TOKENS)


def extract_full_analysis(document_text: str) -> dict:
    return _chat_json(FULL_ANALYSIS_SYSTEM_PROMPT, document_text, max_tokens=FULL_ANALYSIS_MAX_TOKENS, temperature=0.15)