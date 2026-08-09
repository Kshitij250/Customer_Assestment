"""
screener_service.py — Fixed
-----------------------------
Screener.in changed their search API endpoint.
Old (broken): GET /api/company/search/?q=...   → 404
New (working): GET /api/company/search/?q=...&v=3  with correct headers
               OR fallback: scrape the search results page directly.

Verified working approach:
- Primary:  POST https://www.screener.in/api/company/search/?q={query}&v=3
- Fallback: scrape https://www.screener.in/search/?q={query}
"""

import re
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.screener.in"

# Screener requires a session cookie (csrftoken) even for public pages.
# We get it by hitting the homepage first, exactly like a browser would.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}
TIMEOUT = 20

# ── Single shared session (warm once, reuse) ──────────────────────────────────
_session: requests.Session | None = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update(HEADERS)
        # Warm the session — gets csrftoken cookie
        try:
            s.get(f"{BASE_URL}/", timeout=15)
            time.sleep(0.3)
        except Exception:
            pass
        _session = s
    return _session


class ScreenerError(Exception):
    pass


# ── Search ────────────────────────────────────────────────────────────────────

def search_company(query: str) -> list:
    """
    Search Screener.in for a company name.
    Tries the JSON API first; falls back to scraping search results page.
    Returns list of: {'id', 'name', 'url'}
    """
    s = _get_session()

    # ── Attempt 1: JSON API (v=3 param is required now) ──────────────────────
    try:
        r = s.get(
            f"{BASE_URL}/api/company/search/",
            params={"q": query, "v": "3"},
            headers={**HEADERS, "Accept": "application/json",
                     "X-Requested-With": "XMLHttpRequest",
                     "Referer": f"{BASE_URL}/"},
            timeout=TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                return data
            # Sometimes returns {"results": [...]}
            if isinstance(data, dict) and data.get("results"):
                return data["results"]
    except Exception:
        pass

    # ── Attempt 2: Scrape the search results page ─────────────────────────────
    try:
        r = s.get(
            f"{BASE_URL}/search/",
            params={"q": query},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        results = []
        # Screener search page has a list of anchors like:
        # <a href="/company/TCS/consolidated/">Tata Consultancy Services</a>
        for a in soup.select("ul.results a, .search-result a, ul li a"):
            href = a.get("href", "")
            if "/company/" not in href:
                continue
            name = a.get_text(strip=True)
            if not name:
                continue
            # Extract company ID/slug from URL
            results.append({
                "id": href.split("/company/")[-1].split("/")[0],
                "name": name,
                "url": href if href.startswith("/") else f"/{href}",
            })

        if results:
            return results

    except Exception as e:
        raise ScreenerError(f"Screener search failed: {e}")

    raise ScreenerError(f"No results found for '{query}' on Screener.in")


def _best_match(query: str, results: list) -> dict | None:
    """Pick closest name match — avoids getting subsidiaries/ETFs first."""
    if not results:
        return None
    q = query.strip().lower()
    for r in results:
        if (r.get("name") or "").strip().lower() == q:
            return r
    for r in results:
        if q in (r.get("name") or "").strip().lower():
            return r
    return results[0]


# ── Page fetch ────────────────────────────────────────────────────────────────

def _fetch_html(url_path: str) -> str:
    s = _get_session()
    full_url = f"{BASE_URL}{url_path}" if url_path.startswith("/") else url_path
    try:
        r = s.get(full_url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except requests.HTTPError as e:
        raise ScreenerError(f"HTTP {e.response.status_code} fetching {url_path}")
    except Exception as e:
        raise ScreenerError(f"Could not fetch {url_path}: {e}")


# ── Table parsing ─────────────────────────────────────────────────────────────

def _clean_label(cell) -> str:
    text = cell.get_text(" ", strip=True)
    text = re.sub(r"\s*\+\s*$", "", text)
    return text.strip()


def _parse_section_table(soup: BeautifulSoup, section_id: str) -> dict:
    """
    Parses one <section id="..."> financial table.
    Returns {'years': [...], 'rows': [{'particular': str, 'values': {year: val}}]}
    Returns empty structure (not exception) if section not found.
    """
    section = soup.find(id=section_id)
    if not section:
        return {"years": [], "rows": []}

    table = section.find("table")
    if not table:
        return {"years": [], "rows": []}

    # ── Header row → year labels ──────────────────────────────────────────────
    years = []
    thead = table.find("thead")
    if thead:
        header_cells = thead.find_all("th")
        years = [_clean_label(th) for th in header_cells[1:]]

    # ── Body rows ─────────────────────────────────────────────────────────────
    rows = []
    tbody = table.find("tbody") or table
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if not cells:
            continue
        particular = _clean_label(cells[0])
        if not particular:
            continue
        values = {}
        for i, year in enumerate(years):
            if i + 1 < len(cells):
                values[year] = cells[i + 1].get_text(" ", strip=True)
        rows.append({"particular": particular, "values": values})

    return {"years": years, "rows": rows}


def _parse_company_page(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    return {
        "profit_loss":    _parse_section_table(soup, "profit-loss"),
        "balance_sheet":  _parse_section_table(soup, "balance-sheet"),
        "cash_flow":      _parse_section_table(soup, "cash-flow"),
        "ratios":         _parse_section_table(soup, "ratios"),
        "quarterly":      _parse_section_table(soup, "quarters"),
    }


# ── Main entry point ──────────────────────────────────────────────────────────

def get_company_financials(company_name: str) -> dict:
    """
    Given a free-text company name, finds the best Screener.in match
    and returns consolidated + standalone financials.

    Returns:
    {
      "matched_name": str,
      "screener_id": str|int,
      "screener_url": str,
      "consolidated": {profit_loss, balance_sheet, cash_flow, ratios, quarterly} | None,
      "standalone":   {same} | None,
    }
    """
    results = search_company(company_name)
    match = _best_match(company_name, results)
    if not match:
        raise ScreenerError(f"No Screener.in match found for '{company_name}'")

    # Build URLs
    raw_url = match.get("url") or ""
    if not raw_url:
        slug = match.get("id", "")
        raw_url = f"/company/{slug}/consolidated/"

    # Ensure consolidated URL has the right suffix
    if not raw_url.rstrip("/").endswith("consolidated"):
        consolidated_url = raw_url.rstrip("/") + "/consolidated/"
    else:
        consolidated_url = raw_url

    standalone_url = consolidated_url.replace("/consolidated/", "/")

    out = {
        "matched_name": match.get("name"),
        "screener_id":  match.get("id"),
        "screener_url": f"{BASE_URL}{consolidated_url}",
        "consolidated": None,
        "standalone":   None,
    }

    # ── Fetch consolidated ────────────────────────────────────────────────────
    try:
        html = _fetch_html(consolidated_url)
        data = _parse_company_page(html)
        if any(data[k]["rows"] for k in data):
            out["consolidated"] = data
    except ScreenerError:
        pass

    # ── Fetch standalone ──────────────────────────────────────────────────────
    try:
        html = _fetch_html(standalone_url)
        data = _parse_company_page(html)
        if any(data[k]["rows"] for k in data):
            out["standalone"] = data
    except ScreenerError:
        pass

    if not out["consolidated"] and not out["standalone"]:
        raise ScreenerError(
            f"Found '{match.get('name')}' on Screener.in but could not parse "
            f"any financial tables. The page layout may have changed."
        )

    return out