import os
import re
import base64
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="Customer Assessment AI", layout="wide",
                    page_icon="🛡️", initial_sidebar_state="collapsed")

# ══════════════════════════════════════════════════════════════════════════
#  GLOBAL CSS — this is the mockup's stylesheet, verbatim, plus a small
#  "Streamlit adaptation" section at the end that maps Streamlit's own
#  generated widgets (text inputs, buttons, tabs, file uploader, selects)
#  onto the same classes/visual language so the two systems don't clash.
# ══════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=IBM+Plex+Mono:wght@500;600;700&display=swap');

:root{
  --indigo:#4f39f6;
  --indigo-dark:#3b2ad1;
  --indigo-light:#eeecfe;
  --green:#16a34a;
  --green-bg:#e8f9ee;
  --green-border:#bdecd0;
  --red:#dc2626;
  --red-bg:#fdeaea;
  --orange:#d97706;
  --orange-bg:#fef3e2;
  --text-dark:#1a1d2b;
  --text-mid:#565b70;
  --text-light:#8b8fa3;
  --border:#e7e8ee;
  --bg:#f4f5f9;
  --card-bg:#ffffff;
  --shadow: 0 1px 2px rgba(16,24,40,0.04), 0 1px 3px rgba(16,24,40,0.03);
  --radius:14px;
  --mono: 'IBM Plex Mono', ui-monospace, monospace;
}
*{box-sizing:border-box;}
html, body, [class*="st-"], [class*="css"]{
  font-family:'Inter',-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif !important;
}
body{ background:var(--bg); color:var(--text-dark); -webkit-font-smoothing:antialiased; }

/* Financial digits get tabular-nums so columns line up like a terminal */
table td, .kpi-value, .nse-item .val, .legal-kpi-value{
  font-variant-numeric: tabular-nums;
}

