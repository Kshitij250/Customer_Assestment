"""
Inference module for the company risk-assessment ("Decision") page.

Loads the model bundle produced by train_decision_model.py and exposes
assess_risk(), which takes whatever the app already has -- the per-document
summary/full-analysis dicts from groq_client.py and the NSE quote dict from
nse_service.py -- pulls out the handful of numeric signals the model uses,
and returns a verdict + confidence + human-readable contributing factors.

See train_decision_model.py's module docstring for the honest limitation:
this model is trained on a synthetically-labeled dataset built from
financial-risk domain heuristics, not on real historical outcomes. Treat
its output as a structured, explainable starting point for a human
reviewer -- not a ground-truth prediction.
"""

import os
import re
import pickle
import numpy as np

_MODEL_PATH = os.path.join(os.path.dirname(__file__), "decision_model.pkl")
_bundle = None


def _load_bundle():
    global _bundle
    if _bundle is None:
        with open(_MODEL_PATH, "rb") as f:
            _bundle = pickle.load(f)
    return _bundle


def _parse_numeric(value):
    """Parses values like '₹ 1,234.5 Cr', '(45.2)', '11.5%', '—', None, 4.2
    into a plain float, or None if it can't be parsed / is a placeholder."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s or s in ("—", "-", "N/A", "NA", "null"):
        return None
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = re.sub(r"[₹%,]", "", s)
    s = re.sub(r"\b(Cr|Crore|Crores|Lakh|Lakhs)\b", "", s, flags=re.IGNORECASE).strip()
    match = re.search(r"-?\d+(\.\d+)?", s)
    if not match:
        return None
    num = float(match.group())
    return -num if negative and num > 0 else num


def _row_value(rows, particular_name, year=None):
    """Finds a row by particular name (case-insensitive substring match) in
    a key_financial_summary/key_ratios/operational_metrics list, and
    returns its value for `year` (or the first/most-recent year if not
    specified)."""
    if not rows:
        return None
    target = particular_name.lower()
    for row in rows:
        name = (row.get("particular") or "").lower()
        if target in name:
            values = row.get("values") or {}
            if not values:
                return None
            if year and year in values:
                return _parse_numeric(values[year])
            # fall back to the first value present (assumed most-recent,
            # per the extraction convention of listing years most-recent-first)
            for v in values.values():
                parsed = _parse_numeric(v)
                if parsed is not None:
                    return parsed
            return None
    return None


def _yoy_growth_from_rows(rows, particular_name):
    """Computes YoY % growth from a row's two most recent year columns,
    if both are present."""
    if not rows:
        return None
    target = particular_name.lower()
    for row in rows:
        name = (row.get("particular") or "").lower()
        if target in name:
            values = row.get("values") or {}
            parsed = [_parse_numeric(v) for v in values.values()]
            parsed = [p for p in parsed if p is not None]
            if len(parsed) >= 2 and parsed[1] not in (0, None):
                return ((parsed[0] - parsed[1]) / abs(parsed[1])) * 100
            return None
    return None


def _best_scope(full_analysis):
    """Prefers consolidated financials over standalone when both exist,
    since consolidated is the more complete picture of the group."""
    if not full_analysis:
        return None
    scope = full_analysis.get("financial_scope") or {}
    return scope.get("consolidated") or scope.get("standalone")


def extract_features(annual_summary=None, balance_summary=None,
                      annual_full=None, balance_full=None, nse=None):
    """Pulls the model's feature values from whatever data is available.
    Returns (features: dict[name -> float|None], sources: dict[name -> str])
    where `sources` records where each value came from (or 'missing'), so
    the UI/response can be transparent about what was actually extracted
    vs. defaulted."""
    features = {}
    sources = {}

    scope = _best_scope(annual_full) or _best_scope(balance_full)
    ratios = (scope or {}).get("key_ratios") or []
    fin_summary_rows = (scope or {}).get("key_financial_summary") or []

    def _set(name, value, source):
        features[name] = value
        sources[name] = source if value is not None else "missing"

    _set("current_ratio", _row_value(ratios, "current ratio"), "full_analysis.key_ratios")
    dte = _row_value(ratios, "debt : equity") or _row_value(ratios, "debt-equity")
    if dte is None and balance_summary:
        dte = _parse_numeric((balance_summary.get("financials", {}).get("debt_to_equity") or {}).get("value"))
        _set("debt_to_equity", dte, "summary.debt_to_equity")
    else:
        _set("debt_to_equity", dte, "full_analysis.key_ratios")

    _set("roe_pct", _row_value(ratios, "roe"), "full_analysis.key_ratios")

    ebitda_margin = _row_value(ratios, "ebitda margin")
    if ebitda_margin is None and annual_summary:
        ebitda_margin = _parse_numeric((annual_summary.get("financials", {}).get("operating_profit_margin_pct") or {}).get("value"))
        _set("ebitda_margin_pct", ebitda_margin, "summary.operating_profit_margin_pct")
    else:
        _set("ebitda_margin_pct", ebitda_margin, "full_analysis.key_ratios")

    pat_margin = _row_value(ratios, "pat margin")
    if pat_margin is None and annual_summary:
        pat_margin = _parse_numeric((annual_summary.get("financials", {}).get("net_profit_margin_pct") or {}).get("value"))
        _set("pat_margin_pct", pat_margin, "summary.net_profit_margin_pct")
    else:
        _set("pat_margin_pct", pat_margin, "full_analysis.key_ratios")

    _set("interest_coverage_ratio", _row_value(ratios, "interest coverage"), "full_analysis.key_ratios")

    rev_growth = _yoy_growth_from_rows(fin_summary_rows, "revenue from operations")
    if rev_growth is None and annual_summary:
        rev_growth = (annual_summary.get("financials", {}).get("total_revenue") or {}).get("yoy_pct")
        _set("revenue_yoy_growth_pct", rev_growth, "summary.total_revenue.yoy_pct")
    else:
        _set("revenue_yoy_growth_pct", rev_growth, "full_analysis.key_financial_summary")

    profit_growth = _yoy_growth_from_rows(fin_summary_rows, "pat")
    if profit_growth is None and annual_summary:
        profit_growth = (annual_summary.get("financials", {}).get("net_profit") or {}).get("yoy_pct")
        _set("profit_yoy_growth_pct", profit_growth, "summary.net_profit.yoy_pct")
    else:
        _set("profit_yoy_growth_pct", profit_growth, "full_analysis.key_financial_summary")

    pe = None
    pct_from_high = None
    market_cap = None
    if nse:
        pe = nse.get("pe_ratio")
        last_price = nse.get("last_price")
        week52_high = nse.get("week52_high")
        if isinstance(last_price, (int, float)) and isinstance(week52_high, (int, float)) and week52_high:
            pct_from_high = ((last_price - week52_high) / week52_high) * 100
        market_cap = nse.get("market_cap_cr")

    _set("pe_ratio", pe, "nse.pe_ratio")
    _set("pct_from_52w_high", pct_from_high, "nse (computed from last_price/week52_high)")
    _set("log_market_cap_cr", np.log1p(market_cap) if isinstance(market_cap, (int, float)) else None, "nse.market_cap_cr")

    return features, sources


_FEATURE_LABELS = {
    "current_ratio": "Current Ratio",
    "debt_to_equity": "Debt-to-Equity",
    "roe_pct": "Return on Equity (%)",
    "ebitda_margin_pct": "EBITDA Margin (%)",
    "pat_margin_pct": "PAT Margin (%)",
    "interest_coverage_ratio": "Interest Coverage Ratio",
    "revenue_yoy_growth_pct": "Revenue YoY Growth (%)",
    "profit_yoy_growth_pct": "Profit YoY Growth (%)",
    "pe_ratio": "P/E Ratio",
    "pct_from_52w_high": "% From 52-Week High",
    "log_market_cap_cr": "Market Cap (size factor)",
}


def assess_risk(annual_summary=None, balance_summary=None,
                 annual_full=None, balance_full=None, nse=None):
    bundle = _load_bundle()
    features, sources = extract_features(annual_summary, balance_summary, annual_full, balance_full, nse)

    n_missing = sum(1 for v in features.values() if v is None)
    n_total = len(bundle["features"])

    filled = []
    for name in bundle["features"]:
        val = features.get(name)
        filled.append(val if val is not None else bundle["defaults"][name])

    X = np.array(filled).reshape(1, -1)
    X_scaled = bundle["scaler"].transform(X)
    clf = bundle["classifier"]
    proba = clf.predict_proba(X_scaled)[0]
    classes = list(clf.classes_)
    pred_idx = int(np.argmax(proba))
    verdict = classes[pred_idx]
    confidence = float(proba[pred_idx])

    # Data-completeness discount: confidence is only meaningful if we
    # actually had real inputs, not defaults standing in for missing data.
    completeness = 1 - (n_missing / n_total)

    # Feature contributions for the predicted class (coef * scaled value),
    # restricted to features that were ACTUALLY extracted (not defaulted),
    # so the explanation only cites real evidence.
    contributions = []
    if hasattr(clf, "coef_"):
        class_row = clf.coef_[pred_idx] if clf.coef_.shape[0] > 1 else clf.coef_[0]
        for i, name in enumerate(bundle["features"]):
            if features.get(name) is None:
                continue
            contributions.append((name, class_row[i] * X_scaled[0][i]))
    contributions.sort(key=lambda x: abs(x[1]), reverse=True)

    top_factors = []
    for name, contrib in contributions[:4]:
        raw_val = features[name]
        if name == "log_market_cap_cr":
            display_val = f"₹{round(np.expm1(raw_val)):,} Cr"
        else:
            display_val = round(raw_val, 2)
        direction = "supports lower risk" if (contrib > 0) else "adds to risk"
        top_factors.append(f"{_FEATURE_LABELS[name]} = {display_val} ({direction})")

    return {
        "verdict": verdict,               # "Low" | "Medium" | "High"
        "confidence": round(confidence, 3),
        "probabilities": {c: round(float(p), 3) for c, p in zip(classes, proba)},
        "data_completeness": round(completeness, 2),
        "top_factors": top_factors,
        "feature_sources": sources,
        "note": (
            "This model is trained on a synthetically-labeled dataset built from "
            "standard financial-risk heuristics (not real historical outcomes). "
            "Treat it as an explainable starting point for review, not a "
            "guaranteed prediction."
        ),
    }
