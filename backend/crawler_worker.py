"""
crawler_worker.py — Standalone Playwright script.

This runs as a SEPARATE PROCESS (not inside FastAPI's event loop),
called via subprocess.run() from web_crawler.py.

Because it's a fresh Python process with no running event loop,
Playwright's sync API works perfectly — no Windows asyncio conflicts.

Usage (internal):
    python crawler_worker.py <url>

Output: JSON to stdout with structure:
    {"links": [{"text": "...", "href": "..."}, ...], "page_used": "..."}
    or on error:
    {"error": "..."}
"""

import json
import re
import sys
import time
from urllib.parse import urljoin, urlparse

ANNUAL_KW = [
    "annual report", "annual-report", "annual_report", "ar 20",
    "integrated report", "annual results", "annual accounts",
    "audited results", "q4 result", "full year",
]
BALANCE_KW = [
    "balance sheet", "balance-sheet", "balance_sheet",
    "financial statement", "standalone financial",
    "financial result", "quarterly result", "financials",
]
IR_NAV_KW = [
    "investor", "financials", "annual report", "reports",
    "financial result", "investor relation",
]
YEAR_RE = re.compile(r"20\d{2}")


def score(text, href, keywords):
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


def collect_links(page, base_url):
    anchors = page.eval_on_selector_all(
        "a",
        "els => els.map(e => ({text: (e.innerText||'').trim(), href: e.href||''}))"
    )
    links = []
    for a in anchors:
        href = a.get("href", "").strip()
        text = a.get("text", "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        blob = f"{text} {href}".lower()
        if href.lower().endswith(".pdf") or any(
            k in blob for k in ANNUAL_KW + BALANCE_KW
        ):
            links.append({"text": text, "href": href})
    return links


def find_ir_subpages(page, base_url, already_visited):
    anchors = page.eval_on_selector_all(
        "a",
        "els => els.map(e => ({text: (e.innerText||'').trim(), href: e.href||''}))"
    )
    domain = urlparse(base_url).netloc
    subpages = []
    seen = set(already_visited)
    for a in anchors:
        href = a.get("href", "").strip()
        text = a.get("text", "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#")):
            continue
        if urlparse(href).netloc != domain:
            continue
        blob = f"{text} {href}".lower()
        if any(k in blob for k in IR_NAV_KW) and href not in seen:
            seen.add(href)
            subpages.append(href)
        if len(subpages) >= 10:
            break
    return subpages


def run(start_url):
    from playwright.sync_api import sync_playwright

    parsed = urlparse(start_url)
    domain_root = f"{parsed.scheme}://{parsed.netloc}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        all_links = []
        page_used = start_url
        visited = set()

        def try_page(url):
            nonlocal all_links, page_used
            if url in visited:
                return False
            visited.add(url)
            try:
                page.goto(url, timeout=18000, wait_until="domcontentloaded")
                time.sleep(1.5)  # let JS settle
                links = collect_links(page, url)
                if links:
                    all_links = links
                    page_used = url
                    return True
            except Exception:
                pass
            return False

        # Step 1: try the given URL
        found = try_page(start_url)

        # Step 2: if no links, try common IR paths on the root domain
        if not found:
            common_paths = [
                "/investors", "/investor-relations", "/investor_relations",
                "/ir", "/annual-reports", "/financials",
                "/investors/financials", "/investors/annual-reports",
                "/investor/financials", "/investor/reports",
                "/corporate/investor-relations", "/about/investors",
                "/investor/financials/financial_result",
            ]
            for path in common_paths:
                if try_page(urljoin(domain_root, path)):
                    break

        # Step 3: if still no links, scan IR sub-pages found in the homepage nav
        if not all_links:
            try:
                page.goto(start_url, timeout=18000, wait_until="domcontentloaded")
                time.sleep(1.5)
                subpages = find_ir_subpages(page, start_url, visited)
                for sp in subpages:
                    if try_page(sp):
                        break
            except Exception:
                pass

        browser.close()
        return all_links, page_used


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No URL provided"}))
        sys.exit(1)

    url = sys.argv[1]
    try:
        links, page_used = run(url)
        print(json.dumps({"links": links, "page_used": page_used}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    main()