/* TOP BAR */
.topbar{
  display:flex;align-items:center;justify-content:space-between;
  background:linear-gradient(90deg,#161b4d,#2c1f8f);
  padding:14px 28px;
}
.topbar-left{display:flex;align-items:center;gap:12px;}
.logo{
  width:40px;height:40px;border-radius:11px;
  background:linear-gradient(135deg,#7b6cf6,#5b3df0);
  display:flex;align-items:center;justify-content:center;
  color:#fff;font-size:18px;font-weight:700;
  box-shadow:0 2px 6px rgba(0,0,0,0.25);
}
.brand{font-size:19px;font-weight:700;color:#fff;letter-spacing:-0.2px;}
.topbar-right{display:flex;align-items:center;gap:12px;}
.date-pill{
  display:flex;align-items:center;gap:8px;border:1px solid rgba(255,255,255,0.18);
  border-radius:8px;padding:9px 14px;font-size:13px;color:#dfe1f5;font-weight:600;
  background:rgba(255,255,255,0.06);
}

/* NAV ROW — a Streamlit column row sitting directly under .topbar, same
   navy gradient with no seam, so it reads as one continuous header. */
.navrow{background:linear-gradient(90deg,#161b4d,#2c1f8f);padding:0 22px 14px;}
.navrow div[data-testid="column"]{width:auto !important;flex:0 0 auto !important;}
.navrow div[data-testid="stHorizontalBlock"]{gap:8px;}
.navrow div[data-testid="column"] .stButton > button{
  border-radius:9px !important;font-weight:600 !important;font-size:14px !important;
  border:none !important;background:rgba(255,255,255,0.05) !important;color:#c7cae8 !important;
  padding:10px 18px !important;transition:background .15s,color .15s !important;
  white-space:nowrap !important;
}
.navrow div[data-testid="column"] .stButton > button:hover{
  background:rgba(255,255,255,0.09) !important;color:#fff !important;
}
.navrow div[data-testid="column"] .stButton > button[kind="primary"]{
  background:var(--indigo) !important;color:#fff !important;
  box-shadow:0 2px 8px rgba(79,57,246,0.5) !important;
}

.container{padding:22px 28px 44px;max-width:1600px;margin:0 auto;}

/* INPUT FORM (shared) */
.input-card{
  background:var(--card-bg);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:18px 22px 6px;margin-bottom:20px;
}
.field label{display:block;font-size:13px;font-weight:700;color:var(--text-dark);margin-bottom:7px;}

/* ============ FINANCIALS PAGE ============ */
.kpi-row{margin-bottom:6px;}
.kpi-card{
  background:var(--card-bg);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:17px;display:flex;gap:13px;align-items:flex-start;
  transition:box-shadow .15s, transform .15s;height:100%;
}
.kpi-card:hover{box-shadow:0 4px 14px rgba(16,24,40,0.08);transform:translateY(-1px);}
.kpi-icon{
  width:44px;height:44px;border-radius:11px;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:19px;
}
.kpi-icon.blue{background:#eef2ff;}
.kpi-icon.green{background:#eafaf0;}
.kpi-icon.orange{background:#fef3e2;}
.kpi-icon.lightblue{background:#e8f3fb;}
.kpi-icon.pink{background:#fdeef1;}
.kpi-icon.purple{background:#f1eefe;}
.kpi-icon.red{background:var(--red-bg);}
.kpi-icon.teal{background:#e8f3fb;}
.kpi-label{font-size:12.5px;color:var(--text-light);font-weight:600;margin-bottom:6px;}
.kpi-value{font-size:19px;font-weight:700;color:var(--text-dark);letter-spacing:-0.2px;}
.kpi-sub{font-size:12px;color:var(--text-light);margin-top:4px;font-weight:500;}
.kpi-sub.up{color:var(--green);font-weight:700;}
.kpi-sub.down{color:var(--red);font-weight:700;}

.card{
  background:var(--card-bg);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;
  box-shadow:var(--shadow);margin-bottom:16px;height:100%;
}
.card-header{
  background:linear-gradient(135deg,#5b3df0,#4f39f6);color:#fff;padding:13px 18px;font-size:14.5px;font-weight:700;
  display:flex;justify-content:space-between;align-items:center;letter-spacing:-0.1px;
}
.card-header a{color:#fff;font-size:12px;font-weight:600;text-decoration:none;opacity:0.92;display:flex;align-items:center;gap:4px;}
.card-header a:hover{opacity:1;text-decoration:underline;}
.card-body{padding:15px 18px 18px;}
.card-body.tight{padding-top:8px;}

.empty-state{text-align:center;padding:22px 16px;font-size:0.8rem;color:var(--text-light);
  background:#fbfbfe;border:1.5px dashed var(--border);border-radius:10px;line-height:1.55;}

table{width:100%;border-collapse:collapse;font-size:12.8px;}
th{
  text-align:right;color:var(--text-light);font-weight:700;padding:8px 4px;
  border-bottom:1.5px solid var(--border);font-size:11.8px;text-transform:uppercase;letter-spacing:0.2px;
  font-family:'Inter',sans-serif;
}
th:first-child,td:first-child{text-align:left;}
td{padding:10px 4px;border-bottom:1px solid #f1f2f6;color:var(--text-dark);text-align:right;font-weight:500;
  font-family:var(--mono);}
td:first-child{font-family:'Inter',sans-serif;color:var(--text-dark);font-weight:500;white-space:normal;}
tr:last-child td{border-bottom:none;}
tbody tr:hover td{background:#fafaff;}
.up-val{color:var(--green) !important;font-weight:700 !important;}
.down-val{color:var(--red) !important;font-weight:700 !important;}
.arrow{font-size:10px;margin-right:2px;}
.link-row{
  margin-top:12px;padding:11px;text-align:center;border:1px solid var(--border);
  border-radius:9px;font-size:13px;font-weight:700;color:var(--indigo);
  transition:background .15s, border-color .15s;
}
.link-row a{color:var(--indigo);text-decoration:none;display:block;}

.chart-controls{display:flex;justify-content:space-between;align-items:center;padding:14px 18px 0;}
.chart-title{font-size:14.5px;font-weight:700;color:var(--text-dark);}
.legend{display:flex;gap:18px;padding:10px 18px 0;font-size:12.5px;color:var(--text-mid);font-weight:600;}
.legend span{display:flex;align-items:center;gap:6px;}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;}

.nse-row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;padding:15px 18px 8px;font-size:12.8px;}
.nse-item .lbl{color:var(--text-light);font-size:11.5px;margin-bottom:4px;font-weight:600;}
.nse-item .val{font-weight:700;color:var(--text-dark);font-size:13.8px;font-family:var(--mono);}

.price-section{padding:8px 18px 18px;}
.price-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;}
.price-header .chart-title{font-size:13.5px;}

.doc-card-body{padding:0;}
.doc-empty{display:flex;flex-direction:column;align-items:center;text-align:center;padding:26px 18px 20px;}
.doc-icon{
  width:58px;height:58px;border-radius:50%;background:var(--indigo-light);
  display:flex;align-items:center;justify-content:center;font-size:24px;margin-bottom:14px;color:var(--indigo);
}
.doc-empty h4{margin:2px 0 6px;font-size:14.5px;color:var(--text-dark);}
.doc-empty p{margin:0 0 16px;font-size:12px;color:var(--text-light);max-width:240px;line-height:1.5;}

.doclist-row{display:flex;align-items:center;justify-content:space-between;
  padding:10px 14px;border-bottom:1px solid #f3f4f6;}
.doclist-row:last-child{border-bottom:none;}
.doclist-left{display:flex;align-items:center;gap:10px;}
.doclist-icon{color:#ef4444;font-size:1.05rem;}
.doclist-name{font-size:0.8rem;color:var(--text-dark);font-weight:600;}
.doclist-meta{font-size:0.7rem;color:var(--text-light);}

.status-card{
  background:var(--green-bg);border:1px solid var(--green-border);border-radius:var(--radius);
  padding:18px 20px;box-shadow:var(--shadow);
}
.status-title{display:flex;align-items:center;gap:9px;font-weight:700;color:#15803d;font-size:14.5px;margin-bottom:8px;}
.status-check{
  width:21px;height:21px;border-radius:50%;background:#16a34a;color:#fff;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;
}
.status-text{font-size:12.8px;color:#256b43;line-height:1.55;}

/* ============ LEGAL PAGE ============ */
.section-header{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:18px;}
.section-header-left{display:flex;gap:12px;align-items:flex-start;}
.section-icon{
  width:38px;height:38px;border-radius:10px;background:var(--indigo-light);
  display:flex;align-items:center;justify-content:center;font-size:18px;color:var(--indigo);flex-shrink:0;
}
.section-title{font-size:20px;font-weight:800;color:var(--text-dark);letter-spacing:-0.3px;}
.section-sub{font-size:13px;color:var(--text-light);margin-top:3px;}
.updated-block{text-align:right;font-size:12.5px;color:var(--text-light);}
.updated-block .updated-time{font-weight:700;color:var(--text-dark);}

.legal-kpi-card{
  background:var(--card-bg);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:17px;transition:box-shadow .15s, transform .15s;height:100%;
}
.legal-kpi-card:hover{box-shadow:0 4px 14px rgba(16,24,40,0.08);transform:translateY(-1px);}
.kpi-top{display:flex;align-items:center;gap:10px;margin-bottom:10px;}
.legal-kpi-value{font-size:22px;font-weight:800;letter-spacing:-0.4px;margin-bottom:4px;}
.risk-high{color:var(--red);}
.risk-moderate{color:var(--orange);}
.risk-low{color:var(--green);}
.risk-bar-track{height:6px;border-radius:4px;background:#f1f2f6;margin-top:10px;overflow:hidden;}
.risk-bar-fill{height:100%;border-radius:4px;}

.tab-note{font-size:12px;color:var(--text-light);margin:2px 0 12px;}

.main-grid-gap{height:4px;}
.case-card{
  background:var(--card-bg);border:1px solid var(--border);border-radius:12px;box-shadow:var(--shadow);
  padding:16px 18px;display:flex;gap:14px;align-items:flex-start;
  border-left:3px solid transparent;margin-bottom:12px;
}
.case-icon{
  width:38px;height:38px;border-radius:9px;flex-shrink:0;display:flex;align-items:center;
  justify-content:center;font-size:16px;
}
.case-icon.tribunal{background:#f1eefe;color:var(--indigo);}
.case-icon.court{background:#eef2ff;color:#4338ca;}
.case-icon.regulatory{background:#e8f9ee;color:var(--green);}
.case-icon.news{background:#f1f2f6;color:var(--text-mid);}
.case-content{flex:1;min-width:0;}
.case-title-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:5px;}
.case-title{font-size:14.5px;font-weight:700;color:var(--text-dark);line-height:1.4;}
.badge{
  font-size:10.5px;font-weight:800;padding:3px 9px;border-radius:6px;letter-spacing:0.3px;white-space:nowrap;
}
.badge.tribunal{background:#f1eefe;color:#6d3ff0;}
.badge.court-case{background:#eef2ff;color:#4338ca;}
.badge.regulatory{background:#e8f9ee;color:#0f8a3e;}
.badge.news{background:#f1f2f6;color:var(--text-mid);}
.badge.high{background:var(--red-bg);color:var(--red);}
.badge.moderate{background:var(--orange-bg);color:var(--orange);}
.badge.low{background:var(--green-bg);color:var(--green);}
.case-meta{font-size:12px;color:var(--text-light);margin-bottom:7px;font-weight:500;}
.case-desc{font-size:12.8px;color:var(--text-mid);line-height:1.55;}
.case-right{display:flex;flex-direction:column;align-items:flex-end;gap:6px;flex-shrink:0;}
.match-pct{font-size:12.5px;color:var(--text-light);font-weight:600;white-space:nowrap;}

.sidebar{display:flex;flex-direction:column;gap:16px;}
.side-card{
  background:var(--card-bg);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:18px 20px;
}
.card-title-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;}
.card-title{font-size:14.5px;font-weight:700;color:var(--text-dark);display:flex;align-items:center;gap:8px;}
.bar-accent{width:4px;height:16px;background:var(--indigo);border-radius:2px;display:inline-block;}

.donut-row{display:flex;align-items:center;gap:20px;}
.legend-list{display:flex;flex-direction:column;gap:10px;font-size:12.5px;flex:1;}
.legend-item{display:flex;align-items:center;justify-content:space-between;gap:8px;}
.legend-left{display:flex;align-items:center;gap:8px;color:var(--text-mid);font-weight:600;}
.legend-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;display:inline-block;}
.legend-val{font-weight:700;color:var(--text-dark);}

.risk-area-list{display:flex;flex-direction:column;gap:12px;}
.risk-area-item{display:flex;justify-content:space-between;align-items:center;font-size:13px;}
.risk-area-name{color:var(--text-dark);font-weight:600;}

.download-card{background:linear-gradient(135deg,#f6f5ff,#eef0ff);border:1px solid #e2e0ff;}
.download-title{font-size:14px;font-weight:700;color:var(--text-dark);margin-bottom:5px;}
.download-sub{font-size:12.3px;color:var(--text-mid);margin-bottom:14px;line-height:1.5;}

/* ============ DECISION PAGE ============ */
.verdict-card{border-radius:14px;padding:22px;margin-bottom:16px;display:flex;
  align-items:center;justify-content:space-between;}
.verdict-left{display:flex;align-items:center;gap:16px;}
.verdict-badge{width:56px;height:56px;border-radius:14px;display:flex;align-items:center;
  justify-content:center;font-size:1.6rem;flex-shrink:0;background:rgba(255,255,255,0.55);}
.verdict-title{font-size:1.15rem;font-weight:800;}
.verdict-sub{font-size:0.8rem;color:var(--text-mid);margin-top:2px;}
.verdict-confidence{font-size:0.78rem;color:var(--text-mid);text-align:right;}
.prob-row{display:flex;align-items:center;gap:10px;margin-bottom:8px;}
.prob-label{font-size:0.75rem;color:var(--text-mid);width:64px;flex-shrink:0;}
.prob-track{flex:1;height:10px;border-radius:999px;background:#f1f2f6;overflow:hidden;}
.prob-fill{height:100%;border-radius:999px;}
.prob-pct{font-size:0.75rem;color:var(--text-dark);font-weight:600;width:44px;text-align:right;flex-shrink:0;
  font-family:var(--mono);}
.factor-item{display:flex;align-items:flex-start;gap:8px;font-size:0.82rem;color:var(--text-mid);
  padding:8px 0;border-bottom:1px solid #f3f4f6;}
.factor-item:last-child{border-bottom:none;}
.decision-note{font-size:0.72rem;color:var(--text-light);line-height:1.5;margin-top:10px;
  padding:10px 12px;background:#f9fafb;border-radius:8px;}

.placeholder-card{
  background:var(--card-bg);border:1px solid var(--border);border-radius:var(--radius);
  box-shadow:var(--shadow);padding:60px 30px;text-align:center;color:var(--text-light);
}
.placeholder-card .big-icon{font-size:36px;margin-bottom:14px;}
.placeholder-card h3{color:var(--text-dark);font-size:17px;margin:0 0 8px;}
.placeholder-card p{font-size:13.5px;margin:0;}

.footer{text-align:center;padding:14px;font-size:0.73rem;color:var(--text-light);
  border-top:1px solid var(--border);background:#fff;margin-top:10px;}

/* ══════════════════════════════ STREAMLIT ADAPTATION ══════════════════════════════
   Everything below maps Streamlit's own widget DOM onto the mockup's visual
   language, since real <input>/<button>/<select> elements can't be swapped
   for the mockup's static markup. */
.block-container { padding: 0 !important; max-width: 100% !important; }
header[data-testid="stHeader"] { display: none; }
section[data-testid="stSidebar"] { display: none; }

div[data-testid="stTextInput"] input, div[data-testid="stSelectbox"] > div{
  border-radius:9px !important; border:1px solid var(--border) !important;
  background:#fbfbfd !important; font-size:13.5px !important; color:var(--text-dark) !important;
}
div[data-testid="stTextInput"] input:focus{
  border-color:var(--indigo) !important; background:#fff !important;
  box-shadow:0 0 0 3px rgba(79,57,246,0.12) !important;
}
div[data-testid="stTextInput"] label p, div[data-testid="stSelectbox"] label p{
  font-size:13px !important; font-weight:700 !important; color:var(--text-dark) !important;
}
.input-card div[data-testid="stTextInput"], .input-card div[data-testid="stSelectbox"]{margin-bottom:14px;}

div.stButton > button[kind="primary"], div.stDownloadButton > button{
  background:linear-gradient(135deg,#5b3df0,#4636e0) !important; color:#fff !important;
  border:none !important; border-radius:9px !important; font-weight:700 !important;
  transition: box-shadow .15s ease, transform .15s ease !important;
  box-shadow: 0 2px 8px rgba(79,57,246,0.3) !important;
}
div.stButton > button[kind="primary"]:hover, div.stDownloadButton > button:hover{
  box-shadow: 0 4px 14px rgba(79,57,246,0.4) !important;
  transform: translateY(-1px);
}
div.stButton > button[kind="secondary"]{
  border-radius:9px !important; font-weight:600 !important; color:var(--text-dark) !important;
  border-color:var(--border) !important;
}
div.stButton > button[kind="secondary"]:hover{background:#fafafd !important;}

[data-testid="stFileUploaderDropzone"]{
  border: 1.5px dashed #c7d2fe !important; background:#fafafe !important; border-radius:10px !important;
}
div[data-testid="stFileUploader"] button{
  background:var(--indigo) !important; color:#fff !important; border:none !important; border-radius:8px !important;
}

.stTabs [data-baseweb="tab-list"] { gap: 22px; border-bottom: 1px solid var(--border); }
.stTabs [data-baseweb="tab"] { font-size: 13.5px; color: var(--text-light); font-weight: 700; padding-bottom:10px; }
.stTabs [aria-selected="true"] { color: var(--indigo) !important; }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--indigo) !important; height:2.5px !important; }
.stTabs [data-baseweb="tab-border"] { display:none; }

div[data-testid="stExpander"]{border:1px solid var(--border) !important;border-radius:var(--radius) !important;
  box-shadow:var(--shadow) !important; background:#fff !important;}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  HELPERS — shared
# ══════════════════════════════════════════════════════════════════════════
def _guess_nse_symbol_from_screener_url(screener_url):
    """Best-effort NSE-symbol guess from a Screener.in company URL."""
    if not screener_url:
        return None
    try:
        seg = screener_url.split("/company/", 1)[1].split("/", 1)[0]
    except IndexError:
        return None
    seg = seg.strip()
    if seg and not seg.isdigit():
        return seg.upper()
    return None


def backend_err(e):
    try:
        if hasattr(e, "response") and e.response is not None:
            return e.response.json().get("detail", str(e))
    except Exception:
        pass
    return str(e)


def fmt_size(num_bytes):
    if num_bytes is None:
        return "—"
    mb = num_bytes / (1024 * 1024)
    return f"{mb:.1f} MB"


def fmt_date(iso_str):
    if not iso_str:
        return "—"
    try:
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00")).strftime("%d %b %Y")
    except Exception:
        return iso_str


def price_history(symbol, period="1mo"):
    sym = symbol.upper().strip()
    if not sym.endswith(".NS"):
        sym += ".NS"
    try:
        return yf.Ticker(sym).history(period=period)
    except Exception:
        return pd.DataFrame()


def render_pdf_viewer(document_id: str, widget_key: str, height: int = 600):
    cache_key = f"pdf_bytes_{document_id}"
    if cache_key not in st.session_state:
        if st.button("📄 Load PDF Preview", key=f"load_{widget_key}"):
            try:
                r = requests.get(f"{BACKEND_URL}/api/document/{document_id}/file", timeout=30)
                r.raise_for_status()
                st.session_state[cache_key] = r.content
                st.rerun()
            except Exception as e:
                st.error(f"Could not load PDF: {backend_err(e)}")
    else:
        b64 = base64.b64encode(st.session_state[cache_key]).decode()
        st.markdown(
            f'<iframe src="data:application/pdf;base64,{b64}" width="100%" height="{height}" '
            f'style="border:1px solid #e7e8ee;border-radius:8px;"></iframe>',
            unsafe_allow_html=True,
        )
        if st.button("✕ Close Preview", key=f"close_{widget_key}"):
            del st.session_state[cache_key]
            st.rerun()


def _num(v):
    if v in (None, "", "—"):
        return None
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def _match_rows(rows: list, row_map: list) -> list:
    """Re-labels a Screener rows list to a fixed display order, matching
    each target label against the source 'particular' text by substring."""
    out = []
    for label, candidates in row_map:
        found = None
        for row in rows or []:
            name = (row.get("particular") or "").lower()
            if any(c in name for c in candidates):
                found = row
                break
        if found:
            out.append({"particular": label, "values": found.get("values") or {}})
    return out


def _best_scope_data(screener_data: dict):
    """Prefers consolidated over standalone."""
    if not screener_data:
        return None, None
    if screener_data.get("consolidated"):
        return screener_data["consolidated"], "Consolidated"
    if screener_data.get("standalone"):
        return screener_data["standalone"], "Standalone"
    return None, None


def _recent_years(years: list, n: int = 5) -> list:
    return years[-n:] if years and len(years) > n else (years or [])


def _latest_metric(rows, candidates, years):
    for row in rows or []:
        name = (row.get("particular") or "").lower()
        if any(c in name for c in candidates):
            values = row.get("values") or {}
            if not years:
                return None, None
            latest = _num(values.get(years[-1]))
            prev = _num(values.get(years[-2])) if len(years) > 1 else None
            yoy = ((latest - prev) / abs(prev)) * 100 if latest is not None and prev not in (None, 0) else None
            return latest, yoy
    return None, None


KEY_SUMMARY_ROW_DEFS = [
    ("Revenue from Operations", "profit_loss", ["sales", "revenue from operations"]),
    ("Other Income", "profit_loss", ["other income"]),
    ("Depreciation and amortisation expense", "profit_loss", ["depreciation"]),
    ("Finance costs", "profit_loss", ["interest"]),
    ("PBT", "profit_loss", ["profit before tax", "pbt"]),
    ("PAT", "profit_loss", ["net profit", "pat "]),
    ("Share Capital", "balance_sheet", ["equity share capital", "share capital"]),
    ("Reserves & Surplus", "balance_sheet", ["reserves"]),
    ("Net Worth", "balance_sheet", ["net worth", "total equity", "shareholder"]),
]


def _build_key_summary_table(scope_data: dict):
    sections = {"profit_loss": scope_data.get("profit_loss", {}) or {},
                "balance_sheet": scope_data.get("balance_sheet", {}) or {}}
    years_all = sections["profit_loss"].get("years") or []
    years = years_all[-2:] if len(years_all) >= 2 else years_all

    rows = []
    for label, section_key, candidates in KEY_SUMMARY_ROW_DEFS:
        section_rows = sections[section_key].get("rows") or []
        found = None
        for row in section_rows:
            name = (row.get("particular") or "").lower()
            if any(c in name for c in candidates):
                found = row
                break
        src_vals = (found.get("values") or {}) if found else {}
        rows.append({"particular": label, "values": {y: src_vals.get(y) for y in years}})
    return rows, years


RATIO_ROW_MAP_FULL = [
    ("Gross Margin (%)", ["gross margin"]),
    ("EBITDA Margin (%)", ["ebitda margin"]),
    ("PAT Margin (%)", ["pat margin", "net profit margin"]),
    ("ROE (%)", ["roe"]),
    ("ROCE (%)", ["roce"]),
    ("ROA (%)", ["roa"]),
    ("Debt/Equity (x)", ["debt / equity", "debt-equity", "debt : equity", "debt to equity"]),
    ("Current Ratio (x)", ["current ratio"]),
    ("Interest Coverage (x)", ["interest coverage"]),
]
CONSOLIDATED_RATIO_SUBSET = [
    ("Gross Margin (%)", ["gross margin"]),
    ("EBITDA Margin (%)", ["ebitda margin"]),
    ("ROE (%)", ["roe"]),
    ("ROCE (%)", ["roce"]),
    ("Debt/Equity (x)", ["debt / equity", "debt-equity", "debt : equity", "debt to equity"]),
]
QUARTERLY_ROW_MAP = [
    ("Revenue", ["sales", "revenue from operations"]),
    ("EBITDA", ["operating profit", "ebitda"]),
    ("PAT", ["net profit", "pat "]),
    ("EPS", ["eps"]),
]


# ══════════════════════════════════════════════════════════════════════════
#  RENDER HELPERS — mockup-shaped card/table/kpi builders
# ══════════════════════════════════════════════════════════════════════════
def kpi_card(col, icon, icon_class, label, value, sub=None, sub_class=""):
    with col:
        sub_html = f'<div class="kpi-sub {sub_class}">{sub}</div>' if sub else ""
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-icon {icon_class}">{icon}</div>
          <div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {sub_html}
          </div>
        </div>""", unsafe_allow_html=True)


def render_table_card(title, years, rows, header_link=None, footer_link=None,
                       change_col=False, change_col_label="Change (%)",
                       empty_msg="No data extracted for this table."):
    """Renders one `.card` with a gradient `.card-header` and a Particulars
    x Years `<table>`, matching the mockup's financial-table cards exactly."""
    header_link_html = (f'<a href="{header_link[1]}" target="_blank">{header_link[0]}</a>'
                         if header_link else "")
    if not rows or not years:
        st.markdown(
            f'<div class="card"><div class="card-header">{title}{header_link_html}</div>'
            f'<div class="card-body"><div class="empty-state">{empty_msg}</div></div></div>',
            unsafe_allow_html=True,
        )
        return

    th_extra = f"<th>{change_col_label}</th>" if change_col else ""
    header_cells = "".join(f"<th>{y}</th>" for y in years) + th_extra
    body_rows = ""
    for row in rows:
        particular = row.get("particular", "—")
        values = row.get("values") or {}
        cells = "".join(
            f"<td>{values.get(y) if values.get(y) not in (None, '', '—') else '—'}</td>" for y in years
        )
        chg_cell = ""
        if change_col:
            prev = _num(values.get(years[0])) if len(years) > 1 else None
            latest = _num(values.get(years[-1])) if years else None
            if prev not in (None, 0) and latest is not None:
                chg = ((latest - prev) / abs(prev)) * 100
                arrow = "▲" if chg >= 0 else "▼"
                cls = "up-val" if chg >= 0 else "down-val"
                chg_cell = f'<td class="{cls}"><span class="arrow">{arrow}</span>{abs(chg):.2f}%</td>'
            else:
                chg_cell = "<td>—</td>"
        body_rows += f"<tr><td>{particular}</td>{cells}{chg_cell}</tr>"

    footer_html = f'<div class="link-row">{footer_link}</div>' if footer_link else ""
    st.markdown(f"""
    <div class="card">
      <div class="card-header">{title}{header_link_html}</div>
      <div class="card-body">
        <table>
          <tr><th>Particulars</th>{header_cells}</tr>
          {body_rows}
        </table>
        {footer_html}
      </div>
    </div>
    """, unsafe_allow_html=True)


def _parse_any_date(s):
    """Best-effort parse of the assorted date strings the backend returns
    (RSS pubDate for articles, 'D Month, YYYY' for Indian Kanoon cases)."""
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ("%d %B, %Y", "%d %b, %Y", "%d %B %Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            continue
    return None


def _article_type(article):
    """Classifies a news article into tribunal / regulatory / news using
    its already-extracted matched_keywords -- no invented categorization,
    just a relabeling of real signals already on the object."""
    kws = {k.lower() for k in (article.get("matched_keywords") or [])}
    if kws & {"nclt", "nclat", "tribunal", "arbitration", "insolvency", "bankruptcy"}:
        return "tribunal", "⚖️", "TRIBUNAL", "tribunal"
    if kws & {"sebi", "penalty", "fine", "regulatory", "probe", "show cause", "violation"}:
        return "regulatory", "📄", "REGULATORY", "regulatory"
    return "news", "🗞️", "NEWS", "news"


# ══════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════
for k, v in {
    "active_page": "Financials",
    "doc_ids": {"annual_report": None, "balance_sheet": None},
    "doc_labels": {"annual_report": None, "balance_sheet": None},
    "doc_sizes": {"annual_report": None, "balance_sheet": None},
    "summary_by_type": {"annual_report": None, "balance_sheet": None},
    "full_analysis_by_type": {"annual_report": None, "balance_sheet": None},
    "show_full_analysis_by_type": {"annual_report": False, "balance_sheet": False},
    "full_analysis_error_by_type": {"annual_report": None, "balance_sheet": None},
    "nse": None,
    "nse_sym": "",
    "legal_result": None,
    "decision_result": None,
    "active_company_name": "",
    "active_company_website": "",
    "active_nse_symbol": "",
    "screener_data": None,
    "screener_error": None,
    "legal_company": "",
    "legal_days_back": 365,
    "show_upload_panel": False,
    "nse_fetch_error": None,
    "trigger_reanalyze": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


def fetch_summary_for_doc(dtype: str, doc_id: str):
    with st.spinner(f"Analyzing {dtype.replace('_', ' ')}..."):
        try:
            r = requests.post(f"{BACKEND_URL}/api/analyze/summary",
                               json={"document_id": doc_id}, timeout=60)
            r.raise_for_status()
            st.session_state.summary_by_type[dtype] = r.json()
            st.session_state.full_analysis_by_type[dtype] = None
            st.session_state.show_full_analysis_by_type[dtype] = False
            st.session_state.full_analysis_error_by_type[dtype] = None
        except Exception as e:
            st.error(f"{dtype.replace('_', ' ').title()}: {backend_err(e)}")


# ══════════════════════════════════════════════════════════════════════════
#  TOP NAV
# ══════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="topbar">
  <div class="topbar-left">
    <div class="logo">M</div>
    <div class="brand">Customer Assessment AI</div>
  </div>
  <div class="topbar-right">
    <div class="date-pill">📅 Data as on: {datetime.now().strftime("%d %b %Y")}</div>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="navrow">', unsafe_allow_html=True)
nc1, nc2, nc3, _nsp = st.columns([1, 1, 1, 8])
with nc1:
    if st.button("📈 Financials", key="nav_financials", use_container_width=True,
                 type="primary" if st.session_state.active_page == "Financials" else "secondary"):
        st.session_state.active_page = "Financials"
        st.rerun()
with nc2:
    if st.button("⚖️ Legal", key="nav_legal", use_container_width=True,
                 type="primary" if st.session_state.active_page == "Legal" else "secondary"):
        st.session_state.active_page = "Legal"
        st.rerun()
with nc3:
    if st.button("🎯 Decision", key="nav_decision", use_container_width=True,
                 type="primary" if st.session_state.active_page == "Decision" else "secondary"):
        st.session_state.active_page = "Decision"
        st.rerun()
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="container">', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  SHARED INPUT CARD  (Company Name / Website / NSE Symbol / Analyze button)
# ══════════════════════════════════════════════════════════════════════════
def render_input_card(button_label: str, button_key: str):
    st.markdown('<div class="input-card">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1.2, 1.2, 1, 0.9])
    with c1:
        st.markdown('<div class="field"><label>Company Name</label></div>', unsafe_allow_html=True)
        name_val = st.text_input("Company name", value=st.session_state.active_company_name,
                                  placeholder="e.g. Larsen & Toubro Limited",
                                  label_visibility="collapsed", key=f"{button_key}_company_name")
    with c2:
        st.markdown('<div class="field"><label>Company Website (Optional)</label></div>', unsafe_allow_html=True)
        website_val = st.text_input("Company website", value=st.session_state.active_company_website,
                                     placeholder="https://www.example.com",
                                     label_visibility="collapsed", key=f"{button_key}_company_website")
    with c3:
        st.markdown('<div class="field"><label>NSE Symbol (Optional)</label></div>', unsafe_allow_html=True)
        nse_val = st.text_input("NSE Symbol", value=st.session_state.active_nse_symbol,
                                 placeholder="e.g. LT", label_visibility="collapsed",
                                 key=f"{button_key}_nse_symbol")
    with c4:
        st.markdown('<div style="height:29px;"></div>', unsafe_allow_html=True)
        clicked = st.button(button_label, type="primary", use_container_width=True, key=button_key)
    st.markdown('</div>', unsafe_allow_html=True)
    return name_val.strip(), website_val.strip(), nse_val.strip().upper(), clicked


# ══════════════════════════════════════════════════════════════════════════
#  FINANCIALS PAGE
# ══════════════════════════════════════════════════════════════════════════
def render_financials():
    company_name_input, company_website_input, nse_symbol_input, fetch_all_clicked = render_input_card(
        "✨ Analyze Company", "analyze_company_btn"
    )

    if st.session_state.pop("trigger_reanalyze", False):
        fetch_all_clicked = True
        company_name_input = st.session_state.active_company_name
        company_website_input = st.session_state.active_company_website
        nse_symbol_input = st.session_state.active_nse_symbol

    if fetch_all_clicked:
        st.session_state.active_company_name = company_name_input
        st.session_state.active_company_website = company_website_input
        st.session_state.active_nse_symbol = nse_symbol_input
        st.session_state.legal_result = None
        st.session_state.decision_result = None

        if st.session_state.active_company_name:
            with st.spinner("Fetching balance sheet / P&L / ratios from Screener.in..."):
                try:
                    r = requests.post(f"{BACKEND_URL}/api/screener/fetch",
                                       json={"company_name": st.session_state.active_company_name},
                                       timeout=30)
                    r.raise_for_status()
                    st.session_state.screener_data = r.json()
                    st.session_state.screener_error = None
                except Exception as e:
                    st.session_state.screener_data = None
                    st.session_state.screener_error = backend_err(e)

        if st.session_state.active_nse_symbol:
            symbol_to_fetch, auto_derived = st.session_state.active_nse_symbol, False
        else:
            symbol_to_fetch, auto_derived = _guess_nse_symbol_from_screener_url(
                (st.session_state.screener_data or {}).get("screener_url")
            ), True

        if symbol_to_fetch:
            with st.spinner("Fetching NSE quote..."):
                try:
                    r = requests.get(f"{BACKEND_URL}/api/nse/quote",
                                      params={"symbol": symbol_to_fetch}, timeout=20)
                    r.raise_for_status()
                    st.session_state.nse = r.json()
                    st.session_state.nse_sym = symbol_to_fetch
                    st.session_state.nse_fetch_error = None
                    if auto_derived:
                        st.session_state.active_nse_symbol = symbol_to_fetch
                except Exception as e:
                    st.session_state.nse = None
                    st.session_state.nse_fetch_error = None if auto_derived else f"NSE fetch failed: {backend_err(e)}"
        else:
            st.session_state.nse_fetch_error = None

        if st.session_state.active_company_website:
            with st.spinner("Scanning company website for financial documents..."):
                try:
                    r = requests.post(f"{BACKEND_URL}/api/crawl-website",
                                       json={"company_website": st.session_state.active_company_website},
                                       timeout=60)
                    r.raise_for_status()
                    crawl_results = r.json().get("results", {})
                    for dtype, item in crawl_results.items():
                        if item and item.get("document_id"):
                            st.session_state.doc_ids[dtype] = item["document_id"]
                            st.session_state.doc_labels[dtype] = item.get("label", dtype)
                            st.session_state.doc_sizes[dtype] = None
                            fetch_summary_for_doc(dtype, item["document_id"])
                except Exception:
                    pass
        st.rerun()

    if st.session_state.screener_error:
        st.error(f"Screener.in: {st.session_state.screener_error}")
    if st.session_state.nse_fetch_error:
        st.error(st.session_state.nse_fetch_error)

    nse = st.session_state.nse or {}
    screener_data = st.session_state.screener_data
    standalone_scope = (screener_data or {}).get("standalone")
    consolidated_scope = (screener_data or {}).get("consolidated")
    primary_scope = standalone_scope or consolidated_scope
    best_scope, best_scope_label = _best_scope_data(screener_data)
    analysis_done = bool(screener_data or nse)

    # ── KPI row (Market Price / Market Cap / P/E / 52W High-Low / Div Yield) ──
    st.markdown('<div class="kpi-row">', unsafe_allow_html=True)
    k1, k2, k3, k4, k5 = st.columns(5)
    if nse.get("last_price") is not None:
        pct = nse.get("pct_change") or 0
        arrow = "▲" if pct >= 0 else "▼"
        kpi_card(k1, "📈", "blue", "Market Price (NSE)", f"₹ {nse['last_price']:,.2f}",
                 f"{arrow} {abs(pct):.2f}% (₹{abs(nse.get('change') or 0):,.2f})",
                 "up" if pct >= 0 else "down")
    else:
        kpi_card(k1, "📈", "blue", "Market Price (NSE)", "—", "Add an NSE symbol above")

    if nse.get("market_cap_cr") is not None:
        kpi_card(k2, "💰", "green", "Market Cap", f"₹ {nse['market_cap_cr']:,.0f} Cr",
                  f"As on {datetime.now().strftime('%d %b %Y')}")
    else:
        kpi_card(k2, "💰", "green", "Market Cap", "—")

    if nse.get("pe_ratio") is not None:
        kpi_card(k3, "🏅", "orange", "P/E Ratio (TTM)", f"{nse['pe_ratio']:.2f}", "Industry Avg: NA")
    else:
        kpi_card(k3, "🏅", "orange", "P/E Ratio (TTM)", "—", "Industry Avg: NA")

    if nse.get("week52_high") is not None:
        kpi_card(k4, "🏷️", "lightblue", "52 Week High / Low",
                  f"₹ {nse['week52_high']:,.0f} / ₹ {nse['week52_low']:,.0f}",
                  f"As on {datetime.now().strftime('%d %b %Y')}")
    else:
        kpi_card(k4, "🏷️", "lightblue", "52 Week High / Low", "—")

    if nse.get("dividend_yield_pct") is not None:
        kpi_card(k5, "🎂", "pink", "Dividend Yield", f"{nse['dividend_yield_pct']:.2f}%", "TTM")
    else:
        kpi_card(k5, "🎂", "pink", "Dividend Yield", "—")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── grid3 row 1: Key Financial Summary | Financial Trend | NSE Summary ──
    g1, g2, g3 = st.columns([1.15, 1.5, 1], gap="medium")
    with g1:
        if primary_scope:
            rows, years = _build_key_summary_table(primary_scope)
            link = (f"View Full Financial Statements ↗", screener_data.get("screener_url", "#"))
            render_table_card("Key Financial Summary (₹ Cr)", years, rows,
                               footer_link=f'<a href="{link[1]}" target="_blank">{link[0]}</a>')
        else:
            render_table_card("Key Financial Summary (₹ Cr)", [], [],
                               empty_msg='Enter a company name above and click "Analyze Company" to pull financials from Screener.in.')

    with g2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        year_range = None
        chart_hdr_l, chart_hdr_r = st.columns([2, 1])
        with chart_hdr_l:
            st.markdown('<div class="chart-controls" style="padding-left:0;"><div class="chart-title">Financial Trend (₹ Cr)</div></div>', unsafe_allow_html=True)
        with chart_hdr_r:
            year_range = st.selectbox("Range", ["3 Years", "5 Years", "All"], index=1,
                                       label_visibility="collapsed", key="trend_year_range")
        st.markdown('<div class="legend"><span><span class="dot" style="background:#4f39f6;"></span>Revenue from Operations</span>'
                    '<span><span class="dot" style="background:#16a34a;"></span>PAT</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="card-body tight">', unsafe_allow_html=True)
        if not best_scope:
            st.markdown('<div class="empty-state">Multi-year Revenue and PAT trend will appear here once a company is analyzed.</div>', unsafe_allow_html=True)
        else:
            pl = best_scope.get("profit_loss", {})
            n_years = {"3 Years": 3, "5 Years": 5, "All": 99}[year_range]
            pl_years = _recent_years(pl.get("years", []), n=n_years)

            def _series(rows, years, candidates):
                for row in rows or []:
                    name = (row.get("particular") or "").lower()
                    if any(c in name for c in candidates):
                        vals = row.get("values") or {}
                        return [_num(vals.get(y)) for y in years]
                return [None] * len(years)

            rev_series = _series(pl.get("rows"), pl_years, ["sales", "revenue from operations"])
            pat_series = _series(pl.get("rows"), pl_years, ["net profit", "pat "])

            if not any(v is not None for v in rev_series + pat_series):
                st.markdown('<div class="empty-state">No multi-year Revenue/PAT rows found for this company on Screener.in.</div>', unsafe_allow_html=True)
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=pl_years, y=rev_series, name="Revenue from Operations",
                                          mode="lines+markers", line=dict(color="#4f39f6", width=2.5),
                                          fill="tozeroy", fillcolor="rgba(79,57,246,0.07)", connectgaps=True))
                fig.add_trace(go.Scatter(x=pl_years, y=pat_series, name="PAT",
                                          mode="lines+markers", line=dict(color="#16a34a", width=2.5),
                                          connectgaps=True))
                fig.update_layout(
                    height=260, margin=dict(l=0, r=0, t=6, b=0), showlegend=False,
                    plot_bgcolor="white", paper_bgcolor="white",
                    xaxis=dict(showgrid=False, tickfont=dict(size=10, color="#8b8fa3")),
                    yaxis=dict(showgrid=True, gridcolor="#f1f2f6", tickfont=dict(size=10, color="#8b8fa3")),
                )
                st.plotly_chart(fig, use_container_width=True, key="financial_trend_chart")
        if screener_data:
            st.link_button("📊 View Detailed Charts", screener_data.get("screener_url", "#"), use_container_width=True)
        st.markdown('</div></div>', unsafe_allow_html=True)

    with g3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        nse_symbol_display = nse.get("symbol") or st.session_state.nse_sym
        nse_link = f"https://www.nseindia.com/get-quotes/equity?symbol={nse_symbol_display}" if nse_symbol_display else "#"
        st.markdown(f'<div class="card-header">NSE Summary <a href="{nse_link}" target="_blank">View More on NSE ↗</a></div>', unsafe_allow_html=True)
        if nse:
            def _fmt(v, prefix="₹"):
                return f'{prefix}{v:,.2f}' if isinstance(v, (int, float)) else "—"
            st.markdown(f"""
            <div class="nse-row">
              <div class="nse-item"><div class="lbl">Prev. Close</div><div class="val">{_fmt(nse.get('prev_close'))}</div></div>
              <div class="nse-item"><div class="lbl">Volume</div><div class="val">{f"{nse.get('volume'):,}" if isinstance(nse.get('volume'), (int, float)) else "—"}</div></div>
              <div class="nse-item"><div class="lbl">P/E Ratio (TTM)</div><div class="val">{_fmt(nse.get('pe_ratio'), prefix="")}</div></div>
              <div class="nse-item"><div class="lbl">52W High</div><div class="val">{_fmt(nse.get('week52_high'))}</div></div>
              <div class="nse-item"><div class="lbl">52W Low</div><div class="val">{_fmt(nse.get('week52_low'))}</div></div>
              <div class="nse-item"><div class="lbl">Dividend Yield</div><div class="val">{f"{nse.get('dividend_yield_pct')}%" if nse.get('dividend_yield_pct') is not None else "—"}</div></div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown('<div class="price-section">', unsafe_allow_html=True)
            ph_l, ph_r = st.columns([2, 1])
            with ph_l:
                st.markdown('<div class="chart-title">Price Chart</div>', unsafe_allow_html=True)
            with ph_r:
                period_label = st.selectbox("Period", ["1M", "3M", "6M", "1Y", "3Y", "5Y"], index=3,
                                             label_visibility="collapsed", key="nse_price_chart_period")
            period_map = {"1M": "1mo", "3M": "3mo", "6M": "6mo", "1Y": "1y", "3Y": "3y", "5Y": "5y"}
            hist = price_history(st.session_state.nse_sym, period_map[period_label])
            if not hist.empty:
                close = hist["Close"]
                up = close.iloc[-1] >= close.iloc[0]
                color = "#16a34a" if up else "#dc2626"
                fill = "rgba(22,163,74,0.08)" if up else "rgba(220,38,38,0.08)"
                price_fig = go.Figure()
                price_fig.add_trace(go.Scatter(
                    x=hist.index, y=close, mode="lines",
                    line=dict(color=color, width=1.8), fill="tozeroy", fillcolor=fill,
                    hovertemplate="₹%{y:,.2f}<br>%{x|%d %b %Y}<extra></extra>",
                ))
                price_fig.update_layout(
                    height=190, margin=dict(l=0, r=0, t=6, b=0),
                    xaxis=dict(showgrid=False, showline=False, tickfont=dict(size=9, color="#8b8fa3")),
                    yaxis=dict(showgrid=True, gridcolor="#f1f2f6", tickprefix="₹",
                               tickformat=",.0f", tickfont=dict(size=9, color="#8b8fa3")),
                    plot_bgcolor="white", paper_bgcolor="white", showlegend=False, hovermode="x unified",
                )
                st.plotly_chart(price_fig, use_container_width=True, key="nse_price_chart")
            else:
                st.markdown('<div class="empty-state">No price history available for this period.</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="card-body"><div class="empty-state">Enter an NSE Symbol above and click "Analyze Company" to pull a live quote.</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── grid3 row 2: Key Ratios | Cash Flow Statement | Consolidated Key Financial Summary ──
    g4, g5, g6 = st.columns(3, gap="medium")
    with g4:
        if best_scope:
            ratios = best_scope.get("ratios", {})
            r_years = _recent_years(ratios.get("years", []), n=3)
            r_rows = _match_rows(ratios.get("rows"), RATIO_ROW_MAP_FULL)
            render_table_card("Key Ratios", r_years, r_rows,
                               footer_link=f'<a href="{(screener_data or {}).get("screener_url", "#")}" target="_blank">View All Ratios ↗</a>')
        else:
            render_table_card("Key Ratios", [], [])
    with g5:
        if best_scope:
            cf = best_scope.get("cash_flow", {})
            cf_years = _recent_years(cf.get("years", []), n=3)
            render_table_card("Cash Flow Statement (₹ Cr)", cf_years, cf.get("rows") or [],
                               footer_link=f'<a href="{(screener_data or {}).get("screener_url", "#")}" target="_blank">View Cash Flow Statement ↗</a>')
        else:
            render_table_card("Cash Flow Statement (₹ Cr)", [], [])
    with g6:
        if consolidated_scope:
            rows, years = _build_key_summary_table(consolidated_scope)
            render_table_card("Consolidated Key Financial Summary (₹ Cr)", years, rows,
                               footer_link=f'<a href="{(screener_data or {}).get("screener_url", "#")}" target="_blank">View Consolidated Statements ↗</a>',
                               empty_msg="No consolidated financials found for this company (common for single-entity companies).")
        else:
            render_table_card("Consolidated Key Financial Summary (₹ Cr)", [], [],
                               empty_msg="No consolidated financials found for this company (common for single-entity companies).")

    # ── grid4: Quarterly | Consolidated Ratios | Consolidated Cash Flow | Documents/Status ──
    h1, h2, h3, h4 = st.columns(4, gap="medium")
    with h1:
        q_scope = standalone_scope or consolidated_scope
        if q_scope:
            q = q_scope.get("quarterly", {})
            q_years = _recent_years(q.get("years", []), n=4)
            q_rows = _match_rows(q.get("rows"), QUARTERLY_ROW_MAP)
            render_table_card("Quarterly Performance (Standalone) (₹ Cr)", q_years, q_rows,
                               change_col=True, change_col_label="YoY (%)")
        else:
            render_table_card("Quarterly Performance (Standalone) (₹ Cr)", [], [])
    with h2:
        if consolidated_scope:
            cr = consolidated_scope.get("ratios", {})
            cr_years = _recent_years(cr.get("years", []), n=3)
            cr_rows = _match_rows(cr.get("rows"), CONSOLIDATED_RATIO_SUBSET)
            render_table_card("Consolidated Ratios", cr_years, cr_rows)
        else:
            render_table_card("Consolidated Ratios", [], [])
    with h3:
        if consolidated_scope:
            ccf = consolidated_scope.get("cash_flow", {})
            ccf_years = _recent_years(ccf.get("years", []), n=3)
            render_table_card("Consolidated Cash Flow (₹ Cr)", ccf_years, ccf.get("rows") or [])
        else:
            render_table_card("Consolidated Cash Flow (₹ Cr)", [], [])
    with h4:
        # Documents Used
        n_docs = sum(1 for dt in ("annual_report", "balance_sheet") if st.session_state.doc_ids.get(dt))
        st.markdown('<div class="card"><div class="card-header">📄 Documents Used</div><div class="doc-card-body">', unsafe_allow_html=True)
        if n_docs == 0:
            st.markdown("""
            <div class="doc-empty">
              <div class="doc-icon">☁️</div>
              <h4>No documents yet</h4>
              <p>Upload financial statements or add a company website and click "Analyze Company" to auto-find documents.</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Upload Financial Document", key="show_upload_btn", type="primary", use_container_width=True):
                st.session_state.show_upload_panel = not st.session_state.show_upload_panel
        else:
            DOC_TITLES = {"annual_report": "Annual Report", "balance_sheet": "Balance Sheet / Financial Results"}
            rows_html = ""
            for dtype in ("annual_report", "balance_sheet"):
                doc_id = st.session_state.doc_ids.get(dtype)
                if not doc_id:
                    continue
                label = st.session_state.doc_labels.get(dtype) or DOC_TITLES[dtype]
                size = fmt_size(st.session_state.doc_sizes.get(dtype))
                rows_html += f"""
                <div class="doclist-row">
                  <div class="doclist-left">
                    <span class="doclist-icon">📕</span>
                    <div><div class="doclist-name">{label}</div><div class="doclist-meta">{size} · {DOC_TITLES[dtype]}</div></div>
                  </div>
                  <a href="{BACKEND_URL}/api/document/{doc_id}/file" target="_blank" style="font-size:0.75rem;color:var(--indigo);font-weight:600;text-decoration:none;">↓</a>
                </div>"""
            st.markdown(rows_html, unsafe_allow_html=True)
            if st.button("Upload Another Document", key="show_upload_btn2", use_container_width=True):
                st.session_state.show_upload_panel = not st.session_state.show_upload_panel
        st.markdown('</div></div>', unsafe_allow_html=True)

        if st.session_state.show_upload_panel:
            with st.container(border=True):
                upload_doc_type = st.selectbox("Document type", ["Annual Report", "Balance Sheet"], key="upload_doc_type_select")
                dtype = "annual_report" if upload_doc_type == "Annual Report" else "balance_sheet"
                f = st.file_uploader("Drag & drop your file here", type=["pdf"], key=f"{dtype}_upload")
                if f is not None and st.button("⬆ Upload & Extract", key=f"{dtype}_btn", use_container_width=True, type="primary"):
                    with st.spinner("Uploading..."):
                        try:
                            r = requests.post(
                                f"{BACKEND_URL}/api/upload",
                                files={"file": (f.name, f.getvalue(), "application/pdf")},
                                params={"doc_type": dtype}, timeout=60,
                            )
                            r.raise_for_status()
                            st.session_state.doc_ids[dtype] = r.json()["document_id"]
                            st.session_state.doc_labels[dtype] = f.name
                            st.session_state.doc_sizes[dtype] = len(f.getvalue())
                            st.session_state.show_upload_panel = False
                            fetch_summary_for_doc(dtype, st.session_state.doc_ids[dtype])
                            st.rerun()
                        except Exception as e:
                            st.error(backend_err(e))

        # Status card
        if analysis_done:
            matched = (screener_data or {}).get("matched_name")
            src_url = (screener_data or {}).get("screener_url")
            sub = f"Matched <strong>{matched}</strong> on Screener.in" if matched else "Data extracted from NSE"
            st.markdown(f"""
            <div class="status-card" style="margin-top:16px;">
              <div class="status-title"><span class="status-check">✓</span> Analysis Completed Successfully</div>
              <div class="status-text">{sub}</div>
            </div>
            """, unsafe_allow_html=True)
            sa1, sa2 = st.columns(2)
            with sa1:
                if src_url:
                    st.link_button("🔗 View Sources", src_url, use_container_width=True)
            with sa2:
                if st.button("🔄 Re-analyze", key="reanalyze_btn", use_container_width=True):
                    st.session_state.trigger_reanalyze = True
                    st.rerun()

    # ── AI Document Analysis (kept from the working app -- annual report /
    # balance sheet PDF extraction, not represented in the mockup but core
    # functionality) ──
    if any(st.session_state.doc_ids.values()):
        with st.expander("📄 AI Document Analysis (Annual Report / Balance Sheet)"):
            SUMMARY_CARD_SPECS = {
                "annual_report": {"label": "Annual Report Summary", "icon": "📄", "fields": [
                    ("total_revenue", "Total Revenue"), ("net_profit", "Net Profit"), ("ebitda", "EBITDA"),
                    ("operating_profit_margin_pct", "Operating Margin", "%"), ("net_profit_margin_pct", "Net Margin", "%"),
                    ("eps", "EPS"),
                ]},
                "balance_sheet": {"label": "Balance Sheet Summary", "icon": "📊", "fields": [
                    ("total_assets", "Total Assets"), ("total_liabilities", "Total Liabilities"),
                    ("net_worth", "Net Worth"), ("current_assets", "Current Assets"),
                    ("current_liabilities", "Current Liabilities"), ("debt_to_equity", "Debt to Equity"),
                ]},
            }
            sc1, sc2 = st.columns(2, gap="medium")
            for scol, dtype in zip((sc1, sc2), ("annual_report", "balance_sheet")):
                spec = SUMMARY_CARD_SPECS[dtype]
                s = st.session_state.summary_by_type.get(dtype)
                with scol:
                    if not st.session_state.doc_ids.get(dtype):
                        st.markdown(f'<div class="card"><div class="card-header">{spec["icon"]} {spec["label"]}</div>'
                                    f'<div class="card-body"><div class="empty-state">No {dtype.replace("_"," ")} uploaded yet.</div></div></div>',
                                    unsafe_allow_html=True)
                        continue
                    if not s:
                        st.markdown(f'<div class="card"><div class="card-header">{spec["icon"]} {spec["label"]}</div>'
                                    f'<div class="card-body"><div class="empty-state">Analyzing this document…</div></div></div>',
                                    unsafe_allow_html=True)
                        continue
                    fin = s.get("financials", {}) if isinstance(s, dict) else {}
                    rows_html = ""
                    for field in spec["fields"]:
                        key, label = field[0], field[1]
                        suffix = field[2] if len(field) > 2 else ""
                        item = fin.get(key) or {}
                        raw_val = item.get("value")
                        val = f"{raw_val}{suffix}" if raw_val not in (None, "") else "—"
                        rows_html += f"<tr><td>{label}</td><td>{val}</td></tr>"
                    st.markdown(f"""
                    <div class="card"><div class="card-header">{spec['icon']} {spec['label']}
                    <span style="font-size:12px;opacity:.85;">{s.get('report_period') or 'Period n/a'}</span></div>
                    <div class="card-body"><table>{rows_html}</table></div></div>
                    """, unsafe_allow_html=True)
                    if s.get("key_insights"):
                        st.markdown('<div style="font-weight:700;font-size:0.8rem;color:var(--indigo);margin:10px 0 4px 2px;">✨ Key Insights</div>', unsafe_allow_html=True)
                        for ins in s["key_insights"]:
                            st.markdown(f'<div style="font-size:0.78rem;color:var(--text-mid);padding:4px 0;">• {ins}</div>', unsafe_allow_html=True)

                    is_open = st.session_state.show_full_analysis_by_type.get(dtype)
                    btn_label = "📖 Hide Full Analysis" if is_open else "📖 View Full Analysis"
                    if st.button(btn_label, key=f"fa_btn_{dtype}", use_container_width=True):
                        if is_open:
                            st.session_state.show_full_analysis_by_type[dtype] = False
                        else:
                            doc_id = st.session_state.doc_ids.get(dtype)
                            if st.session_state.full_analysis_by_type.get(dtype):
                                st.session_state.show_full_analysis_by_type[dtype] = True
                            else:
                                with st.spinner("Running full analysis..."):
                                    try:
                                        r2 = requests.post(f"{BACKEND_URL}/api/analyze/full",
                                                            json={"document_id": doc_id}, timeout=120)
                                        r2.raise_for_status()
                                        resp_json = r2.json()
                                        if isinstance(resp_json, dict) and resp_json.get("error"):
                                            detail = resp_json.get("detail") or str(resp_json.get("raw", ""))[:300]
                                            st.session_state.full_analysis_error_by_type[dtype] = f"{resp_json['error']}: {detail}"
                                            st.session_state.show_full_analysis_by_type[dtype] = False
                                        else:
                                            st.session_state.full_analysis_by_type[dtype] = resp_json
                                            st.session_state.show_full_analysis_by_type[dtype] = True
                                            st.session_state.full_analysis_error_by_type[dtype] = None
                                    except Exception as e:
                                        st.session_state.full_analysis_error_by_type[dtype] = backend_err(e)
                        st.rerun()
                    if st.session_state.full_analysis_error_by_type.get(dtype):
                        st.error(f"Full analysis failed: {st.session_state.full_analysis_error_by_type[dtype]}")

            for dtype in ("annual_report", "balance_sheet"):
                if not st.session_state.show_full_analysis_by_type.get(dtype):
                    continue
                fa = st.session_state.full_analysis_by_type.get(dtype) or {}
                st.markdown(f'<div class="card-header" style="border-radius:10px;margin-top:14px;">📊 Full Analysis — {dtype.replace("_"," ").title()}</div>', unsafe_allow_html=True)
                sc, fc = st.columns(2)
                with sc:
                    st.markdown('<div class="card"><div class="card-body"><div class="section-title" style="font-weight:700;margin-bottom:8px;">✅ Strengths</div>', unsafe_allow_html=True)
                    for item in (fa.get("strengths") or []):
                        st.markdown(f'<div style="font-size:0.8rem;color:var(--text-mid);padding:4px 0;">• {item}</div>', unsafe_allow_html=True)
                    if not fa.get("strengths"):
                        st.markdown('<div class="empty-state">No specific strengths identified in the source text.</div>', unsafe_allow_html=True)
                    st.markdown('</div></div>', unsafe_allow_html=True)
                with fc:
                    st.markdown('<div class="card"><div class="card-body"><div class="section-title" style="font-weight:700;margin-bottom:8px;">🚩 Red Flags</div>', unsafe_allow_html=True)
                    for item in (fa.get("red_flags") or []):
                        st.markdown(f'<div style="font-size:0.8rem;color:var(--text-mid);padding:4px 0;">• {item}</div>', unsafe_allow_html=True)
                    if not fa.get("red_flags"):
                        st.markdown('<div class="empty-state">No red flags identified in the source text.</div>', unsafe_allow_html=True)
                    st.markdown('</div></div>', unsafe_allow_html=True)

    if not analysis_done:
        st.markdown("""
        <div class="empty-state" style="padding:40px 20px;margin-top:8px;">
          <div style="font-size:1.6rem;margin-bottom:8px;">📊</div>
          <div style="font-weight:700;color:var(--text-mid);">Enter company details above and click "Analyze Company"</div>
          <div style="font-size:0.78rem;margin-top:4px;">Financials, market data, and AI insights will appear here.</div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  LEGAL PAGE
# ══════════════════════════════════════════════════════════════════════════
RISK_BAND_META = {
    "low":      ("🛡️", "risk-low", "#16a34a", "LOW"),
    "moderate": ("🛡️", "risk-moderate", "#d97706", "MODERATE"),
    "high":     ("🛡️", "risk-high", "#dc2626", "HIGH"),
}
BAR_GRADIENTS = {
    "low": "linear-gradient(90deg,#16a34a,#22c55e)",
    "moderate": "linear-gradient(90deg,#d97706,#f59e0b)",
    "high": "linear-gradient(90deg,#dc2626,#f59e0b)",
}


def render_legal():
    company_input, _website_unused, _nse_unused, run_search = render_input_card(
        "⚖️ Run Legal Analysis", "run_legal_btn"
    )
    days_back = st.session_state.legal_days_back

    if company_input:
        st.session_state.active_company_name = company_input

    should_auto_run = (
        company_input
        and (st.session_state.legal_result is None or st.session_state.legal_company != company_input)
    )

    if (run_search or should_auto_run) and company_input:
        with st.spinner("Scanning news and court records..."):
            try:
                r = requests.post(
                    f"{BACKEND_URL}/api/legal/summary",
                    json={"company_name": company_input, "days_back": days_back, "max_court_pages": 2},
                    timeout=60,
                )
                r.raise_for_status()
                st.session_state.legal_result = r.json()
                st.session_state.legal_company = company_input
            except Exception as e:
                st.error(backend_err(e))

    st.markdown(f"""
    <div class="section-header">
      <div class="section-header-left">
        <div class="section-icon">⚖️</div>
        <div>
          <div class="section-title">Legal Risk Intelligence</div>
          <div class="section-sub">Monitor litigation, regulatory exposure and adverse legal signals</div>
        </div>
      </div>
      <div class="updated-block">
        <div>Last updated</div>
        <div class="updated-time">{datetime.now().strftime("%d %b %Y, %I:%M %p")}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    result = st.session_state.legal_result
    if not result:
        st.markdown('<div class="card"><div class="card-body"><div class="empty-state">Enter a company name above '
                    'and click "Run Legal Analysis" to scan for litigation and regulatory signals.</div></div></div>',
                    unsafe_allow_html=True)
        return

    kpis = result.get("kpis", {})
    dist = result.get("signal_distribution", {})
    score = result.get("legal_risk_score", 0)
    band = result.get("risk_band", "low")
    band_icon, band_class, band_hex, band_label = RISK_BAND_META.get(band, RISK_BAND_META["low"])

    # ── legal-kpi-row ──
    lk1, lk2, lk3, lk4, lk5 = st.columns([1.3, 1, 1, 1, 1.2])
    with lk1:
        st.markdown(f"""
        <div class="legal-kpi-card">
          <div class="kpi-top"><div class="kpi-icon orange">🛡️</div><div class="kpi-label">LEGAL RISK SCORE</div></div>
          <div class="legal-kpi-value {band_class}">{band_label}</div>
          <div class="kpi-sub">{score} / 100</div>
          <div class="risk-bar-track"><div class="risk-bar-fill" style="width:{score}%;background:{BAR_GRADIENTS.get(band)};"></div></div>
        </div>""", unsafe_allow_html=True)
    with lk2:
        st.markdown(f"""
        <div class="legal-kpi-card">
          <div class="kpi-top"><div class="kpi-icon blue">🏛️</div><div class="kpi-label">COURT CASES</div></div>
          <div class="legal-kpi-value">{kpis.get('court_records', 0)}</div>
          <div class="kpi-sub">Found on Indian Kanoon</div>
        </div>""", unsafe_allow_html=True)
    with lk3:
        st.markdown(f"""
        <div class="legal-kpi-card">
          <div class="kpi-top"><div class="kpi-icon purple">🗞️</div><div class="kpi-label">ADVERSE NEWS</div></div>
          <div class="legal-kpi-value">{kpis.get('adverse_news_total', 0)}</div>
          <div class="kpi-sub">{kpis.get('relevant_signals', 0)} Relevant Signal(s)</div>
        </div>""", unsafe_allow_html=True)
    with lk4:
        cf = kpis.get('critical_flags', 0)
        st.markdown(f"""
        <div class="legal-kpi-card">
          <div class="kpi-top"><div class="kpi-icon red">🚩</div><div class="kpi-label">CRITICAL FLAGS</div></div>
          <div class="legal-kpi-value {'risk-high' if cf else ''}">{cf}</div>
          <div class="kpi-sub">{'Requires Attention' if cf else 'No Material Flags'}</div>
        </div>""", unsafe_allow_html=True)
    with lk5:
        period_start = (datetime.now() - timedelta(days=days_back)).strftime("%d %b %Y")
        period_end = datetime.now().strftime("%d %b %Y")
        st.markdown(f"""
        <div class="legal-kpi-card">
          <div class="kpi-top"><div class="kpi-icon teal">📅</div><div class="kpi-label">MONITORING PERIOD</div></div>
          <div class="legal-kpi-value" style="font-size:17px;">Last {days_back} Days</div>
          <div class="kpi-sub">{period_start} – {period_end}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div style="padding-top:14px;"></div>', unsafe_allow_html=True)

    articles = result.get("articles", [])
    cases = result.get("cases", [])
    relevant_articles = [a for a in articles if a.get("relevance") == "relevant"]
    low_conf_articles = [a for a in articles if a.get("relevance") == "low_confidence"]

    tr1, tr2 = st.columns([3, 1])
    with tr1:
        st.markdown(f'<div class="tab-note">Lookback window — currently <strong>{days_back} days</strong>. Change it and re-run the analysis above.</div>', unsafe_allow_html=True)
    with tr2:
        st.session_state.legal_days_back = st.selectbox(
            "Lookback", [90, 180, 365, 730],
            index=[90, 180, 365, 730].index(days_back) if days_back in (90, 180, 365, 730) else 2,
            format_func=lambda d: f"Last {d} Days", label_visibility="collapsed", key="legal_lookback_select",
        )

    feed_tabs = st.tabs([
        f"All ({len(articles) + len(cases)})",
        f"Relevant ({len(relevant_articles)})",
        f"Low Confidence ({len(low_conf_articles)})",
        f"Court Cases ({len(cases)})",
    ])

    def _risk_badge_for_article(a):
        if a.get("relevance") == "low_confidence":
            return '<span class="badge news">LOW CONFIDENCE</span>'
        rl = a.get("risk_level", "low")
        cls, label = {"high": ("high", "HIGH RISK"), "medium": ("moderate", "MODERATE RISK"), "low": ("low", "LOW RISK")}[rl]
        return f'<span class="badge {cls}">{label}</span>'

    def _render_article_card(a, idx_key):
        atype, icon, badge_label, badge_class = _article_type(a)
        match_pct = a.get("company_match_pct", 0)
        desc = a.get("description") or ("Potentially material legal signal involving the assessed company."
                                         if a.get("relevance") != "low_confidence"
                                         else "This result shares a name fragment with the company but likely refers to a different entity.")
        st.markdown(f"""
        <div class="case-card">
          <div class="case-icon {badge_class}">{icon}</div>
          <div class="case-content">
            <div class="case-title-row">
              <div class="case-title">{a.get('title','—')}</div>
              <span class="badge {badge_class}">{badge_label}</span>
              {_risk_badge_for_article(a)}
            </div>
            <div class="case-meta">{a.get('source') or '—'} &nbsp;•&nbsp; {a.get('published_at') or '—'}</div>
            <div class="case-desc">{desc}</div>
          </div>
          <div class="case-right">
            <div class="match-pct">{match_pct}% Match</div>
          </div>
        </div>
        """, unsafe_allow_html=True)
        if a.get("url"):
            st.link_button("View Source ↗", a["url"], key=f"art_src_{idx_key}")

    def _render_case_card(c, idx_key):
        st.markdown(f"""
        <div class="case-card">
          <div class="case-icon court">🏛️</div>
          <div class="case-content">
            <div class="case-title-row">
              <div class="case-title">{c.get('title','—')}</div>
              <span class="badge court-case">COURT CASE</span>
            </div>
            <div class="case-meta">{c.get('court') or 'Court not specified'} &nbsp;•&nbsp; {c.get('date') or 'Date unknown'}</div>
            <div class="case-desc">{c.get('snippet') or ''}</div>
          </div>
          <div class="case-right"></div>
        </div>
        """, unsafe_allow_html=True)
        if c.get("url"):
            st.link_button("View Source ↗", c["url"], key=f"case_src_{idx_key}")

    with feed_tabs[0]:
        if not articles and not cases:
            st.markdown('<div class="empty-state">No legal-relevant news or court records found in this period.</div>', unsafe_allow_html=True)
        for i, a in enumerate(articles):
            _render_article_card(a, f"all_a_{i}")
        for i, c in enumerate(cases):
            _render_case_card(c, f"all_c_{i}")
    with feed_tabs[1]:
        if not relevant_articles:
            st.markdown('<div class="empty-state">No high-confidence company matches found.</div>', unsafe_allow_html=True)
        for i, a in enumerate(relevant_articles):
            _render_article_card(a, f"rel_{i}")
    with feed_tabs[2]:
        if not low_conf_articles:
            st.markdown('<div class="empty-state">No low-confidence mentions found.</div>', unsafe_allow_html=True)
        else:
            st.caption("These results share a name fragment with the company but the surrounding text suggests "
                       "they likely refer to a different, similarly-named entity.")
        for i, a in enumerate(low_conf_articles):
            _render_article_card(a, f"low_{i}")
    with feed_tabs[3]:
        if not cases:
            st.markdown('<div class="empty-state">No court records found on Indian Kanoon for this company.</div>', unsafe_allow_html=True)
        for i, c in enumerate(cases):
            _render_case_card(c, f"court_{i}")

    st.caption("Best-effort from public news search + Indian Kanoon — not a substitute for an official "
              "NCLT/NCLAT filing search or a paid credit bureau report. Company-match confidence is heuristic, "
              "not a legal determination — always verify via \"View Source\" before acting.")

    # ── Sidebar equivalents, rendered below the feed on the Streamlit layout ──
    sb1, sb2, sb3 = st.columns(3, gap="medium")

    with sb1:
        st.markdown('<div class="side-card"><div class="card-title-row"><div class="card-title">'
                    '<span class="bar-accent"></span>Signal Timeline</div></div>', unsafe_allow_html=True)
        buckets = {}
        for a in relevant_articles:
            d = _parse_any_date(a.get("published_at"))
            if d:
                buckets[d.strftime("%b %Y")] = buckets.get(d.strftime("%b %Y"), 0) + 1
        for c in cases:
            d = _parse_any_date(c.get("date"))
            if d:
                buckets[d.strftime("%b %Y")] = buckets.get(d.strftime("%b %Y"), 0) + 1
        if len(buckets) >= 2:
            ordered = sorted(buckets.items(), key=lambda kv: datetime.strptime(kv[0], "%b %Y"))
            xs = [k for k, _ in ordered]
            ys = [v for _, v in ordered]
            fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines+markers",
                                        line=dict(color="#dc2626", width=2), fill="tozeroy",
                                        fillcolor="rgba(220,38,38,0.12)"))
            fig.update_layout(height=180, margin=dict(l=0, r=0, t=6, b=0),
                               plot_bgcolor="white", paper_bgcolor="white",
                               xaxis=dict(showgrid=False, tickfont=dict(size=9, color="#8b8fa3")),
                               yaxis=dict(showgrid=True, gridcolor="#f1f2f6", tickfont=dict(size=9, color="#8b8fa3")))
            st.plotly_chart(fig, use_container_width=True, key="legal_timeline_chart")
        else:
            st.markdown('<div class="empty-state">Not enough dated signals in this period to chart a timeline.</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with sb2:
        st.markdown('<div class="side-card"><div class="card-title-row"><div class="card-title">'
                    '<span class="bar-accent"></span>Signal Distribution</div></div>', unsafe_allow_html=True)
        labels = ["High Risk", "Moderate Risk", "Low Risk", "Court Records"]
        values = [dist.get("high", 0), dist.get("moderate", 0), dist.get("low", 0), dist.get("court_records", 0)]
        colors = ["#dc2626", "#d97706", "#16a34a", "#4f39f6"]
        total = dist.get("total", 0)
        if total == 0:
            st.markdown('<div class="empty-state">No signals to chart yet.</div>', unsafe_allow_html=True)
        else:
            donut = go.Figure(go.Pie(labels=labels, values=values, hole=0.62,
                                      marker=dict(colors=colors), textinfo="none"))
            donut.update_layout(height=170, margin=dict(l=0, r=0, t=0, b=0), showlegend=False,
                                 annotations=[dict(text=str(total), x=0.5, y=0.55, font_size=22, showarrow=False),
                                              dict(text="Total", x=0.5, y=0.38, font_size=11, showarrow=False, font_color="#8b8fa3")])
            st.plotly_chart(donut, use_container_width=True, key="legal_donut_chart")
            legend_html = ""
            for label, val, color in zip(labels, values, colors):
                pct = round((val / total) * 100) if total else 0
                legend_html += (f'<div class="legend-item"><div class="legend-left">'
                                 f'<span class="legend-dot" style="background:{color};"></span>{label}</div>'
                                 f'<div class="legend-val">{val} ({pct}%)</div></div>')
            st.markdown(f'<div class="legend-list">{legend_html}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with sb3:
        st.markdown('<div class="side-card"><div class="card-title-row"><div class="card-title">'
                    '<span class="bar-accent"></span>Top Legal Signals</div></div>', unsafe_allow_html=True)
        kw_counts = {}
        for a in relevant_articles:
            for kw in (a.get("matched_keywords") or []):
                kw_counts[kw] = kw_counts.get(kw, 0) + 1
        top_kws = sorted(kw_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
        if not top_kws:
            st.markdown('<div class="empty-state">No recurring legal keywords found in the matched articles.</div>', unsafe_allow_html=True)
        else:
            items_html = ""
            for kw, cnt in top_kws:
                cls, lbl = ("high", "HIGH") if cnt >= 3 else (("moderate", "MODERATE") if cnt >= 2 else ("low", "LOW"))
                items_html += (f'<div class="risk-area-item"><span class="risk-area-name">{kw.title()}</span>'
                                f'<span class="badge {cls}">{lbl}</span></div>')
            st.markdown(f'<div class="risk-area-list">{items_html}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Download report card ──
    st.markdown('<div style="padding-top:16px;"></div>', unsafe_allow_html=True)
    dl1, dl2 = st.columns([2.3, 1])
    with dl2:
        report_lines = [
            f"# Legal Risk Report — {result.get('company')}",
            f"Generated {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
            "",
            f"**Legal Risk Score:** {score}/100 ({band_label})",
            f"**Court Records:** {kpis.get('court_records', 0)}",
            f"**Adverse News (total / relevant):** {kpis.get('adverse_news_total', 0)} / {kpis.get('relevant_signals', 0)}",
            f"**Critical Flags:** {kpis.get('critical_flags', 0)}",
            "",
            "## Key Findings",
        ]
        for f in result.get("key_findings", []):
            report_lines.append(f"- **{f['title']}** — {f['body']}")
        report_lines.append("\n## Court Cases")
        for c in cases:
            report_lines.append(f"- {c.get('title')} ({c.get('court') or 'Court n/a'}, {c.get('date') or 'date n/a'}) — {c.get('url')}")
        report_lines.append("\n## Relevant News")
        for a in relevant_articles:
            report_lines.append(f"- {a.get('title')} ({a.get('source')}, {a.get('published_at')}) — {a.get('url')}")
        report_text = "\n".join(report_lines)

        st.markdown('<div class="side-card download-card">'
                    '<div class="download-title">Need more details?</div>'
                    '<div class="download-sub">Download the full legal report for in-depth analysis.</div>',
                    unsafe_allow_html=True)
        st.download_button("⬇️ Download Report", data=report_text,
                            file_name=f"legal_report_{(result.get('company') or 'company').replace(' ', '_')}.md",
                            mime="text/markdown", use_container_width=True, key="legal_report_dl")
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Diagnostics (kept for debugging source scrapes -- not in the mockup
    # but genuinely useful and already wired to real backend debug info) ──
    debug = result.get("debug", {})
    ik_debug = debug.get("court_records", {})
    news_debug = debug.get("news", {})
    with st.expander("🔧 Diagnostics — source status"):
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("**Indian Kanoon (court records)**")
            if ik_debug.get("error"):
                st.error(f"Scrape failed: {ik_debug['error']}")
            elif ik_debug.get("http_status") is None:
                st.warning("No request was recorded for this source.")
            else:
                st.success(f"HTTP {ik_debug.get('http_status')} · {ik_debug.get('html_bytes', 0):,} bytes · "
                          f"{ik_debug.get('pages_fetched', 0)} page(s) fetched")
                if ik_debug.get("note"):
                    st.warning(ik_debug["note"])
                elif cases:
                    st.caption(f"Parsed {len(cases)} case record(s) from the response.")
        with d2:
            st.markdown("**News search**")
            if news_debug:
                st.markdown(
                    f"- Queries used: `{', '.join(news_debug.get('queries_used', []))}`\n"
                    f"- Raw from Google News RSS: **{news_debug.get('raw_from_rss', 0)}**\n"
                    f"- Raw from GNews API: **{news_debug.get('raw_from_gnews_api', 0)}**\n"
                    f"- Kept as relevant: **{news_debug.get('kept_relevant', 0)}**\n"
                    f"- Kept as low-confidence: **{news_debug.get('kept_low_confidence', 0)}**"
                )
            else:
                st.caption("No news debug info returned.")


# ══════════════════════════════════════════════════════════════════════════
#  DECISION PAGE — kept fully functional (the mockup only shows a
#  placeholder here), restyled with the same .card/.verdict-card language
#  used across the rest of the app.
# ══════════════════════════════════════════════════════════════════════════
VERDICT_META = {
    "Low":    ("✅", "var(--green-bg)", "var(--green)", "Low Risk"),
    "Medium": ("⚠️", "var(--orange-bg)", "var(--orange)", "Medium Risk"),
    "High":   ("🚨", "var(--red-bg)", "var(--red)", "High Risk"),
}


def render_decision():
    have_financials = any(st.session_state.summary_by_type.values())
    have_nse = bool(st.session_state.nse)

    st.markdown(f"""
    <div class="card"><div class="card-body">
      <div style="font-size:0.95rem;font-weight:700;color:var(--text-dark);margin-bottom:8px;">🧭 What this uses</div>
      <div style="font-size:0.82rem;color:var(--text-mid);line-height:1.6;">
        Financials: {"✅ available" if have_financials else "❌ not yet — go to the Financials tab and upload/analyze a document"}<br>
        NSE market data: {"✅ available" if have_nse else "❌ not yet — go to the Financials tab and fetch an NSE quote"}
      </div>
    </div></div>
    """, unsafe_allow_html=True)

    run_disabled = not (have_financials or have_nse)
    if st.button("🎯 Run Risk Assessment", type="primary", disabled=run_disabled, use_container_width=False):
        with st.spinner("Running risk model..."):
            try:
                r = requests.post(
                    f"{BACKEND_URL}/api/decision/assess",
                    json={
                        "annual_summary": st.session_state.summary_by_type.get("annual_report"),
                        "balance_summary": st.session_state.summary_by_type.get("balance_sheet"),
                        "annual_full": st.session_state.full_analysis_by_type.get("annual_report"),
                        "balance_full": st.session_state.full_analysis_by_type.get("balance_sheet"),
                        "nse": st.session_state.nse,
                    },
                    timeout=30,
                )
                r.raise_for_status()
                st.session_state.decision_result = r.json()
            except Exception as e:
                st.error(backend_err(e))

    result = st.session_state.get("decision_result")
    if not result:
        st.markdown('<div class="card"><div class="card-body"><div class="empty-state">Run the assessment above once you have '
                    'Financials and/or NSE data loaded.</div></div></div>', unsafe_allow_html=True)
        return

    icon, bg, color, label = VERDICT_META.get(result.get("verdict"), VERDICT_META["Medium"])
    st.markdown(f"""
    <div class="verdict-card" style="background:{bg};">
      <div class="verdict-left">
        <div class="verdict-badge">{icon}</div>
        <div>
          <div class="verdict-title" style="color:{color};">{label}</div>
          <div class="verdict-sub">Data completeness: {int(result.get("data_completeness", 0) * 100)}%</div>
        </div>
      </div>
      <div class="verdict-confidence">Confidence<br><span style="font-size:1.1rem;font-weight:700;color:{color};">{int(result.get("confidence", 0) * 100)}%</span></div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="medium")
    with col1:
        st.markdown('<div class="card"><div class="card-header">📊 Probability Breakdown</div><div class="card-body">', unsafe_allow_html=True)
        prob_colors = {"Low": "#16a34a", "Medium": "#f59e0b", "High": "#dc2626"}
        probs = result.get("probabilities", {})
        for cls in ("Low", "Medium", "High"):
            pct = probs.get(cls, 0) * 100
            st.markdown(f"""
            <div class="prob-row">
              <div class="prob-label">{cls}</div>
              <div class="prob-track"><div class="prob-fill" style="width:{pct}%;background:{prob_colors[cls]};"></div></div>
              <div class="prob-pct">{pct:.0f}%</div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="card"><div class="card-header">🔍 Top Contributing Factors</div><div class="card-body">', unsafe_allow_html=True)
        factors = result.get("top_factors") or []
        if factors:
            for f in factors:
                st.markdown(f'<div class="factor-item"><span>•</span><span>{f}</span></div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="empty-state">No factors could be extracted from the available data.</div>', unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)

    st.markdown(f'<div class="decision-note">ℹ️ {result.get("note", "")}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════
#  ROUTE TO ACTIVE PAGE
# ══════════════════════════════════════════════════════════════════════════
if st.session_state.active_page == "Financials":
    render_financials()
    footer_text = "🛡️ All data is AI-extracted and for informational purposes only."
elif st.session_state.active_page == "Legal":
    render_legal()
    footer_text = ("⚖️ Legal signals are AI-extracted from public news and court search results "
                   "for informational purposes only — always verify with primary sources / legal counsel before acting.")
else:
    render_decision()
    footer_text = ("🧭 This risk verdict comes from a model trained on synthetic, heuristic-derived data — "
                   "treat it as a starting point for review, not a guaranteed prediction.")

st.markdown(f'<div class="footer">{footer_text}</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)  # close .container