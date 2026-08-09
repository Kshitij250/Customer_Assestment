"""
web_crawler.py — Two-stage generic website crawler.

Stage 1 (fast): requests + BeautifulSoup — works for server-rendered pages.
Stage 2 (full): Playwright subprocess — for JS-heavy pages where stage 1
  finds nothing.

This approach means techno.co.in and similar sites work instantly via
requests, while JS-only sites get the real browser fallback.
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

ANNUAL_KW = [
    "annual report", "annual-report", "annual_report", "ar 20",
    "integrated report", "annual results", "annual accounts",
    "audited results", "q4 annual", "full year",
]
BALANCE_KW = [
    "balance sheet", "balance-sheet", "balance_sheet",
    "financial statement", "standalone financial",
    "financial result", "quarterly result",
]
IR_NAV_KW = [
    "investor", "financials", "annual report", "annual-report",
    "financial result", "investor relation", "reports",
]

COMMON_IR_PATHS = [
    "/investors", "/investor-relations", "/investor_relations",
    "/ir", "/annual-reports", "/financials",
    "/investors/financials", "/investors/annual-reports",
    "/investor/financials", "/investor/reports",
    "/investor/financials/financial_result",
    "/investor/generalInformation",
    "/corporate/investor-relations", "/about/investors",
]

YEAR_RE = re.compile(r"20\d{2}")


def _score(text: str, href: str, keywords: list) -> int:
    blob = f"{text} {href}".lower()
    s = sum(2 for k in keywords if k in blob)
    if not s:
        return 0
    m = YEAR_RE.search(blob)
    if m:
        y = int(m.group())
        if y >= 2023: s += 3
        elif y >= 2021: s += 1
    if href.lower().endswith(".pdf"):
        s += 2
    return s


def _fetch_html(url: str, timeout: int = 12) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None


def _extract_links(html: str, base_url: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        text = (tag.get_text() or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        full = urljoin(base_url, href)
        blob = f"{text} {href}".lower()
        if href.lower().endswith(".pdf") or any(
            k in blob for k in ANNUAL_KW + BALANCE_KW
        ):
            links.append({"text": text, "href": full})
    return links


def _ir_subpages(html: str, base_url: str) -> list:
    soup = BeautifulSoup(html, "lxml")
    domain = urlparse(base_url).netloc
    seen, result = set(), []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.startswith(("javascript:", "mailto:", "#")):
            continue
        full = urljoin(base_url, href)
        if urlparse(full).netloc != domain:
            continue
        blob = f"{tag.get_text() or ''} {href}".lower()
        if any(k in blob for k in IR_NAV_KW) and full not in seen:
            seen.add(full)
            result.append(full)
        if len(result) >= 10:
            break
    return result


def _stage1_requests(start_url: str):
    """Fast pass: requests + BeautifulSoup. Returns (links, page_used)."""
    parsed = urlparse(start_url)
    domain_root = f"{parsed.scheme}://{parsed.netloc}"

    candidates = [start_url]
    if parsed.path.rstrip("/") in ("", "/"):
        candidates += [urljoin(domain_root, p) for p in COMMON_IR_PATHS]

    visited = set()

    def try_url(url):
        if url in visited:
            return []
        visited.add(url)
        html = _fetch_html(url)
        return _extract_links(html, url) if html else [], html

    # Try direct candidates first
    for url in candidates:
        if url in visited:
            continue
        visited.add(url)
        html = _fetch_html(url)
        if not html:
            continue
        links = _extract_links(html, url)
        if links:
            return links, url
        # Also try IR sub-pages found on this page's nav
        for sub in _ir_subpages(html, url):
            if sub in visited:
                continue
            visited.add(sub)
            sub_html = _fetch_html(sub)
            if not sub_html:
                continue
            sub_links = _extract_links(sub_html, sub)
            if sub_links:
                return sub_links, sub

    return [], start_url


def _stage2_playwright(start_url: str):
    """Full browser pass via crawler_worker.py subprocess."""
    worker = Path(__file__).parent.parent / "crawler_worker.py"
    try:
        res = subprocess.run(
            [sys.executable, str(worker), start_url],
            capture_output=True, text=True, timeout=90,
        )
        data = json.loads(res.stdout.strip() or "{}")
        links = data.get("links", [])
        page_used = data.get("page_used", start_url)
        return links, page_used
    except Exception as e:
        return [], start_url


def find_report_links(start_url: str) -> dict:
    # Stage 1: fast requests-based crawl
    links, page_used = _stage1_requests(start_url)

    # Stage 2: if nothing found, launch real browser
    if not links:
        links, page_used = _stage2_playwright(start_url)

    if not links:
        return {
            "annual_report": None, "balance_sheet": None,
            "page_used": page_used,
            "error": (
                "No financial document links found on the site after trying "
                "both fast and browser-based crawl. Use manual upload instead."
            ),
        }

    ar = [l for l in links if _score(l["text"], l["href"], ANNUAL_KW) > 0]
    bs = [l for l in links if _score(l["text"], l["href"], BALANCE_KW) > 0]

    annual  = max(ar, key=lambda l: _score(l["text"], l["href"], ANNUAL_KW),  default=None)
    balance = max(bs, key=lambda l: _score(l["text"], l["href"], BALANCE_KW), default=None)

    return {"annual_report": annual, "balance_sheet": balance, "page_used": page_used}


def download_pdf(url: str, dest_path: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
    r.raise_for_status()
    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    return dest_path