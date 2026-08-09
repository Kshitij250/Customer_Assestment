import os
import asyncio
import uuid
import glob
from pathlib import Path

from dotenv import load_dotenv

# Load .env BEFORE importing services — some services (e.g. legal_service)
# read env vars at import time via os.getenv(), so load_dotenv() must run
# first or they'll silently lock in empty values.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from services.pdf_extractor import extract_pdf_text, save_upload
from services.groq_client import extract_financial_summary, extract_full_analysis
from services.web_crawler import find_report_links, download_pdf
from services.nse_service import _run_nse_quote, _run_nse_search, parse_quote_summary
from services import legal_service
from services import decision_model
from services import screener_service

app = FastAPI(title="Customer Assessment AI - Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"


# In-memory store of last extracted text per document id, so the
# "Full Analysis" button can re-use the already-extracted text without
# re-uploading. Fine for a single-user dev setup; swap for Redis/DB later.
_DOCUMENT_TEXT_CACHE: dict[str, str] = {}


# ---------- Schemas ----------

class CrawlRequest(BaseModel):
    company_website: str  # e.g. "https://www.larsentoubro.com"


class AnalyzeRequest(BaseModel):
    document_id: str


class LegalSearchRequest(BaseModel):
    company_name: str
    days_back: int = 365
    max_court_pages: int = 2


class ScreenerRequest(BaseModel):
    company_name: str


class DecisionRequest(BaseModel):
    """
    The frontend already holds the summary/full-analysis results for each
    uploaded document (from /api/analyze/summary and /api/analyze/full) and
    the last-fetched NSE quote in its own session state -- rather than
    re-deriving/re-caching that server-side, it just forwards whatever it
    already has, and this endpoint runs the risk model over it.
    """
    annual_summary: Optional[dict] = None
    balance_summary: Optional[dict] = None
    annual_full: Optional[dict] = None
    balance_full: Optional[dict] = None
    nse: Optional[dict] = None


# ---------- Upload + manual analysis ----------

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), doc_type: str = "annual_report"):
    """Manual upload path. doc_type: 'annual_report' | 'balance_sheet'."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported")

    document_id = str(uuid.uuid4())
    contents = await file.read()
    saved_path = save_upload(contents, f"{document_id}_{file.filename}", UPLOAD_DIR)

    text = extract_pdf_text(saved_path)
    if not text.strip():
        raise HTTPException(422, "Could not extract any text from this PDF (it may be scanned/image-only).")

    _DOCUMENT_TEXT_CACHE[document_id] = text

    return {
        "document_id": document_id,
        "filename": file.filename,
        "doc_type": doc_type,
        "pages_extracted": text.count("[Page"),
    }


@app.get("/api/document/{document_id}/file")
def get_document_file(document_id: str):
    """
    Serves the raw stored PDF for a given document_id, so the frontend can
    render an inline preview. Works for both manually uploaded files
    (saved as '{document_id}_{filename}.pdf') and auto-crawled ones
    (saved as '{document_id}.pdf').
    """
    matches = glob.glob(os.path.join(UPLOAD_DIR, f"{document_id}*"))
    if not matches:
        raise HTTPException(404, "Document file not found on disk")
    return FileResponse(matches[0], media_type="application/pdf")


# ---------- Auto-fetch from company website ----------

@app.post("/api/crawl-website")
def crawl_website(req: CrawlRequest):
    """
    Attempts to locate Annual Report / Balance Sheet PDFs on the company's
    website and download them. Returns what was found; frontend falls back
    to manual upload if both come back null.
    """
    try:
        found = find_report_links(req.company_website)
    except Exception as e:
        raise HTTPException(502, f"Crawl failed: {e}")

    # If the crawler itself flagged an error (e.g. JS-only page), surface it
    if "error" in found and not found.get("annual_report") and not found.get("balance_sheet"):
        raise HTTPException(422, found["error"])

    results = {}
    for key in ("annual_report", "balance_sheet"):
        link = found.get(key)
        if not link:
            results[key] = None
            continue
        document_id = str(uuid.uuid4())
        dest = f"{UPLOAD_DIR}/{document_id}.pdf"
        try:
            download_pdf(link["href"], dest)
            text = extract_pdf_text(dest)
            if not text.strip():
                results[key] = {"error": "Downloaded PDF has no extractable text (may be scanned).",
                                "source_url": link["href"]}
                continue
            _DOCUMENT_TEXT_CACHE[document_id] = text
            results[key] = {
                "document_id": document_id,
                "source_url": link["href"],
                "label": link["text"] or key,
            }
        except Exception as e:
            results[key] = {"error": str(e), "source_url": link["href"]}

    return {"page_used": found.get("page_used"), "results": results}


# ---------- Analysis ----------

@app.post("/api/analyze/summary")
def analyze_summary(req: AnalyzeRequest):
    text = _DOCUMENT_TEXT_CACHE.get(req.document_id)
    if not text:
        raise HTTPException(404, "Document not found. Upload or crawl first.")
    try:
        return extract_financial_summary(text)
    except Exception as e:
        raise HTTPException(502, f"Groq analysis failed: {e}")


@app.post("/api/analyze/full")
def analyze_full(req: AnalyzeRequest):
    text = _DOCUMENT_TEXT_CACHE.get(req.document_id)
    if not text:
        raise HTTPException(404, "Document not found. Upload or crawl first.")
    try:
        return extract_full_analysis(text)
    except Exception as e:
        raise HTTPException(502, f"Groq analysis failed: {e}")


# ---------- Decision / risk assessment ----------

@app.post("/api/decision/assess")
def decision_assess(req: DecisionRequest):
    """
    Runs the trained risk-assessment model (see services/decision_model.py)
    over whatever financials/NSE data the frontend already has in session
    state. Returns a Low/Medium/High verdict, confidence, per-class
    probabilities, and the top contributing factors actually extracted
    from the data (as opposed to defaulted).
    """
    try:
        return decision_model.assess_risk(
            annual_summary=req.annual_summary,
            balance_summary=req.balance_summary,
            annual_full=req.annual_full,
            balance_full=req.balance_full,
            nse=req.nse,
        )
    except Exception as e:
        raise HTTPException(502, f"Decision model failed: {e}")


# ---------- Screener.in (public balance sheet / P&L / ratios data) ----------

@app.post("/api/screener/fetch")
def screener_fetch(req: ScreenerRequest):
    """
    Fetches Standalone/Consolidated Profit & Loss, Balance Sheet, Cash Flow,
    and Ratios tables from Screener.in's public pages for a company name.
    No login/credentials involved -- this data is publicly accessible.
    """
    try:
        return screener_service.get_company_financials(req.company_name)
    except screener_service.ScreenerError as e:
        raise HTTPException(502, str(e))


# ---------- NSE stock data ----------

@app.get("/api/nse/search")
def nse_search(q: str = Query(..., min_length=1)):
    try:
        return _run_nse_search(q)
    except Exception as e:
        raise HTTPException(502, f"NSE search failed: {e}")


@app.get("/api/nse/quote")
def nse_quote(symbol: str):
    try:
        info = _run_nse_quote(symbol)
        return parse_quote_summary(info)
    except Exception as e:
        raise HTTPException(502, f"NSE quote failed: {e}")


# ---------- Legal due diligence ----------

@app.post("/api/legal/news")
def legal_news(req: LegalSearchRequest):
    try:
        return legal_service.get_legal_news(req.company_name, req.days_back)
    except legal_service.LegalServiceError as e:
        raise HTTPException(502, f"Legal news search failed: {e}")


@app.post("/api/legal/court-cases")
def legal_court_cases(req: LegalSearchRequest):
    try:
        return legal_service.get_court_cases(req.company_name, req.max_court_pages)
    except legal_service.LegalServiceError as e:
        raise HTTPException(502, f"Legal court-case search failed: {e}")


@app.post("/api/legal/summary")
def legal_summary(req: LegalSearchRequest):
    try:
        return legal_service.get_legal_summary(req.company_name, req.days_back, req.max_court_pages)
    except legal_service.LegalServiceError as e:
        raise HTTPException(502, f"Legal summary failed: {e}")


@app.get("/api/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)