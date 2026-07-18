"""
JW Market & News Monitor — full web app (Streamlit), 4-quadrant dashboard.
Reuses desktop data modules unchanged. Dark Bloomberg theme + Plotly.
"""
import os, sys, io
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
for _k in ("FRED_API_KEY", "NEWS_API_KEY"):
    try:
        if _k in st.secrets: os.environ[_k] = str(st.secrets[_k])
    except Exception: pass

# Force-reload data modules so deployed code changes always take effect, even when
# Streamlit reruns the script without restarting the process (avoids stale modules).
import importlib
for _m in ("market_data", "fi_spreads", "factors_data", "yield_curve", "futures_data", "prediction_markets"):
    try:
        importlib.reload(importlib.import_module(_m))
    except Exception:
        pass

# Auto-clear the data cache when the instrument universe changes (e.g. new tabs/
# tickers added) so stale empty/old cached results don't persist after a deploy.
@st.cache_resource
def _ver_holder(): return {"v": None}
try:
    import market_data as _mdv
    _dv = sum(len(getattr(_mdv, _n, {})) for _n in
              ("INDICES","RATES","VOLATILITY","FX","FIXED_INCOME","MUNIS","FACTORS",
               "COMMODITIES","SECTORS","HEDGE_FUNDS","FUNDING","RISK_PREMIA","AQR_FUNDS","CRYPTO"))
    _h=_ver_holder()
    if _h["v"] != _dv:
        st.cache_data.clear(); _h["v"]=_dv
except Exception:
    pass

import pandas as pd
import plotly.graph_objects as go
try:
    from streamlit_searchbox import st_searchbox
    _HAS_SEARCHBOX=True
except Exception:
    _HAS_SEARCHBOX=False

# ── Theme ───────────────────────────────────────────────────────
BG="#0d1117"; SIDEBAR="#161b22"; CARD="#1c2128"; CARD2="#21262d"; BORDER="#30363d"
ACCENT="#f78166"; BLUE="#58a6ff"; GREEN="#3fb950"; RED="#f85149"
YELLOW="#e3b341"; PURPLE="#bc8cff"; CYAN="#79c0ff"
TEXT1="#e6edf3"; TEXT2="#8b949e"; TEXT3="#6e7681"
PALETTE=[ACCENT,BLUE,GREEN,YELLOW,PURPLE,CYAN,"#ff6b6b","#ffa94d"]

st.set_page_config(page_title="JW Market & News Monitor", page_icon="📈",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
  .stApp {{ background:{BG}; color:{TEXT1}; }}
  header[data-testid="stHeader"] {{ background:{BG}; height:0; }}
  #MainMenu, footer {{ visibility:hidden; }}
  .block-container {{ padding:0.6rem 1rem 1rem 1rem; max-width:100%; }}
  h1,h2,h3,h4,h5 {{ color:{TEXT1}; font-family:'Segoe UI',sans-serif; }}
  .topbar {{ display:flex; align-items:center; gap:14px; padding:6px 4px 10px 4px; }}
  .jaws-logo {{ background:{ACCENT}; color:#0d1117; font-weight:800; font-size:22px;
               padding:5px 16px; border-radius:6px; font-family:Consolas,monospace;
               letter-spacing:2px; }}
  .jaws-title {{ color:{TEXT1}; font-family:'Segoe UI',sans-serif; font-size:18px; font-weight:600; }}
  .jaws-sub {{ color:{TEXT2}; font-family:Consolas,monospace; font-size:12px; }}
  table.jaws {{ width:100%; border-collapse:collapse; font-family:Consolas,monospace; font-size:12px; }}
  table.jaws th {{ background:{CARD2}; color:{TEXT2}; text-align:right; padding:6px 8px;
                  border-bottom:1px solid {BORDER}; position:sticky; top:0; z-index:2; }}
  table.jaws th:first-child {{ text-align:left; }}
  table.jaws td {{ padding:5px 8px; border-bottom:1px solid {BORDER}; text-align:right;
                  color:{TEXT1}; white-space:nowrap; }}
  table.jaws td:first-child {{ text-align:left; }}
  table.jaws tr:nth-child(even) td {{ background:{CARD2}; }}
  table.jaws tr:nth-child(odd)  td {{ background:{CARD}; }}
  .jaws-cat {{ background:#161b22; color:{ACCENT}; font-family:Consolas; font-weight:700;
              padding:4px 8px; font-size:11px; }}
  .tbl-wrap {{ max-height:330px; overflow:auto; border:1px solid {BORDER}; border-radius:6px; }}
  /* ── Bigger, easier-to-find scrollbars ── */
  ::-webkit-scrollbar {{ width:16px; height:16px; }}
  ::-webkit-scrollbar-track {{ background:{SIDEBAR}; }}
  ::-webkit-scrollbar-thumb {{ background:#ffffff; border-radius:8px; border:3px solid {SIDEBAR}; }}
  ::-webkit-scrollbar-thumb:hover {{ background:{ACCENT}; }}
  ::-webkit-scrollbar-corner {{ background:{SIDEBAR}; }}
  * {{ scrollbar-width:auto; scrollbar-color:#ffffff {SIDEBAR}; }}
  div[data-testid="stVerticalBlockBorderWrapper"] {{ background:{CARD};
       border:1px solid {BORDER} !important; border-radius:8px; }}
  .stRadio label, .stCheckbox label {{ color:{TEXT1}; }}

  /* ── High-contrast form controls (inputs, selects, dates, searchbox) ── */
  input, textarea {{ color:{TEXT1} !important; }}
  input::placeholder, textarea::placeholder {{ color:{TEXT2} !important; opacity:1; }}
  /* field backgrounds: dark with visible border */
  [data-baseweb="input"], [data-baseweb="base-input"],
  [data-baseweb="select"] > div, [data-baseweb="input"] > div {{
       background:#0b0e13 !important; border:1px solid {BORDER} !important; }}
  /* selected text shown inside selects / searchbox */
  [data-baseweb="select"] div, [data-baseweb="select"] span,
  [data-baseweb="select"] input {{ color:{TEXT1} !important; }}
  /* dropdown / autocomplete option lists */
  [data-baseweb="popover"] li, [data-baseweb="menu"] li,
  [role="option"] {{ color:{TEXT1} !important; background:{CARD2} !important; }}
  [data-baseweb="popover"] li:hover, [role="option"]:hover {{ background:{ACCENT} !important;
       color:#0d1117 !important; }}
  /* field labels */
  label, .stSelectbox label, .stTextInput label, .stDateInput label {{ color:{TEXT1} !important; }}
  /* metrics (regression output) */
  [data-testid="stMetricLabel"] p {{ color:{TEXT2} !important; }}
  [data-testid="stMetricValue"] {{ color:{TEXT1} !important; }}

  /* ── Buttons: red/black theme, high contrast ── */
  .stButton > button, .stDownloadButton > button, [data-testid="stBaseButton-secondary"],
  [data-testid="baseButton-secondary"], button[kind="secondary"] {{
       background:#0d1117 !important; color:{ACCENT} !important;
       border:1.5px solid {ACCENT} !important; font-weight:700 !important; }}
  .stButton > button:hover, .stDownloadButton > button:hover,
  button[kind="secondary"]:hover {{
       background:{ACCENT} !important; color:#0d1117 !important; border-color:{ACCENT} !important; }}
  .stButton > button:active, .stDownloadButton > button:active {{
       background:{RED} !important; color:#0d1117 !important; border-color:{RED} !important; }}
  /* file-uploader browse button */
  [data-testid="stFileUploader"] button {{
       background:#0d1117 !important; color:{ACCENT} !important; border:1.5px solid {ACCENT} !important; }}
  /* dropdown / date fields: subtle accent border for definition */
  [data-baseweb="select"] > div:focus-within, [data-baseweb="input"]:focus-within {{
       border:1.5px solid {ACCENT} !important; }}
</style>
""", unsafe_allow_html=True)

# ── Auth ────────────────────────────────────────────────────────
def _bg_data_uri():
    """Build a 'cool finance' SVG background (skyline + grid + rising charts)."""
    import urllib.parse
    W,H=1440,760; n=12
    p=[f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>"]
    p.append("<rect width='100%' height='100%' fill='#0a0e15'/>")
    g="<g stroke='#13202d' stroke-width='1'>"
    for x in range(0,W+1,60): g+=f"<line x1='{x}' y1='0' x2='{x}' y2='{H}'/>"
    for y in range(0,H+1,48): g+=f"<line x1='0' y1='{y}' x2='{W}' y2='{y}'/>"
    p.append(g+"</g>")
    # skyline
    heights=[150,250,190,300,210,340,170,260,320,200,280,230,360,180,250,310,160,270,330,210,300,190]
    bw=W//len(heights); b="<g fill='#0f1923'>"
    for i,h in enumerate(heights):
        bx=i*bw; b+=f"<rect x='{bx}' y='{H-h}' width='{bw-7}' height='{h}'/>"
        for wy in range(H-h+14, H-12, 26):
            for wx in range(bx+8, bx+bw-14, 18):
                if (wx*7+wy)%5==0:
                    b+=f"<rect x='{wx}' y='{wy}' width='6' height='9' fill='#1f6feb' opacity='0.45'/>"
    p.append(b+"</g>")
    ys =[0.66,0.74,0.6,0.7,0.54,0.64,0.48,0.58,0.42,0.52,0.36,0.30]
    ys2=[0.74,0.7,0.76,0.64,0.68,0.58,0.63,0.52,0.57,0.47,0.52,0.44]
    poly =" ".join(f"{int(i*W/(n-1))},{int(v*H)}" for i,v in enumerate(ys))
    poly2=" ".join(f"{int(i*W/(n-1))},{int(v*H)}" for i,v in enumerate(ys2))
    p.append(f"<polyline points='0,{H} {poly} {W},{H}' fill='#3fb950' opacity='0.07'/>")
    p.append(f"<polyline points='{poly}' fill='none' stroke='#3fb950' stroke-width='3' opacity='0.85'/>")
    p.append(f"<polyline points='{poly2}' fill='none' stroke='#58a6ff' stroke-width='2' opacity='0.6'/>")
    p.append("</svg>")
    return "data:image/svg+xml,"+urllib.parse.quote("".join(p))

def _auth():
    try:    pw = st.secrets.get("app_password", "jaws2026")
    except Exception: pw = "jaws2026"
    if st.session_state.get("auth_ok"): return True
    uri=_bg_data_uri()
    st.markdown(f"""<style>
      .stApp {{ background:
          linear-gradient(rgba(7,10,16,0.62), rgba(7,10,16,0.88)),
          url("{uri}") center/cover no-repeat fixed !important; }}
      [data-testid="stTextInput"] {{ max-width:520px; margin:0 auto; }}
    </style>""", unsafe_allow_html=True)
    st.markdown("<div style='height:11vh'></div>", unsafe_allow_html=True)
    c=st.columns([1,2,1])
    with c[1]:
        st.markdown(
            "<div style='text-align:center;'>"
            f"<span class='jaws-logo' style='font-size:46px; padding:12px 34px;'>JAWS</span>"
            f"<div style='color:{TEXT1}; font-size:26px; font-weight:600; margin-top:18px;'>"
            "JW Market &amp; News Monitor</div>"
            f"<div style='color:{TEXT2}; font-family:Consolas; font-size:13px; margin-top:4px;'>"
            "market &amp; macro intelligence</div></div>", unsafe_allow_html=True)
        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        e = st.text_input("Enter access password", type="password")
        if e:
            if e == pw: st.session_state["auth_ok"]=True; st.rerun()
            else: st.error("Incorrect password")
    return False
if not _auth(): st.stop()

try:
    from streamlit_autorefresh import st_autorefresh
    _HAS_AUTOREFRESH=True
except Exception:
    _HAS_AUTOREFRESH=False

# ── Formatting ──────────────────────────────────────────────────
def f_pct(v):
    if v is None: return f'<span style="color:{TEXT3}">—</span>'
    c=GREEN if v>=0 else RED
    return f'<span style="color:{c}">{"+" if v>=0 else ""}{v:.2f}%</span>'
def f_abs(v):
    if v is None: return f'<span style="color:{TEXT3}">—</span>'
    c=GREEN if v>=0 else RED
    return f'<span style="color:{c}">{"+" if v>=0 else ""}{v:.2f}</span>'
def f_price(v,name=""):
    if v is None: return "—"
    if any(x in name for x in ["EUR/","GBP/","AUD/","JPY","CNY","MXN","CAD","CHF"]): return f"{v:,.4f}"
    if v<10: return f"{v:.4f}"
    if v<1000: return f"{v:,.2f}"
    return f"{v:,.0f}"
def z_color(z):
    if z is None: return TEXT2
    if z>2: return RED
    if z>1: return YELLOW
    if z<-1: return GREEN
    return TEXT2

# ── Cached loaders ──────────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def md_returns(key, custom_start=None, custom_end=None, absolute=False):
    import market_data as md
    dmap={"indices":md.INDICES,"volatility":md.VOLATILITY,"fx":md.FX,
          "fixed_income":md.FIXED_INCOME,"munis":md.MUNIS,"factors":md.FACTORS,
          "commodities":md.COMMODITIES,"sectors":md.SECTORS,
          "hedge_funds":getattr(md,"HEDGE_FUNDS",{}),
          "risk_premia":getattr(md,"RISK_PREMIA",{}),
          "aqr":getattr(md,"AQR_FUNDS",{}),
          "crypto":getattr(md,"CRYPTO",{})}
    cs=pd.Timestamp(custom_start).date() if custom_start else None
    ce=pd.Timestamp(custom_end).date() if custom_end else None
    try:
        data=md.fetch_returns(dmap[key], custom_start=cs, custom_end=ce, absolute=absolute)
    except TypeError:   # resilience if an older market_data is still in memory
        data=md.fetch_returns(dmap[key], custom_start=cs, absolute=absolute)
    return data, dmap[key]

@st.cache_data(ttl=900, show_spinner=False)
def _md_history_remote(sym, start=None, adjusted=True):
    import market_data as md
    try:
        return md.price_history(sym, start=start, adjusted=adjusted)
    except TypeError:   # resilience if an older market_data is still in memory
        return md.price_history(sym, start=start)

# ── Persistent watchlist (survives refresh / re-login) ─────────────
import json as _json
_WL_FILE=os.path.join(os.path.dirname(os.path.abspath(__file__)), "_watchlist.json")
def watchlist_store():
    """{SYMBOL: name} — persisted to disk so it stays until explicitly removed."""
    if "wl_store" not in st.session_state:
        d={}
        try:
            with open(_WL_FILE,"r",encoding="utf-8") as f:
                d={x["sym"]:x["name"] for x in _json.load(f)}
        except Exception:
            d={}
        st.session_state["wl_store"]=d
    return st.session_state["wl_store"]
def watchlist_save():
    try:
        with open(_WL_FILE,"w",encoding="utf-8") as f:
            _json.dump([{"sym":s,"name":n} for s,n in watchlist_store().items()], f)
    except Exception:
        pass

# ── User-uploaded custom time series (session-scoped) ──────────────
def custom_store():
    """{SYMBOL: {'name':str,'prices':pd.Series}} — user-uploaded series as price levels."""
    return st.session_state.setdefault("cust", {})
def custom_labels():
    """{display_label: SYMBOL} for pickers/search."""
    return {f"{v['name']} [{s}]": s for s,v in custom_store().items()}

# ── Academic L/S factors as searchable pseudo-instruments ──────────
@st.cache_data(ttl=3600, show_spinner=False)
def factor_price_store():
    """{PSEUDO_SYM: {'name':label,'prices':price Series}} — every L/S academic
    factor (Ken French + AQR, incl. Betting-Against-Beta) as a growth-of-100 index
    so it can be charted/correlated/regressed like any other instrument."""
    out={}
    try:
        data=factor_data()
    except Exception:
        return out
    for sect in ("daily","monthly"):
        for r in data.get(sect,[]):
            if r.get("error") or not r.get("raw_dates"): continue
            prod=1.0; idx=[]
            for x in r["raw_rets"]:
                prod*=(1.0+x); idx.append(prod*100.0)
            s=pd.Series(idx, index=pd.to_datetime(r["raw_dates"])).sort_index()
            s=s[~s.index.duplicated(keep="last")]
            tag="D" if r["is_daily"] else "M"
            out[f"FAC:{r['name']}:{tag}"]={"name":f"{r['name']} ({tag})","prices":s}
    return out
def factor_labels():
    """{display_label: PSEUDO_SYM} for pickers/search."""
    return {f"{v['name']} [factor]": s for s,v in factor_price_store().items()}

# ── FRED macro series (yields/spreads/funding/inflation) as instruments ──
@st.cache_data(ttl=1800, show_spinner=False)
def macro_price_store():
    """{PSEUDO_SYM: {'name':label,'prices':level Series}} — every FRED level series
    shown on the Spreads/Rates/Funding/Inflation tabs, exposed as a plottable
    instrument so it can be charted/scanned anywhere. Pseudo-symbols start 'FRED:'."""
    out={}
    try:
        cat=tool_series_catalog()
    except Exception:
        return out
    for label,(kind,payload) in cat.items():
        if kind!="level": continue          # factors handled by factor_price_store
        ds,vs=payload
        s=pd.Series(vs, index=pd.to_datetime(ds)).sort_index()
        s=s[~s.index.duplicated(keep="last")]
        out[f"FRED:{label}"]={"name":label,"prices":s}
    return out
def macro_labels():
    """{display_label: PSEUDO_SYM} for pickers/search."""
    return {f"{v['name']} [macro]": s for s,v in macro_price_store().items()}

def md_history(sym, start=None, adjusted=True):
    """Price history. User-uploaded customs and academic factors take precedence
    over remote (yfinance) sources."""
    cs=custom_store()
    if sym in cs:
        s=cs[sym]["prices"]
        if start is not None:
            s=s[s.index>=pd.Timestamp(start)]
        return s.copy()
    fp=factor_price_store()
    if sym in fp:
        s=fp[sym]["prices"]
        if start is not None:
            s=s[s.index>=pd.Timestamp(start)]
        return s.copy()
    if isinstance(sym,str) and sym.startswith("FRED:"):
        mp=macro_price_store()
        if sym in mp:
            s=mp[sym]["prices"]
            if start is not None:
                s=s[s.index>=pd.Timestamp(start)]
            return s.copy()
    return _md_history_remote(sym, start=start, adjusted=adjusted)

def parse_uploaded_series(file, kind):
    """Parse an uploaded CSV/XLSX of time series into {SYMBOL:(name, price Series)}.
    Wide format: first column = dates, each remaining column = one identifier.
    kind: 'Prices' (use as-is) or 'Returns %' / 'Returns (decimal)' (compound to a price index=100)."""
    name=file.name.lower()
    if name.endswith((".xlsx",".xls")):
        raw=pd.read_excel(file)
    else:
        raw=pd.read_csv(file)
    if raw.shape[1]<2:
        raise ValueError("Need a date column plus at least one data column.")
    raw=raw.rename(columns={raw.columns[0]:"Date"})
    raw["Date"]=pd.to_datetime(raw["Date"], errors="coerce")
    raw=raw.dropna(subset=["Date"]).set_index("Date").sort_index()
    out={}
    for col in raw.columns:
        ser=pd.to_numeric(raw[col], errors="coerce").dropna()
        if ser.empty: continue
        sym=str(col).strip().upper()
        if kind=="Prices":
            px=ser
        else:
            r=ser/100.0 if kind=="Returns %" else ser
            px=(1.0+r).cumprod()*100.0
        out[sym]=(str(col).strip(), px)
    if not out:
        raise ValueError("No numeric data columns found.")
    return out

def build_upload_template():
    """Return (bytes) an .xlsx template showing the expected upload layout:
    column 1 = dates, each subsequent column = one identifier."""
    import io as _io
    ex_dates=pd.date_range(end=date.today(), periods=6, freq="ME")
    df=pd.DataFrame({
        "Date":[d.strftime("%Y-%m-%d") for d in ex_dates],
        "MY_FUND":[100.0,101.2,99.8,103.5,104.1,106.0],
        "BENCHMARK":[100.0,100.6,100.1,101.9,102.4,103.0],
    })
    buf=_io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as xw:
        df.to_excel(xw, index=False, sheet_name="Data", startrow=0)
        wb=xw.book; ws=xw.sheets["Data"]
        hdr=wb.add_format({"bold":True,"bg_color":"#1f2730","font_color":"#ffffff","border":1})
        for ci,col in enumerate(df.columns):
            ws.write(0, ci, col, hdr); ws.set_column(ci, ci, 16)
        notes=wb.add_worksheet("How to use")
        for i,line in enumerate([
            "JAWS — custom data upload template",
            "",
            "1. Put DATES in the first column (any clear date format, e.g. 2024-01-31).",
            "2. Each additional column = one instrument. The COLUMN HEADER becomes its",
            "   ticker/identifier (e.g. MY_FUND, BENCHMARK). Add as many columns as you like.",
            "3. Fill values down each column. They can be PRICES/levels or RETURNS —",
            "   pick the matching option ('Values are…') when you upload.",
            "4. Returns are auto-compounded to a base-100 index so every tool works.",
            "5. Save as .xlsx or .csv, then use 'Add to dashboard'.",
            "",
            "Replace the example columns on the 'Data' sheet with your own.",
        ]):
            notes.write(i, 0, line)
    return buf.getvalue()

@st.cache_data(ttl=900, show_spinner=False)
def all_tickers():
    import market_data as md
    d={}
    for dd in (md.INDICES,md.RATES,md.VOLATILITY,md.FX,md.FIXED_INCOME,md.MUNIS,
               md.FACTORS,md.FUNDING,md.COMMODITIES,md.SECTORS,
               getattr(md,"HEDGE_FUNDS",{}),getattr(md,"RISK_PREMIA",{}),
               getattr(md,"AQR_FUNDS",{}),getattr(md,"CRYPTO",{})): d.update(dd)
    return d

def search_instruments(term):
    """Type-ahead search: local tool instruments first, then live Yahoo results.
    Returns [(label, symbol), ...] for streamlit-searchbox."""
    if not term or not term.strip(): return []
    _n=lambda x:(x or "").lower().replace("-"," ")   # hyphen/space-insensitive match
    t=_n(term.strip()); seen=set(); out=[]
    for lbl,sym in custom_labels().items():        # user uploads first
        if t in _n(lbl) or t in _n(sym):
            if sym not in seen: out.append((lbl, sym)); seen.add(sym)
    for lbl,sym in factor_labels().items():        # academic L/S factors
        if t in _n(lbl) or t in _n(sym):
            if sym not in seen: out.append((lbl, sym)); seen.add(sym)
    for lbl,sym in macro_labels().items():         # FRED yields/spreads/funding/inflation
        if t in _n(lbl) or t in _n(sym):
            if sym not in seen: out.append((lbl, sym)); seen.add(sym)
    for name,sym in all_tickers().items():
        if t in _n(name) or t in _n(sym):
            if sym not in seen: out.append((f"{name}  [{sym}]", sym)); seen.add(sym)
    if len(t)>=2:                      # remote search once 2+ chars typed
        for sym,name in yf_search(term.strip()):
            if sym and sym not in seen: out.append((f"{name} ({sym})", sym)); seen.add(sym)
    return out[:12]

@st.cache_data(ttl=3600, show_spinner=False)
def resolve_ticker(sym):
    """Return (name, last_price) for a ticker, or (None,None) if not recognized."""
    import yfinance as yf
    name=None; price=None
    try: price=float(yf.Ticker(sym).fast_info.last_price)
    except Exception: price=None
    try:
        for qq in yf.Search(sym, max_results=4).quotes:
            if qq.get("symbol","").upper()==sym.upper():
                name=qq.get("shortname") or qq.get("longname"); break
    except Exception: pass
    return name, price

@st.cache_data(ttl=3600, show_spinner=False)
def fred_title(sid):
    """Return the FRED series title, or None if not found."""
    import urllib.request, json
    key=os.environ.get("FRED_API_KEY","")
    if not key: return None
    try:
        url=f"https://api.stlouisfed.org/fred/series?series_id={sid}&file_type=json&api_key={key}"
        with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"JAWS"}),timeout=8) as r:
            import json as _j; d=_j.loads(r.read())
        return d["seriess"][0]["title"]
    except Exception: return None

@st.cache_data(ttl=3600, show_spinner=False)
def yf_search(q):
    import yfinance as yf
    try:
        return [(h.get("symbol"), h.get("shortname") or h.get("longname") or h.get("symbol"))
                for h in yf.Search(q, max_results=8).quotes if h.get("symbol")]
    except Exception: return []

@st.cache_data(ttl=1800, show_spinner=False)
def spreads_analytics(): import fi_spreads; return fi_spreads.fetch_spread_analytics()
@st.cache_data(ttl=1800, show_spinner=False)
def rates_analytics():   import fi_spreads; return fi_spreads.fetch_rates_analytics()
@st.cache_data(ttl=1800, show_spinner=False)
def funding_analytics(): import fi_spreads; return fi_spreads.fetch_funding_analytics()
@st.cache_data(ttl=1800, show_spinner=False)
def inflation_analytics(): import fi_spreads; return fi_spreads.fetch_inflation_analytics()
@st.cache_data(ttl=1800, show_spinner=False)
def vix_term(): import futures_data as fx; return fx.fetch_vix_term_structure()
@st.cache_data(ttl=1800, show_spinner=False)
def vix_hist(sym): import futures_data as fx; return fx.fetch_vix_history(sym)
@st.cache_data(ttl=3600, show_spinner=False)
def commodity_curves(products, n): import futures_data as fx; return fx.fetch_commodity_curves(products, n)
@st.cache_data(ttl=1800, show_spinner=False)
def rate_path(): import futures_data as fx; return fx.fetch_rate_expectation_path()
@st.cache_data(ttl=3600, show_spinner=False)
def zq_strip_auto(): import futures_data as fx; return fx.fetch_zq_strip()
@st.cache_data(ttl=900, show_spinner=False)
def prediction_markets_data(sources, topics):
    import prediction_markets as pmkt
    return pmkt.fetch_prediction_markets(list(sources), list(topics))

@st.cache_data(ttl=3600, show_spinner=False)
def trailing_div_yield(etf):
    """Trailing-12m dividend yield (fraction) of an index ETF, or None."""
    import yfinance as yf
    try:
        h=yf.Ticker(etf).history(period="1y", auto_adjust=False)
        if h.empty or "Dividends" not in h.columns: return None
        px=float(h["Close"].iloc[-1]); d12=float(h["Dividends"].sum())
        return d12/px if px>0 else None
    except Exception:
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def etf_top_holdings(sym):
    """Top holdings [(ticker,name,weight_frac)] for an ETF via issuer daily file, or None."""
    import yfinance as yf
    try:
        th=yf.Ticker(sym).get_funds_data().top_holdings
        if th is None or th.empty: return None
        return [(str(i), str(r["Name"]), float(r["Holding Percent"])) for i,r in th.iterrows()]
    except Exception:
        return None

@st.cache_data(ttl=1800, show_spinner=False)
def option_skew(sym, dte_target):
    """Implied-vol skew for an optionable ticker from the yfinance chain nearest dte_target.
    Returns the OTM smile (moneyness → IV%) plus risk-reversal metrics, or None."""
    import yfinance as yf, datetime as _dt
    try:
        tk=yf.Ticker(sym); exps=list(tk.options or [])
        if not exps: return None
        tgt=_dt.date.today()+_dt.timedelta(days=int(dte_target))
        exp=min(exps, key=lambda e: abs((_dt.date.fromisoformat(e)-tgt).days))
        oc=tk.option_chain(exp)
        h=tk.history(period="1d")
        if h.empty: return None
        spot=float(h["Close"].iloc[-1])
    except Exception:
        return None
    def clean(df):
        df=df.dropna(subset=["impliedVolatility"]).copy()
        df=df[(df["impliedVolatility"]>0.01)&(df["impliedVolatility"]<3.0)]
        return df[(df["strike"]>spot*0.6)&(df["strike"]<spot*1.5)]
    calls=clean(oc.calls); puts=clean(oc.puts)
    if calls.empty or puts.empty: return None
    def iv_at(df, mny):
        if df.empty: return None
        k=spot*mny; i=int((df["strike"]-k).abs().values.argmin())
        return float(df["impliedVolatility"].iloc[i])*100
    both=pd.concat([calls,puts])
    atm=iv_at(both,1.0)
    ivp90=iv_at(puts,0.90); ivc110=iv_at(calls,1.10)
    ivp95=iv_at(puts,0.95); ivc105=iv_at(calls,1.05)
    rr =(ivp90-ivc110) if (ivp90 is not None and ivc110 is not None) else None
    rr5=(ivp95-ivc105) if (ivp95 is not None and ivc105 is not None) else None
    otm_p=puts[puts["strike"]<=spot]; otm_c=calls[calls["strike"]>=spot]
    curve=pd.concat([otm_p[["strike","impliedVolatility"]], otm_c[["strike","impliedVolatility"]]]).sort_values("strike")
    return {"expiry":exp, "dte":(_dt.date.fromisoformat(exp)-_dt.date.today()).days, "spot":spot,
            "atm":atm, "ivp90":ivp90,"ivc110":ivc110,"rr":rr,"ivp95":ivp95,"ivc105":ivc105,"rr5":rr5,
            "m":[float(s)/spot*100 for s in curve["strike"]],
            "iv":[float(v)*100 for v in curve["impliedVolatility"]]}
@st.cache_data(ttl=3600, show_spinner=False)
def factor_data(cs=None, ce=None):
    import factors_data as fd; return fd.fetch_factors(custom_start=cs, custom_end=ce)
@st.cache_data(ttl=3600, show_spinner=False)
def news_data():
    from categorized_news import fetch_all_news_categorized
    return fetch_all_news_categorized()

# Top finance/markets RSS sources (Reuters RSS is dead → omitted)
_MKT_FEEDS={
    "Bloomberg":      "https://feeds.bloomberg.com/markets/news.rss",
    "WSJ Markets":    "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "Financial Times":"https://www.ft.com/rss/home",
    "New York Times": "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "CNBC":           "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "MarketWatch":    "http://feeds.marketwatch.com/marketwatch/topstories/",
    "Yahoo Finance":  "https://finance.yahoo.com/news/rssindex",
    "The Economist":  "https://www.economist.com/finance-and-economics/rss.xml",
    "Guardian":       "https://www.theguardian.com/uk/business/rss",
}
def _entry_ts(e):
    """UTC epoch seconds from a feedparser entry's normalized time, or None."""
    import calendar
    pp=e.get("published_parsed") or e.get("updated_parsed")
    if pp:
        try: return calendar.timegm(pp)
        except Exception: return None
    return None

@st.cache_data(ttl=900, show_spinner=False)
def markets_news():
    """Top markets/finance stories from major outlets (RSS) + NewsAPI business.
    Each item carries a UTC 'ts' (epoch) so dates can be filtered/normalized."""
    import feedparser, time as _t
    out=[]; seen=set(); now=_t.time()
    for src,url in _MKT_FEEDS.items():
        try:
            f=feedparser.parse(url)
            for e in f.entries[:10]:
                title=(e.get("title") or "").strip()
                if not title or title.lower() in seen: continue
                ts=_entry_ts(e)
                if ts and ts>now+6*3600: ts=now   # clamp obviously-future timestamps
                seen.add(title.lower())
                out.append({"source":src,"title":title,"url":e.get("link",""),"ts":ts})
        except Exception: pass
    key=os.environ.get("NEWS_API_KEY","")
    if key:
        try:
            import urllib.request, json
            from datetime import datetime
            url=("https://newsapi.org/v2/top-headlines?category=business&language=en"
                 f"&pageSize=40&apiKey={key}")
            req=urllib.request.Request(url, headers={"User-Agent":"JAWS/1.0"})
            with urllib.request.urlopen(req, timeout=6) as r:
                arts=json.loads(r.read()).get("articles",[])
            for a in arts:
                title=(a.get("title") or "").strip()
                if not title or title.lower() in seen: continue
                seen.add(title.lower())
                ts=None
                try: ts=datetime.fromisoformat((a.get("publishedAt") or "").replace("Z","+00:00")).timestamp()
                except Exception: pass
                out.append({"source":(a.get("source") or {}).get("name","NewsAPI"),
                            "title":title,"url":a.get("url",""),"ts":ts})
        except Exception: pass
    return out

def _fmt_age(ts, now):
    """Human, timezone-safe relative date label."""
    if not ts: return ""
    import datetime as _dt
    d=now-ts
    if d<0: d=0
    if d<3600:   return "just now" if d<300 else f"{int(d//60)}m ago"
    if d<86400:  return f"{int(d//3600)}h ago"
    if d<2*86400:return "Yesterday"
    return _dt.datetime.utcfromtimestamp(ts).strftime("%b %d")

# Credit curve by rating (latest effective yield from FRED)
@st.cache_data(ttl=1800, show_spinner=False)
def credit_curve():
    import fi_spreads as fs
    series=[("AAA","BAMLC0A1CAAAEY"),("AA","BAMLC0A2CAAEY"),("A","BAMLC0A3CAEY"),
            ("BBB","BAMLC0A4CBBBEY"),("BB","BAMLH0A1HYBBEY"),("B","BAMLH0A2HYBEY"),
            ("CCC","BAMLH0A3HYCEY")]
    out=[]
    for lbl,sid in series:
        try:
            d,v=fs._fred_fetch_all(sid)
            if d: out.append((lbl,float(v[-1])))
        except Exception: pass
    return out

NEWS_WEIGHT={"bloomberg":10,"wsj":9,"wall street journal":9,"financial times":9,"ft":9,
             "new york times":8,"nyt":8,"reuters":8,"economist":8,"cnbc":7,
             "marketwatch":6,"yahoo finance":6,"guardian":5,"seeking alpha":5,"zero hedge":4}
_SRC_COLORS={"bloomberg":"#f78166","wsj":"#58a6ff","wall street journal":"#58a6ff",
             "financial times":"#bc8cff","ft":"#bc8cff","new york times":"#79c0ff","nyt":"#79c0ff",
             "cnbc":"#3fb950","economist":"#ff6b6b","marketwatch":"#e3b341",
             "yahoo":"#ffa94d","guardian":"#51cf66"}
def _src_color(src):
    s=(src or "").lower()
    for k,v in _SRC_COLORS.items():
        if k in s: return v
    return CYAN
CAT_LABELS={"hedge_fund":"HF","ipo":"IPO","ma":"M&A","issuance":"ISS"}
CAT_COLORS={"hedge_fund":CYAN,"ipo":GREEN,"ma":YELLOW,"issuance":PURPLE}

def xlsx_bytes(df, sheet="Data"):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter",
                        datetime_format="mm/dd/yyyy", date_format="mm/dd/yyyy") as w:
        df.to_excel(w, index=False, sheet_name=sheet[:31])
    return buf.getvalue()

def export_series_xlsx(df, returns_mode):
    """Bulk-export writer: MM/DD/YYYY dates; return columns as true Excel % cells."""
    import xlsxwriter
    buf=io.BytesIO()
    wb=xlsxwriter.Workbook(buf, {"nan_inf_to_errors": True})
    ws=wb.add_worksheet("Data")
    datef=wb.add_format({"num_format":"mm/dd/yyyy"})
    pctf =wb.add_format({"num_format":"0.00%"})
    numf =wb.add_format({"num_format":"#,##0.0000"})
    cols=list(df.columns)
    for c,nm in enumerate(cols): ws.write(0,c,nm)
    ws.set_column(0,0,12); ws.set_column(1,len(cols)-1,14)
    for r,(_,row) in enumerate(df.iterrows()):
        for c,nm in enumerate(cols):
            val=row[nm]
            if nm=="Date":
                ws.write_datetime(r+1,c, pd.Timestamp(val).to_pydatetime(), datef)
            elif pd.isna(val):
                ws.write_blank(r+1,c,None)
            elif returns_mode:
                ws.write_number(r+1,c, float(val)/100.0, pctf)   # 2.34 → 0.0234 → shows 2.34%
            else:
                ws.write_number(r+1,c, float(val), numf)
    wb.close(); return buf.getvalue()
def dl(df, label, fname, key):
    st.download_button("⬇ "+label, data=xlsx_bytes(df), file_name=fname, key=key,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def base_layout(fig, title, ysuffix="", h=330):
    # Title sits in its own band at the very top (left-aligned, bright white);
    # legend drops below the plot so the two never overlap (esp. on mobile).
    fig.update_layout(template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=CARD,
        height=h, margin=dict(l=48,r=16,t=64,b=70),
        title=dict(text=title, x=0.0, xanchor="left", xref="paper",
                   y=0.97, yanchor="top", yref="container",
                   font=dict(size=15, color="#ffffff"), pad=dict(l=6,t=4)),
        # Toolbar (zoom/reset/autoscale) stacked vertically at the far right on a solid
        # backdrop, so it stays available without covering the left-aligned title.
        modebar=dict(orientation="v", bgcolor="rgba(13,17,23,0.85)",
                     color=TEXT2, activecolor=ACCENT),
        font=dict(family="Consolas",color=TEXT1,size=11), showlegend=True,
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0.0, xanchor="left",
                    bgcolor="rgba(28,33,40,0.92)", bordercolor=ACCENT, borderwidth=1,
                    font=dict(size=11, color=TEXT1)))
    fig.update_xaxes(gridcolor=BORDER, color=TEXT1)
    fig.update_yaxes(gridcolor=BORDER, ticksuffix=ysuffix, color=TEXT1)
    return fig

def add_stat_bands(fig, y, color, label, show_avg, show_sd,
                   avg_tag="avg", up_tag="+2σ", dn_tag="-2σ"):
    """Overlay independently-toggled mean and ±2σ horizontal bands for a series.
    show_avg / show_sd are separate booleans so each can be turned on alone."""
    if not (show_avg or show_sd): return
    try:
        v=pd.Series(y).dropna()
        if len(v)<2: return
        mu=float(v.mean()); sd=float(v.std())
    except Exception:
        return
    if show_avg:
        fig.add_hline(y=mu, line=dict(color=color,dash="dot",width=1),
                      annotation_text=f"{label} {avg_tag}", annotation_font_size=9)
    if show_sd:
        for yv,tag in [(mu+2*sd,up_tag),(mu-2*sd,dn_tag)]:
            fig.add_hline(y=yv, line=dict(color=color,dash="dash",width=1),
                          annotation_text=f"{label} {tag}", annotation_font_size=9)

def add_today_marker(fig, series, color=None):
    """Highlight the latest point with a large white dot (colored ring) so 'today' pops."""
    try:
        s=pd.Series(series).dropna()
        if s.empty: return
        fig.add_trace(go.Scatter(x=[s.index[-1]], y=[float(s.iloc[-1])], mode="markers",
            marker=dict(size=11, color="#ffffff", line=dict(color=color or ACCENT, width=2)),
            showlegend=False, hoverinfo="skip"))
    except Exception:
        pass

def yaxis_range_controls(k, host=None):
    """Optional custom axes: Y min/max, Y tick step, and an X-axis tick increment
    (any number + Days/Months/Years). Returns (ymin, ymax, ystep, xdtick) or None."""
    host = host if host is not None else st
    if not host.checkbox("Custom axes", value=False, key=k+"_yon",
                          help="Override the auto Y-axis (min/max + tick step) and/or set the "
                               "x-axis tick increment. Leave blank for auto."):
        return None
    cc = host.columns(3)
    ymin = cc[0].number_input("Y min", value=None, step=1.0, key=k+"_ymn", placeholder="auto")
    ymax = cc[1].number_input("Y max", value=None, step=1.0, key=k+"_ymx", placeholder="auto")
    step = cc[2].number_input("Y tick step", value=None, step=1.0, key=k+"_ystp", placeholder="auto")
    xc = host.columns([1,1])
    xn = xc[0].number_input("X tick every", value=None, min_value=1, step=1, key=k+"_xn", placeholder="auto")
    xu = xc[1].selectbox("unit", ["Months","Years","Days"], key=k+"_xu")
    step = step if (step is not None and step > 0) else None
    xdt = None
    if xn is not None and xn > 0:
        xn = int(xn)
        xdt = f"M{xn}" if xu=="Months" else (f"M{xn*12}" if xu=="Years" else xn*86400000)
    has_range = ymin is not None and ymax is not None and ymax > ymin
    if not has_range and step is None and xdt is None:
        return None
    return (ymin if has_range else None, ymax if has_range else None, step, xdt)

def apply_yrange(fig, spec):
    """Apply a (ymin,ymax,ystep,xdtick) axis spec to a figure, or leave auto if None."""
    if not spec:
        return
    ymin, ymax, step, xdt = spec
    if ymin is not None and ymax is not None:
        fig.update_yaxes(range=[ymin, ymax], autorange=False)
    if step:
        fig.update_yaxes(dtick=step)
    if xdt:
        fig.update_xaxes(dtick=xdt)

def date_window(k, cutoff, years_default=5, host=None):
    """Explicit start/stop for a time-series chart. A 'Custom date range' checkbox reveals
    From/To pickers that OVERRIDE the panel's preset lookback (`cutoff`). Returns (lo, hi)
    timestamps to filter on. Additive — leaves existing preset controls untouched."""
    host = host if host is not None else st
    hi = pd.Timestamp(date.today())
    if host.checkbox("Custom date range", value=False, key=k+"_dro"):
        c1,c2 = host.columns(2)
        lo = c1.date_input("From", value=(cutoff.date() if cutoff is not None
                           else date.today()-relativedelta(years=years_default)),
                           min_value=date(1900,1,1), key=k+"_from")
        hi_d = c2.date_input("To", value=date.today(), key=k+"_to")
        return pd.Timestamp(lo), pd.Timestamp(hi_d)
    return (cutoff if cutoff is not None else pd.Timestamp(date.today()-relativedelta(years=years_default))), hi

# ── Valuation data ──────────────────────────────────────────────
VAL_INDEX_ETFS={"S&P 500 (SPY)":"SPY","Nasdaq 100 (QQQ)":"QQQ","Russell 2000 (IWM)":"IWM",
    "Dow (DIA)":"DIA","S&P MidCap (MDY)":"MDY","EAFE (EFA)":"EFA","EM (EEM)":"EEM",
    "Tech (XLK)":"XLK","Financials (XLF)":"XLF","Energy (XLE)":"XLE","Health (XLV)":"XLV",
    "Cons Disc (XLY)":"XLY","Cons Stpl (XLP)":"XLP"}
MULTPL={"Trailing P/E":"https://www.multpl.com/s-p-500-pe-ratio/table/by-month",
    "Shiller CAPE":"https://www.multpl.com/shiller-pe/table/by-month",
    "Price / Book":"https://www.multpl.com/s-p-500-price-to-book/table/by-quarter",
    "Price / Sales":"https://www.multpl.com/s-p-500-price-to-sales/table/by-quarter"}

@st.cache_data(ttl=3600, show_spinner=False)
def yf_multiples(sym):
    import yfinance as yf
    tk=yf.Ticker(sym)
    try: i=tk.info
    except Exception: i={}
    mc=i.get("marketCap")
    fwd_ps=None; eps_gr=None
    # Forward metrics we build ourselves from consensus estimates (stocks only)
    if mc:
        try:
            re=tk.revenue_estimate
            if re is not None and "+1y" in re.index:
                rev=re.loc["+1y","avg"]
                if rev and rev>0: fwd_ps=mc/rev
        except Exception: pass
    fe=i.get("forwardEps"); te=i.get("trailingEps")
    if fe and te and te>0: eps_gr=(fe/te-1)*100
    return {"FwdPE":i.get("forwardPE"),"PE":i.get("trailingPE"),"PB":i.get("priceToBook"),
            "PS":i.get("priceToSalesTrailing12Months"),"FwdPS":fwd_ps,
            "EVEBITDA":i.get("enterpriseToEbitda"),"PEG":i.get("pegRatio"),
            "EPSgr":eps_gr,"DivYld":i.get("dividendYield")}

@st.cache_data(ttl=86400, show_spinner=False)
def multpl_series(url):
    import urllib.request, re
    req=urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
    html=urllib.request.urlopen(req,timeout=20).read().decode("utf-8","replace")
    rows=re.findall(r'<td>\s*([A-Z][a-z]{2} \d{1,2}, \d{4})\s*</td>\s*<td>.*?([\d]+\.[\d]+|[\d]+)\s*</td>',
                    html, re.DOTALL)
    out=[]
    for d,v in rows:
        try: out.append((datetime.strptime(d,"%b %d, %Y").date(), float(v)))
        except Exception: pass
    out.sort(); return out

# ════════════════════════════════════════════════════════════════
# PANEL RENDERERS  (each takes a unique key prefix `k`)
# ════════════════════════════════════════════════════════════════
RET_HDR=["Name","Tkr","Price","1D%","MTD%","YTD%","1Y%","3Y%","5Y%","10Y%","Custom%"]

def panel_returns(catkey, label, k):
    absolute = catkey in ("rates","funding")
    cs = st.session_state.get(k+"_cs")
    ce = st.session_state.get(k+"_ce")
    with st.spinner(f"Loading {label}…"):
        data,tmap = md_returns(catkey, custom_start=cs.isoformat() if cs else None,
                               custom_end=ce.isoformat() if ce else None, absolute=absolute)
    fc=f_abs if absolute else f_pct
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in RET_HDR)+"</tr>"
    for name,info in data.items():
        r=info.get("returns",{})
        h+=("<tr>"f"<td>{name}</td><td style='color:{TEXT3}'>{tmap.get(name,'')}</td>"
            f"<td>{f_price(info.get('price'),name)}</td><td>{fc(info.get('change_1d'))}</td>"
            f"<td>{fc(r.get('MTD'))}</td><td>{fc(r.get('YTD'))}</td><td>{fc(r.get('1Y'))}</td>"
            f"<td>{fc(r.get('3Y'))}</td><td>{fc(r.get('5Y'))}</td><td>{fc(r.get('10Y'))}</td>"
            f"<td>{fc(r.get('Custom'))}</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    c1,c2,c3=st.columns([1,1,1])
    c1.date_input("Custom start", value=cs, key=k+"_cs", min_value=date(1900,1,1))
    c2.date_input("Custom end", value=ce, key=k+"_ce", min_value=date(1900,1,1))
    df=pd.DataFrame([{"Name":n,"Ticker":tmap.get(n,""),"Price":i.get("price"),
        **{p:i.get("returns",{}).get(p) for p in ["MTD","YTD","1Y","3Y","5Y","10Y","Custom"]}}
        for n,i in data.items()])
    with c3: dl(df, "Export", f"JAWS_{catkey}.xlsx", k+"_dl")

ANA_HDR=["Name","Unit","Cur","Δ1M","Δ3M","Δ1Y","Δ3Y","Δ5Y","Δ10Y","Min","Max","Z","Since"]
def panel_analytics(loader, label, fname, k):
    with st.spinner("Loading from FRED…"):
        rows=loader()
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in ANA_HDR)+"</tr>"
    cats={}
    for r in rows: cats.setdefault(r.get("category",""),[]).append(r)
    for cat,crows in cats.items():
        h+=f'<tr><td class="jaws-cat" colspan="{len(ANA_HDR)}">{cat}</td></tr>'
        for r in crows:
            if r.get("error"): continue
            dec=r.get("decimals",0); cur=r.get("current")
            def fn(v): return f'<span style="color:{TEXT3}">—</span>' if v is None else f"{v:.{dec}f}"
            def chg(v):                        # change from that period to now (current − then)
                if v is None or cur is None: return f'<span style="color:{TEXT3}">—</span>'
                d=cur-v; cc=RED if d>0 else (GREEN if d<0 else TEXT2)
                return f'<span style="color:{cc}">{d:+.{dec}f}</span>'
            z=r.get("z_score"); hh=r.get("hist",{}); zc=z_color(z)
            zt=f'{z:+.2f}σ' if z is not None else "—"
            rd=r.get("raw_dates") or []; since=(str(rd[0])[:4] if rd else "—")
            h+=("<tr>"f"<td>{r['name']}</td><td style='color:{TEXT3}'>{r.get('unit','')}</td>"
                f"<td style='color:{zc}'>{fn(cur)}</td><td>{chg(hh.get('1M'))}</td>"
                f"<td>{chg(hh.get('3M'))}</td><td>{chg(hh.get('1Y'))}</td><td>{chg(hh.get('3Y'))}</td>"
                f"<td>{chg(hh.get('5Y'))}</td><td>{chg(hh.get('10Y'))}</td>"
                f"<td style='color:{GREEN}'>{fn(r.get('all_min'))}</td>"
                f"<td style='color:{RED}'>{fn(r.get('all_max'))}</td><td style='color:{zc}'>{zt}</td>"
                f"<td style='color:{TEXT3}'>{since}</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    st.caption("**Cur** = latest level. **Δ** columns = change from that period ago to now "
               "(current − level then; red = higher now, green = lower). **Min / Max / Z-score** span each "
               "series' full available history — back to its **Since** year (shown in the last column).")
    valid=[r for r in rows if not r.get("error") and r.get("raw_dates")]
    c1,c2=st.columns([2,1])
    pick=c1.selectbox("History", [r["name"] for r in valid], key=k+"_pick", label_visibility="collapsed")
    df=pd.DataFrame([{"Name":r["name"],"Category":r.get("category"),"Current":r.get("current"),
        **{p:r.get("hist",{}).get(p) for p in ["1M","3M","1Y","3Y","5Y","10Y"]},
        "Min":r.get("all_min"),"Max":r.get("all_max"),"Z":r.get("z_score")} for r in valid])
    with c2: dl(df, "Export", fname, k+"_dl")
    if pick:
        r=next(x for x in valid if x["name"]==pick)
        fig=go.Figure(); ds,vs=r["raw_dates"],r["raw_values"]
        if ds:
            mean=sum(vs)/len(vs)
            fig.add_trace(go.Scatter(x=ds,y=vs,mode="lines",line=dict(color=ACCENT,width=1.6)))
            fig.add_hline(y=mean,line=dict(color=TEXT3,dash="dash"))
        st.plotly_chart(base_layout(fig,f"{pick} ({r.get('unit','')})",h=300),
                        use_container_width=True, key=k+"_chart")

def panel_factors(k):
    c1,c2=st.columns(2)
    cstart=c1.date_input("Custom start", value=None, key=k+"_cs", min_value=date(1926,1,1))
    cend=c2.date_input("Custom end", value=None, key=k+"_ce")
    with st.spinner("Downloading factor data…"):
        fdata=factor_data(cstart, cend)
    # No 1D/1W: academic factors (Ken French/AQR) publish on a ~1-month lag, so a
    # "1-day" move here is the last available factor day, NOT yesterday — misleading
    # as a live snapshot. Shortest meaningful window starts at MTD.
    keys=["MTD","1M","QTD","3M","YTD","1Y","3Y","5Y","7Y","10Y","Custom"]
    FCOLS=["Factor"]+keys
    # As-of date per section (latest underlying observation)
    asof={}
    for sect in ("daily","monthly"):
        ds=[r["raw_dates"][-1] for r in fdata.get(sect,[]) if r.get("raw_dates")]
        if ds: asof[sect]=max(ds)
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in FCOLS)+"</tr>"
    for sect,lbl in [("daily","DAILY (Ken French US)"),("monthly","MONTHLY (US/Dev/EM + AQR)")]:
        tag=f"  ·  as of {asof[sect]}" if asof.get(sect) else ""
        h+=f'<tr><td class="jaws-cat" colspan="{len(FCOLS)}">{lbl}{tag}</td></tr>'
        for r in fdata.get(sect,[]):
            if r.get("error"): continue
            w=r["windows"]
            h+="<tr><td>"+r["name"]+"</td>"+"".join(f"<td>{f_pct(w.get(x))}</td>" for x in keys)+"</tr>"
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    st.caption("Academic factors update on a lag (Ken French ~monthly); 1-day/1-week columns are "
               "omitted because they would not reflect yesterday's market. See the 'as of' dates above.")
    import factors_data as fd
    allf=[r for s in ("daily","monthly") for r in fdata.get(s,[]) if not r.get("error")]
    names=[r["name"]+(" (D)" if r["is_daily"] else " (M)") for r in allf]
    c1,c2,c3=st.columns([2,1,1])
    idx=c1.selectbox("Factor", range(len(names)), format_func=lambda i:names[i],
                     key=k+"_pick", label_visibility="collapsed")
    yrs=c2.select_slider("Yrs",[1,3,5,7,10,99],value=5,
                         format_func=lambda x:"All" if x==99 else f"{x}Y",key=k+"_yr")
    erows=[]
    for s in ("daily","monthly"):
        for r in fdata.get(s,[]):
            if r.get("error"): continue
            erows.append({"Factor":r["name"],"Section":s,**{x:r["windows"].get(x) for x in keys}})
    with c3: dl(pd.DataFrame(erows), "Export", "JAWS_LS_Factors.xlsx", k+"_dl")
    r=allf[idx]; start=None if yrs==99 else date.today()-relativedelta(years=yrs)
    ds,vs=fd.cumulative_series(r["raw_dates"],r["raw_rets"],start)
    fig=go.Figure()
    if ds:
        col=GREEN if vs[-1]>=0 else RED
        fig.add_trace(go.Scatter(x=ds,y=vs,mode="lines",line=dict(color=col,width=1.6),fill="tozeroy",
            fillcolor="rgba(63,185,80,0.12)" if vs[-1]>=0 else "rgba(248,81,73,0.12)"))
        fig.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
    st.plotly_chart(base_layout(fig,f"{r['name']} — cumulative L/S %","%",h=300),
                    use_container_width=True, key=k+"_chart")

def ticker_picker(k, default_labels):
    """Searchable multi-ticker picker. Returns {label: symbol} for the chosen set.
    Lets the user add ANY ticker (typed) or company name (resolved via Yahoo search)."""
    tmap={**all_tickers(), **factor_labels(), **macro_labels(), **custom_labels()}
    ek=k+"_extra"
    if ek not in st.session_state: st.session_state[ek]={}
    if _HAS_SEARCHBOX:
        sel=st_searchbox(search_instruments, placeholder="Type to search & add any ticker…",
                         key=k+"_sb")
        if sel: st.session_state[ek][sel]=sel
    else:
        sc1,sc2=st.columns([3,1])
        q=sc1.text_input("Search/add", key=k+"_q", label_visibility="collapsed",
                         placeholder="Search any ticker or name, then Add →")
        if sc2.button("Add", key=k+"_add") and q.strip():
            raw=q.strip()
            if len(raw)<=6 and raw.replace("^","").replace("=","").replace(".","").isalnum():
                st.session_state[ek][raw.upper()]=raw.upper()
            else:
                res=yf_search(raw)
                if res: sym,nm=res[0]; st.session_state[ek][f"{nm[:22]} ({sym})"]=sym
    opts=list(tmap.keys())+list(st.session_state[ek].keys())
    full={**tmap, **st.session_state[ek]}
    defs=[d for d in default_labels if d in opts] or opts[:1]
    picks=st.multiselect("Instruments (add multiple to overlay)", opts, default=defs, key=k+"_ms")
    return {p:full.get(p,p) for p in picks}

def panel_chart(k):
    chosen=ticker_picker(k, ["S&P 500"])
    picks=list(chosen.keys()); full=chosen
    c1,c2,c3=st.columns([2,1,1])
    per=c1.select_slider("Period",["MTD","3M","6M","YTD","1Y","3Y","5Y","10Y","20Y","Max","Custom"],
                         value="1Y",key=k+"_per")
    if per=="Custom":
        d1,d2=st.columns(2)
        cstart=d1.date_input("Start", value=date.today()-relativedelta(years=1),
                             min_value=date(1960,1,1), key=k+"_cstart")
        cend=d2.date_input("End", value=date.today(), key=k+"_cend")
    else:
        cstart={"MTD":date.today().replace(day=1),"3M":date.today()-relativedelta(months=3),
                "6M":date.today()-relativedelta(months=6),"YTD":date.today().replace(month=1,day=1),
                "1Y":date.today()-relativedelta(years=1),"3Y":date.today()-relativedelta(years=3),
                "5Y":date.today()-relativedelta(years=5),"10Y":date.today()-relativedelta(years=10),
                "20Y":date.today()-relativedelta(years=20),"Max":date(1900,1,1)}[per]
        cend=date.today()
    single = len(picks)==1
    mode=c2.radio("Type",["Bar","Line"],horizontal=True,key=k+"_mode",disabled=not single)
    dt=c3.radio("Data",["Returns","Price"],horizontal=True,key=k+"_dt",disabled=not single)
    b1,b2=st.columns(2)
    avg_for=b1.multiselect("Show average for", picks, default=[], key=k+"_avg",
                           help="Pick which series get a mean line.")
    sd_for=b2.multiselect("Show ±2σ bands for", picks, default=[], key=k+"_sd",
                          help="Pick which series get ±2σ bands.")
    fig=go.Figure(); exp={}; ends={}
    for i,nm in enumerate(picks):
        sym=full.get(nm,nm)
        c=md_history(sym, start=cstart.strftime("%Y-%m-%d"))
        if c.empty: continue
        c=c[c.index<=pd.Timestamp(cend)]
        if c.empty: continue
        ends[nm]=c.index[-1].date()
        col=PALETTE[i%len(PALETTE)]
        if single and mode=="Bar":
            m=c.resample("ME").last().pct_change().dropna()*100
            fig.add_trace(go.Bar(x=m.index,y=m.values,name=f"{nm} monthly %",
                marker_color=[GREEN if v>=0 else RED for v in m.values],
                text=[f"{v:+.1f}" for v in m.values], textposition="outside",
                textfont=dict(size=9,color=TEXT1), cliponaxis=False))
            exp[nm+" m%"]=m
            add_stat_bands(fig, m.values, ACCENT, nm, nm in avg_for, nm in sd_for)
        elif single and dt=="Price":
            fig.add_trace(go.Scatter(x=c.index,y=c.values,mode="lines",
                line=dict(color=ACCENT,width=2))); exp[nm]=c
            add_stat_bands(fig, c.values, ACCENT, nm, nm in avg_for, nm in sd_for); add_today_marker(fig, c, ACCENT)
        else:
            base=float(c.iloc[0]); r=(c-base)/base*100
            fig.add_trace(go.Scatter(x=c.index,y=r.values,mode="lines",name=f"{nm} ({r.iloc[-1]:+.1f}%)",
                line=dict(color=col,width=1.8))); exp[nm+" %"]=r
            add_stat_bands(fig, r.values, col, nm, nm in avg_for, nm in sd_for); add_today_marker(fig, r, col)
    suffix="%" if not (single and dt=="Price") else ""
    ttl="Comparison · normalized %" if len(picks)>1 else (picks[0] if picks else "Chart")
    yr=yaxis_range_controls(k)
    fig=base_layout(fig,f"{ttl} · {per}",suffix,h=440); apply_yrange(fig,yr)
    st.plotly_chart(fig,use_container_width=True,key=k+"_chart")
    # Flag series whose data ends materially earlier than the most-recent one
    # (e.g. Ken French daily factors publish on a ~monthly lag).
    if len(ends)>1:
        newest=max(ends.values())
        lagging=[f"{nm} (through {d:%b %d})" for nm,d in ends.items() if (newest-d).days>5]
        if lagging:
            st.caption("⏳ Some series update on a lag, so their lines stop earlier: "
                       + "; ".join(lagging) + ". Academic factors (Ken French) refresh ~monthly.")
    if exp:
        df=pd.DataFrame(exp); df.insert(0,"Date",df.index)
        dl(df, "Export chart data", "JAWS_chart.xlsx", k+"_dl")

# Muni bucket → comparable Treasury maturity for the Muni/UST ratio
_MUNI_UST_MAP=[("0-2 Yr","2 Yr"),("2-5 Yr","5 Yr"),("5-10 Yr","10 Yr"),
               ("15-20 Yr","20 Yr"),("20+ Yr","30 Yr")]

@st.cache_data(ttl=1800, show_spinner=False)
def _ust_curve(days=0):
    import yield_curve as yc
    return yc.fetch_curve_for_date(datetime.today()-relativedelta(days=days))
@st.cache_data(ttl=1800, show_spinner=False)
def _muni_curve():
    import yield_curve as yc
    return yc.fetch_muni_curve(datetime.today())

def panel_yield(k):
    import yield_curve as yc
    mode=st.radio("Curve",["Treasury","Municipal","Muni/UST Ratio"],horizontal=True,key=k+"_mode")
    fig=go.Figure()
    if mode=="Treasury":
        opts={"Today":0,"-1M":30,"-3M":91,"-6M":182,"-1Y":365,"-2Y":730,"-3Y":1095}
        picks=st.multiselect("Curves", list(opts.keys()), default=["Today","-1Y"], key=k+"_ms")
        tips=st.checkbox("TIPS real", key=k+"_tips")
        rowsout={}
        for i,p in enumerate(picks):
            try:
                row=_ust_curve(opts[p])
                if not row: continue
                xs=[m for m in yc.MATURITIES if row["yields"].get(m) is not None]
                ys=[row["yields"][m] for m in xs]
                fig.add_trace(go.Scatter(x=xs,y=ys,mode="lines+markers",name=p,
                    line=dict(color=PALETTE[i%len(PALETTE)],width=2)))
                rowsout[p]=dict(zip(xs,ys))
            except Exception: pass
        if tips:
            try:
                t=yc.fetch_tips_curve_for_date(datetime.today())
                if t:
                    xs=[m for m in yc.TIPS_MATURITIES if t["yields"].get(m) is not None]
                    fig.add_trace(go.Scatter(x=xs,y=[t["yields"][m] for m in xs],
                        mode="lines+markers",name="TIPS",line=dict(color=GREEN,dash="dash")))
            except Exception: pass
        st.plotly_chart(base_layout(fig,"US Treasury Yield Curve","%",h=320),use_container_width=True,key=k+"_chart")
        if rowsout: dl(pd.DataFrame(rowsout),"Export","JAWS_yieldcurve.xlsx",k+"_dl")
    elif mode=="Municipal":
        m=_muni_curve()
        if m and any(v is not None for v in m["yields"].values()):
            xs=[b for b in yc.MUNI_MATURITIES if m["yields"].get(b) is not None]
            ys=[m["yields"][b] for b in xs]
            fig.add_trace(go.Scatter(x=xs,y=ys,mode="lines+markers",name="Muni",
                line=dict(color=PURPLE,width=2),marker=dict(size=8)))
            st.plotly_chart(base_layout(fig,"Municipal Yield Curve (ETF proxy)","%",h=320),
                            use_container_width=True,key=k+"_chart")
            dl(pd.DataFrame({"Bucket":xs,"Yield%":ys}),"Export","JAWS_muni.xlsx",k+"_dl")
        else:
            st.info("Muni data unavailable right now (ETF yields).")
    else:  # Muni/UST Ratio
        m=_muni_curve(); ust=_ust_curve(0)
        if m and ust:
            labels,ratios,mu,tr=[],[],[],[]
            for bucket,mat in _MUNI_UST_MAP:
                mv=m["yields"].get(bucket); tv=ust["yields"].get(mat)
                if mv and tv:
                    labels.append(f"{bucket}→{mat}"); ratios.append(round(mv/tv*100,1))
                    mu.append(mv); tr.append(tv)
            if labels:
                cols=[GREEN if r<85 else (RED if r>100 else YELLOW) for r in ratios]
                fig.add_trace(go.Bar(x=labels,y=ratios,marker_color=cols,
                    text=[f"{r:.0f}%" for r in ratios],textposition="outside"))
                fig.add_hline(y=100,line=dict(color=TEXT3,dash="dash"),annotation_text="100% (parity)")
                st.plotly_chart(base_layout(fig,"Muni / Treasury Yield Ratio  (low = munis rich/expensive)","%",h=320),
                                use_container_width=True,key=k+"_chart")
                st.caption("Ratio = tax-exempt muni yield ÷ Treasury yield. Lower = munis richer "
                           "(expensive); higher (→100%+) = munis cheaper vs Treasuries.")
                dl(pd.DataFrame({"Tenor":labels,"Muni%":mu,"UST%":tr,"Ratio%":ratios}),
                   "Export","JAWS_muni_ust_ratio.xlsx",k+"_dl")
            else:
                st.info("Could not align muni/UST tenors right now.")
        else:
            st.info("Muni or Treasury data unavailable right now.")

# Maturity → numeric x (years) for overlaying curves on one axis.
# Short-end points (<1y) thinned to 3M/6M only to reduce bunching/noise near 0.
_MATX={"3 Mo":0.25,"6 Mo":0.5,"1 Yr":1,"2 Yr":2,"3 Yr":3,"5 Yr":5,"7 Yr":7,
       "10 Yr":10,"20 Yr":20,"30 Yr":30}
_MUNI_X={"0-2 Yr":1,"2-5 Yr":3.5,"5-10 Yr":7.5,"10-15 Yr":12.5,"15-20 Yr":17.5,"20+ Yr":25}

def panel_curves(k):
    import yield_curve as yc
    opts=st.multiselect("Curves to show",
        ["Treasury (nominal)","TIPS (real)","Municipal (proxy)","Credit by rating"],
        default=["Treasury (nominal)"], key=k+"_sel")
    hist=st.multiselect("Treasury history overlays", ["-1M","-3M","-6M","-1Y","-2Y","-3Y"],
                        default=["-1M","-3M","-6M","-1Y"], key=k+"_hist")
    fig=go.Figure(); exp={}
    if "Treasury (nominal)" in opts:
        row=_ust_curve(0)
        if row:
            mats=[m for m in yc.MATURITIES if m in _MATX and row["yields"].get(m) is not None]
            xs=[_MATX[m] for m in mats]; ys=[row["yields"][m] for m in mats]
            fig.add_trace(go.Scatter(x=xs,y=ys,mode="lines+markers",name="Today",
                line=dict(color=ACCENT,width=2.6))); exp["Today"]=dict(zip(mats,ys))
        dmap={"-1M":30,"-3M":91,"-6M":182,"-1Y":365,"-2Y":730,"-3Y":1095}
        hcols=[BLUE,GREEN,YELLOW,PURPLE,CYAN,"#ff6b6b"]
        for hi,hlbl in enumerate(hist):
            rh=_ust_curve(dmap[hlbl])
            if rh:
                mats=[m for m in yc.MATURITIES if m in _MATX and rh["yields"].get(m) is not None]
                fig.add_trace(go.Scatter(x=[_MATX[m] for m in mats],
                    y=[rh["yields"][m] for m in mats],mode="lines",name=hlbl,
                    line=dict(color=hcols[hi%len(hcols)],width=1.4,dash="dot")))
    if "TIPS (real)" in opts:
        try:
            t=yc.fetch_tips_curve_for_date(datetime.today())
            if t:
                mats=[m for m in yc.TIPS_MATURITIES if m in _MATX and t["yields"].get(m) is not None]
                xs=[_MATX[m] for m in mats]; ys=[t["yields"][m] for m in mats]
                fig.add_trace(go.Scatter(x=xs,y=ys,mode="lines+markers",name="TIPS (real)",
                    line=dict(color=GREEN,width=2,dash="dash"))); exp["TIPS"]=dict(zip(mats,ys))
        except Exception: pass
    if "Municipal (proxy)" in opts:
        m=_muni_curve()
        if m:
            bks=[b for b in yc.MUNI_MATURITIES if m["yields"].get(b) is not None]
            xs=[_MUNI_X[b] for b in bks]; ys=[m["yields"][b] for b in bks]
            fig.add_trace(go.Scatter(x=xs,y=ys,mode="lines+markers",name="Municipal",
                line=dict(color=PURPLE,width=2))); exp["Muni"]=dict(zip(bks,ys))
    fig.update_xaxes(title="Maturity (yrs)")
    st.plotly_chart(base_layout(fig,"Yield Curves (nominal · real · muni)","%",h=380),
                    use_container_width=True, key=k+"_curve")
    if "Credit by rating" in opts:
        cc=credit_curve()
        if cc:
            labels,ys=zip(*cc)
            cf=go.Figure(go.Scatter(x=list(labels),y=list(ys),mode="lines+markers",
                line=dict(color=BLUE,width=2),marker=dict(size=8)))
            st.plotly_chart(base_layout(cf,"Corporate Yield by Rating (ICE BofA)","%",h=240),
                            use_container_width=True, key=k+"_credit")
            exp["Credit (by rating)"]=dict(zip(labels,ys))
        else:
            st.caption("Credit-by-rating needs the FRED key.")
    if exp:
        rows=[]
        for cname,d in exp.items():
            for mat,v in d.items(): rows.append({"Curve":cname,"Point":mat,"Yield%":v})
        dl(pd.DataFrame(rows), "Export curves", "JAWS_curves.xlsx", k+"_dl")
    st.caption("Foreign sovereign full curves aren't freely available; Treasury/TIPS = US Treasury, "
               "Muni = ETF-proxy, Credit = ICE BofA effective yields.")

# Muni/Treasury ratio: muni ETF (trailing yield) vs Treasury (FRED) by tenor
_MUNI_RATIO={"Short (SHM ~2-3y)":("SHM","DGS2"),
             "Core (MUB ~7y)":("MUB","DGS10"),
             "Long (TFI ~8y)":("TFI","DGS20")}
@st.cache_data(ttl=1800, show_spinner=False)
def muni_ust_ratio_series(muni_etf, tsy_fred):
    import yfinance as yf, fi_spreads as fs
    try:
        tk=yf.Ticker(muni_etf)
        h=tk.history(period="10y", auto_adjust=False)
        if h.empty: return None
        if h.index.tz is not None: h.index=h.index.tz_localize(None)
        px=h["Close"]
        dd=h["Dividends"] if "Dividends" in h.columns else pd.Series(0.0,index=px.index)
        muni=(dd.rolling(252,min_periods=60).sum()/px)*100          # trailing-12m yield %
        d,v=fs._fred_fetch_all(tsy_fred)
        if not d: return None
        tsy=pd.Series(v,index=pd.to_datetime(d)).reindex(px.index, method="ffill")
        return (muni/tsy*100).dropna()
    except Exception:
        return None

def panel_muni_ratio(k):
    tenors=st.multiselect("Tenor (muni ETF ÷ Treasury)", list(_MUNI_RATIO.keys()),
                          default=["Core (MUB ~7y)"], key=k+"_t")
    yrs=st.select_slider("Lookback (years)",[3,5,10,15,20,25],value=10,key=k+"_yr")
    b1,b2=st.columns(2)
    avg_for=b1.multiselect("Show average for", tenors, default=tenors, key=k+"_avg")
    sd_for=b2.multiselect("Show ±2σ bands for", tenors, default=tenors, key=k+"_sd")
    cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs)); lo,hi=date_window(k,cutoff); fig=go.Figure(); exp={}
    for i,t in enumerate(tenors):
        etf,fred=_MUNI_RATIO[t]
        r=muni_ust_ratio_series(etf,fred)
        if r is None or r.empty: continue
        r=r[(r.index>=lo)&(r.index<=hi)]
        if r.empty: continue
        col=PALETTE[i%len(PALETTE)]
        fig.add_trace(go.Scatter(x=r.index,y=r.values,mode="lines",name=t,
            line=dict(color=col,width=1.6))); exp[t]=r
        add_stat_bands(fig, r.values, col, t, t in avg_for, t in sd_for,
                       up_tag="+2σ (cheap)", dn_tag="-2σ (rich)"); add_today_marker(fig, r, col)
    yr=yaxis_range_controls(k); fig=base_layout(fig,"Muni / Treasury yield ratio (%) — ETF proxy","%",h=440); apply_yrange(fig,yr)
    st.plotly_chart(fig, use_container_width=True, key=k+"_chart")
    st.caption("Muni yield = ETF trailing-12m distribution ÷ price; ratio = muni ÷ Treasury yield. "
               "LOW ratio = munis rich/expensive; HIGH (→100%+) = munis cheap vs Treasuries.")
    if exp:
        df=pd.DataFrame(exp); df.insert(0,"Date",df.index)
        dl(df,"Export","JAWS_muni_ust_ratio.xlsx",k+"_dl")

def _is_monthly(s):
    """True if a price series is (at most) ~monthly frequency."""
    if s is None or len(s)<3: return False
    try:
        gap=s.index.to_series().diff().dt.days.median()
    except Exception:
        return False
    return gap is not None and gap>=20

def _resolve_freq(fmode, series_list):
    """Decide whether to compute on a monthly grid. Returns (use_monthly, note)."""
    any_m=any(_is_monthly(s) for s in series_list)
    if fmode=="Monthly":
        return True, ""
    if fmode=="Daily":
        return False, ("⚠ A selected series is monthly-only — daily view will look sparse. "
                       "Switch to Monthly/Auto for an apples-to-apples comparison." if any_m else "")
    if any_m:   # Auto
        return True, "Auto → Monthly: a selected series is monthly-only, so all series are resampled to month-end."
    return False, ""

def panel_rvol(k):
    chosen=ticker_picker(k, ["S&P 500"])
    series={lbl:md_history(sym) for lbl,sym in chosen.items()}
    series={lbl:s for lbl,s in series.items() if s is not None and not s.empty}
    c1,c2,c3=st.columns([1.2,1,1])
    fmode=c1.radio("Frequency",["Auto","Daily","Monthly"],horizontal=True,key=k+"_fm",
                   help="Monthly resamples every series to month-end so daily and "
                        "monthly-only series (e.g. factors) line up apples-to-apples.")
    use_monthly,note=_resolve_freq(fmode, list(series.values()))
    if use_monthly:
        win=int(c2.number_input("Window (months)", min_value=2, max_value=60, value=6, step=1, key=k+"_wm"))
        ann=12**0.5; unit="month"
    else:
        win=int(c2.number_input("Window (days)", min_value=10, max_value=756, value=63, step=1, key=k+"_wd"))
        ann=252**0.5; unit="day"
    yrs=c3.select_slider("Lookback (years)",[1,2,3,5,10,15,20,25],value=5,key=k+"_yr")
    labels=list(series.keys())
    b1,b2=st.columns(2)
    avg_for=b1.multiselect("Show average for", labels, default=labels, key=k+"_avg")
    sd_for=b2.multiselect("Show ±2σ bands for", labels, default=labels, key=k+"_sd")
    cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs)); lo,hi=date_window(k,cutoff); fig=go.Figure(); exp={}
    for i,(label,c) in enumerate(series.items()):
        if use_monthly: c=c.resample("ME").last().dropna()
        rv=(c.pct_change().dropna().rolling(win).std()*ann*100).dropna()
        rv=rv[(rv.index>=lo)&(rv.index<=hi)]
        if rv.empty: continue
        col=PALETTE[i%len(PALETTE)]
        fig.add_trace(go.Scatter(x=rv.index,y=rv.values,mode="lines",name=label,
            line=dict(color=col,width=1.6))); exp[label]=rv
        add_stat_bands(fig, rv.values, col, label, label in avg_for, label in sd_for); add_today_marker(fig, rv, col)
    yr=yaxis_range_controls(k); fig=base_layout(fig,f"Realized Volatility (annualized) · {win}-{unit} rolling","%",h=440); apply_yrange(fig,yr)
    st.plotly_chart(fig, use_container_width=True, key=k+"_chart")
    if note: st.caption(note)
    if exp:
        df=pd.DataFrame(exp); df.insert(0,"Date",df.index)
        dl(df,"Export","JAWS_realizedvol.xlsx",k+"_dl")

_ZPER={"1D":1,"1W":5,"1M":21,"3M":63,"6M":126,"1Y":252}
def panel_scanner(k):
    # ── Universe: flip segments + search/add individual instruments ──
    segs=seg_catalog()
    seg_pick=st.multiselect("Add segments", list(segs.keys()),
                            default=["Equity Indices","US Sectors"], key=k+"_segs")
    if k+"_syms" not in st.session_state: st.session_state[k+"_syms"]=[]
    if _HAS_SEARCHBOX:
        sel=st_searchbox(search_instruments, placeholder="Search & add an instrument…", key=k+"_sb")
        if sel and sel not in st.session_state[k+"_syms"]:
            st.session_state[k+"_syms"].append(sel)
    import re as _re
    paste=st.text_input("…or paste tickers (comma separated)", "", key=k+"_paste")
    pasted=[t.strip() for t in _re.split(r"[,\s]+", paste) if t.strip()]
    if st.button("Clear added", key=k+"_clear"):
        st.session_state[k+"_syms"]=[]; st.rerun()
    items={}
    for sg in seg_pick: items.update(segs[sg])
    for sym in list(dict.fromkeys(st.session_state[k+"_syms"]+pasted)): items[sym]=sym

    c1,c2=st.columns(2)
    yrs=c1.select_slider("Lookback (years)",[1,2,3,5,10,15,20,25],value=10,key=k+"_yr")
    zper=c2.selectbox("Z-score period",list(_ZPER.keys()),index=2,key=k+"_zp")
    w=_ZPER[zper]
    if not items:
        st.info("Add segments or instruments above to scan."); return
    cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs))
    rows=[]
    with st.spinner(f"Scanning {len(items)} instruments…"):
        for name,sym in items.items():
            c=md_history(sym)
            if c.empty: continue
            c=c[c.index>=cutoff]
            if len(c)<w+5: continue
            r=(c.pct_change(w).dropna())*100          # w-period returns over lookback
            if len(r)<5: continue
            cur=float(r.iloc[-1]); mu=float(r.mean()); sd=float(r.std(ddof=1))
            z=(cur-mu)/sd if sd>1e-9 else None
            rows.append({"Instrument":name,"Ticker":sym,"Last":float(c.iloc[-1]),
                         "Ret%":cur,"Avg%":mu,"Z":z})
    rows.sort(key=lambda r:-(abs(r["Z"]) if r["Z"] is not None else 0))
    hdr=["Instrument","Tkr","Last",f"{zper} Ret%",f"{zper} Avg%","Z","σ"]
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
    for r in rows:
        z=r["Z"]; az=abs(z) if z is not None else 0
        zc=RED if az>=2 else (YELLOW if az>=1 else TEXT2); flag=f"{az:+.1f}σ" if az>=1 else ""
        rcl=GREEN if r["Ret%"]>=0 else RED
        h+=(f"<tr><td>{r['Instrument']}</td><td style='color:{TEXT3}'>{r['Ticker']}</td>"
            f"<td>{f_price(r['Last'],r['Instrument'])}</td>"
            f"<td style='color:{rcl}'>{r['Ret%']:+.2f}%</td>"
            f"<td style='color:{TEXT2}'>{r['Avg%']:+.2f}%</td>"
            f"<td style='color:{zc}'>{(f'{z:+.2f}' if z is not None else '—')}</td>"
            f"<td style='color:{zc}'>{flag}</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    st.caption(f"Z = (latest {zper} return − mean {zper} return over {yrs}y) ÷ {yrs}y std. "
               f"Red ≥ |2σ| extreme move vs history = potential dislocation.")
    dl(pd.DataFrame(rows),"Export","JAWS_dislocation_scanner.xlsx",k+"_dl")

def _wl_ret(c, anchor):
    """Total return (%) from price at/just-before anchor date to latest. None if insufficient."""
    if c is None or c.empty: return None
    base=c[c.index<=pd.Timestamp(anchor)]
    if base.empty: return None
    b=float(base.iloc[-1])
    return (float(c.iloc[-1])/b-1)*100 if b else None

def panel_watchlist(k):
    """User-built watchlist — add any instrument via search; renders the standard returns table.
    The list is stored on disk and persists until you remove each item."""
    wl=watchlist_store()
    if _HAS_SEARCHBOX:
        sel=st_searchbox(search_instruments, placeholder="Search & add to watchlist…", key=k+"_sb")
        if sel and sel not in wl:
            wl[sel]=next((n for n,s in {**all_tickers(),**custom_labels()}.items() if s==sel), sel)
            watchlist_save(); st.rerun()
    else:
        sc1,sc2=st.columns([3,1])
        q=sc1.text_input("Add", key=k+"_q", label_visibility="collapsed",
                         placeholder="Type a ticker, then Add →")
        if sc2.button("Add", key=k+"_add") and q.strip():
            s=q.strip().upper(); wl[s]=s; watchlist_save(); st.rerun()
    if not wl:
        st.info("Search above to add instruments to your watchlist. Items stay until you remove them."); return
    today=date.today()
    anchors=[("1D",None),("MTD",today.replace(day=1)-relativedelta(days=1)),
             ("YTD",date(today.year-1,12,31)),("1Y",today-relativedelta(years=1)),
             ("3Y",today-relativedelta(years=3)),("5Y",today-relativedelta(years=5)),
             ("10Y",today-relativedelta(years=10))]
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in RET_HDR[:-1])+"</tr>"
    rows=[]
    with st.spinner("Loading watchlist…"):
        for sym,lbl in wl.items():
            c=md_history(sym)
            if c is None or c.empty:
                h+=(f"<tr><td>{lbl}</td><td style='color:{TEXT3}'>{sym}</td>"
                    f"<td colspan='{len(RET_HDR)-3}' style='color:{TEXT3}'>no data</td></tr>"); continue
            vals={}
            for nm,anc in anchors:
                vals[nm]=(_wl_ret(c, c.index[-2]) if (nm=="1D" and len(c)>=2)
                          else (_wl_ret(c, anc) if anc else None))
            cells="".join(f"<td>{f_pct(vals[nm])}</td>" for nm,_ in anchors)
            h+=(f"<tr><td>{lbl}</td><td style='color:{TEXT3}'>{sym}</td>"
                f"<td>{f_price(float(c.iloc[-1]),lbl)}</td>{cells}</tr>")
            rows.append({"Name":lbl,"Ticker":sym,"Price":float(c.iloc[-1]),
                         **{nm:vals[nm] for nm,_ in anchors}})
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    cc1,cc2=st.columns([3,1])
    rm=cc1.multiselect("Remove from watchlist", list(wl.keys()),
                       format_func=lambda s: f"{wl[s]} [{s}]", key=k+"_rm")
    if cc2.button("Remove selected", key=k+"_rmbtn") and rm:
        for s in rm: wl.pop(s,None)
        watchlist_save(); st.rerun()
    st.caption("Total-return basis (dividends/coupons included). Your watchlist is saved and persists "
               "across sessions until you remove an item.")
    if rows: dl(pd.DataFrame(rows),"Export","JAWS_watchlist.xlsx",k+"_dl2")

def panel_custom(k):
    """Custom tab — manage and preview user-uploaded time series."""
    cs=custom_store()
    if not cs:
        st.info("No custom data yet. Use **⬆ Upload data** next to the logo to add a "
                "spreadsheet of returns or prices. Uploaded series then work in every section "
                "(Chart, Correlation, Regression, Dislocation Scanner, Watchlist, Bulk Export).")
        return
    cc1,cc2=st.columns([3,1])
    rm=cc1.multiselect("Remove series", list(cs.keys()),
                       format_func=lambda s: f"{cs[s]['name']} [{s}]", key=k+"_rm")
    if cc2.button("Remove selected", key=k+"_rmbtn") and rm:
        for s in rm: cs.pop(s,None)
        st.cache_data.clear(); st.rerun()
    # summary table
    hdr=["Identifier","Ticker","Start","End","Points","Last (index)","Total ret%"]
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
    for sym,v in cs.items():
        px=v["prices"]
        tot=(px.iloc[-1]/px.iloc[0]-1)*100 if len(px)>1 else 0.0
        h+=(f"<tr><td>{v['name']}</td><td style='color:{TEXT3}'>{sym}</td>"
            f"<td>{px.index[0].date()}</td><td>{px.index[-1].date()}</td>"
            f"<td>{len(px)}</td><td>{px.iloc[-1]:,.2f}</td>"
            f"<td style='color:{GREEN if tot>=0 else RED}'>{tot:+.2f}%</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    # quick preview chart (rebased to 100)
    fig=go.Figure()
    for i,(sym,v) in enumerate(cs.items()):
        px=v["prices"]; base=float(px.iloc[0]); r=px/base*100
        fig.add_trace(go.Scatter(x=r.index,y=r.values,mode="lines",name=f"{v['name']} [{sym}]",
            line=dict(color=PALETTE[i%len(PALETTE)],width=1.8)))
    st.plotly_chart(base_layout(fig,"Uploaded series (rebased to 100)","",h=340),
                    use_container_width=True, key=k+"_chart")
    st.caption("Prices are stored as levels; uploaded returns are compounded to a base-100 index. "
               "Search any identifier above by name or ticker in other sections to use it.")

def panel_rolling_returns(k):
    chosen=ticker_picker(k, ["S&P 500"])
    series={lbl:md_history(sym) for lbl,sym in chosen.items()}
    series={lbl:s for lbl,s in series.items() if s is not None and not s.empty}
    c1,c2,c3=st.columns([1.2,1,1])
    fmode=c1.radio("Frequency",["Auto","Daily","Monthly"],horizontal=True,key=k+"_fm",
                   help="Monthly resamples every series to month-end so daily and "
                        "monthly-only series (e.g. factors) line up apples-to-apples.")
    use_monthly,note=_resolve_freq(fmode, list(series.values()))
    if use_monthly:
        win=int(c2.number_input("Window (months)", min_value=1, max_value=60, value=6, step=1, key=k+"_wm")); unit="month"
    else:
        win=int(c2.number_input("Window (days)", min_value=5, max_value=756, value=63, step=1, key=k+"_wd")); unit="day"
    yrs=c3.select_slider("Lookback (years)",[1,2,3,5,10,15,20,25],value=5,key=k+"_yr")
    labels=list(series.keys())
    b1,b2=st.columns(2)
    avg_for=b1.multiselect("Show average for", labels, default=labels, key=k+"_avg")
    sd_for=b2.multiselect("Show ±2σ bands for", labels, default=labels, key=k+"_sd")
    cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs)); lo,hi=date_window(k,cutoff); fig=go.Figure(); exp={}
    for i,(label,c) in enumerate(series.items()):
        if use_monthly: c=c.resample("ME").last().dropna()
        rr=(c.pct_change(win).dropna())*100; rr=rr[(rr.index>=lo)&(rr.index<=hi)]
        if rr.empty: continue
        col=PALETTE[i%len(PALETTE)]
        fig.add_trace(go.Scatter(x=rr.index,y=rr.values,mode="lines",name=label,
            line=dict(color=col,width=1.6))); exp[label]=rr
        add_stat_bands(fig, rr.values, col, label, label in avg_for, label in sd_for); add_today_marker(fig, rr, col)
    fig.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
    yr=yaxis_range_controls(k); fig=base_layout(fig,f"Rolling {win}-{unit} total return (%)","%",h=440); apply_yrange(fig,yr)
    st.plotly_chart(fig, use_container_width=True, key=k+"_chart")
    if note: st.caption(note)
    if exp:
        df=pd.DataFrame(exp); df.insert(0,"Date",df.index)
        dl(df,"Export","JAWS_rolling_returns.xlsx",k+"_dl")

def panel_rolling_sharpe(k):
    import numpy as np
    chosen=ticker_picker(k, ["S&P 500"])
    series={lbl:md_history(sym) for lbl,sym in chosen.items()}
    series={lbl:s for lbl,s in series.items() if s is not None and not s.empty}
    rf=md_history("BIL")     # SPDR 1-3 month T-bill ETF (total return) = risk-free
    c1,c2,c3=st.columns([1.2,1,1])
    fmode=c1.radio("Frequency",["Auto","Daily","Monthly"],horizontal=True,key=k+"_fm",
                   help="Monthly resamples every series to month-end so daily and "
                        "monthly-only series (e.g. factors) line up apples-to-apples.")
    use_monthly,note=_resolve_freq(fmode, list(series.values()))
    if use_monthly:
        win=int(c2.number_input("Window (months)", min_value=3, max_value=60, value=12, step=1, key=k+"_wm")); unit="month"; ppy=12
    else:
        win=int(c2.number_input("Window (days)", min_value=20, max_value=756, value=126, step=1, key=k+"_wd")); unit="day"; ppy=252
    yrs=c3.select_slider("Lookback (years)",[1,2,3,5,10,15,20,25],value=5,key=k+"_yr")
    labels=list(series.keys())
    b1,b2=st.columns(2)
    avg_for=b1.multiselect("Show average for", labels, default=labels, key=k+"_avg")
    sd_for=b2.multiselect("Show ±2σ bands for", labels, default=labels, key=k+"_sd")
    cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs)); lo,hi=date_window(k,cutoff); fig=go.Figure(); exp={}
    rf_ret=None
    if rf is not None and not rf.empty:
        rf2=rf.resample("ME").last() if use_monthly else rf
        rf_ret=rf2.pct_change()
    for i,(label,c) in enumerate(series.items()):
        if use_monthly: c=c.resample("ME").last().dropna()
        ra=c.pct_change()
        if rf_ret is not None:
            d=pd.concat([ra.rename("a"),rf_ret.rename("rf")],axis=1,join="inner").dropna()
            excess=d["a"]-d["rf"]
        else:
            excess=ra.dropna()
        sh=(excess.rolling(win).mean()/excess.rolling(win).std())*np.sqrt(ppy)
        sh=sh.dropna(); sh=sh[(sh.index>=lo)&(sh.index<=hi)]
        if sh.empty: continue
        col=PALETTE[i%len(PALETTE)]
        fig.add_trace(go.Scatter(x=sh.index,y=sh.values,mode="lines",name=label,
            line=dict(color=col,width=1.6))); exp[label]=sh
        add_stat_bands(fig, sh.values, col, label, label in avg_for, label in sd_for); add_today_marker(fig, sh, col)
    fig.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
    yr=yaxis_range_controls(k); fig=base_layout(fig,f"Rolling {win}-{unit} Sharpe ratio (annualized)","",h=440); apply_yrange(fig,yr)
    st.plotly_chart(fig, use_container_width=True, key=k+"_chart")
    rfnote=("Risk-free = **BIL** (1–3m T-bill) return." if rf_ret is not None
            else "⚠ T-bill (BIL) unavailable — risk-free treated as 0.")
    st.caption(f"Sharpe = mean(excess) ÷ std(excess) × √{ppy}, over a rolling {win}-{unit} window "
               f"(excess = asset return − T-bill return). {rfnote} " + (note or ""))
    if exp:
        df=pd.DataFrame(exp); df.insert(0,"Date",df.index)
        dl(df,"Export","JAWS_rolling_sharpe.xlsx",k+"_dl")

_PER_START={"MTD":lambda:date.today().replace(day=1),
            "3M":lambda:date.today()-relativedelta(months=3),
            "6M":lambda:date.today()-relativedelta(months=6),
            "YTD":lambda:date.today().replace(month=1,day=1),
            "1Y":lambda:date.today()-relativedelta(years=1),
            "3Y":lambda:date.today()-relativedelta(years=3),
            "5Y":lambda:date.today()-relativedelta(years=5),
            "10Y":lambda:date.today()-relativedelta(years=10),
            "20Y":lambda:date.today()-relativedelta(years=20),
            "Max":lambda:date(1900,1,1)}

def panel_outperf(k):
    """Outperformance of series A vs series B — rolling excess return or cumulative
    relative performance, with average/±2σ bands, rolling window, and full-period control."""
    chosen=ticker_picker(k, ["S&P 500","NASDAQ"])
    labels=list(chosen.keys())
    if len(labels)<2:
        st.info("Pick **two** series above. The **first** is A (target), the **second** is B "
                "(benchmark). Outperformance = A − B."); return
    if len(labels)>2:
        st.caption(f"Using the first two: **A = {labels[0]}**, **B = {labels[1]}** (others ignored).")
    A,B=labels[0],labels[1]; symA,symB=chosen[A],chosen[B]
    c1,c2,c3=st.columns([2,1,1])
    per=c1.select_slider("Period",list(_PER_START)+["Custom"],value="5Y",key=k+"_per")
    if per=="Custom":
        d1,d2=st.columns(2)
        cstart=d1.date_input("Start", value=date.today()-relativedelta(years=5),
                             min_value=date(1900,1,1), key=k+"_cs")
        cend=d2.date_input("End", value=date.today(), key=k+"_ce")
    else:
        cstart=_PER_START[per](); cend=date.today()
    basis=c2.radio("Basis",["Rolling","Cumulative"],horizontal=True,key=k+"_basis",
                   help="Rolling = A's window return minus B's. Cumulative = growth of A "
                        "relative to B since the start of the period.")
    fmode=c3.radio("Frequency",["Auto","Daily","Monthly"],horizontal=True,key=k+"_fm")
    sA=md_history(symA, start=cstart.strftime("%Y-%m-%d"))
    sB=md_history(symB, start=cstart.strftime("%Y-%m-%d"))
    if sA is None or sA.empty or sB is None or sB.empty:
        st.warning("One of the series returned no data for this range."); return
    sA=sA[sA.index<=pd.Timestamp(cend)]; sB=sB[sB.index<=pd.Timestamp(cend)]
    use_monthly,note=_resolve_freq(fmode,[sA,sB])
    if use_monthly:
        sA=sA.resample("ME").last().dropna(); sB=sB.resample("ME").last().dropna()
    df=pd.concat([sA.rename("a"),sB.rename("b")],axis=1,join="inner").dropna()
    if len(df)<3:
        st.warning("Not enough overlapping data between the two series for this range."); return
    b1,b2=st.columns(2)
    show_avg=b1.checkbox("Show average", value=True, key=k+"_avg")
    show_sd=b2.checkbox("Show ±2σ bands", value=True, key=k+"_sd")
    fig=go.Figure()
    if basis=="Rolling":
        wc=st.columns([1,3])[0]
        if use_monthly:
            win=int(wc.number_input("Rolling window (months)",min_value=1,max_value=60,value=6,step=1,key=k+"_wm")); unit="month"
        else:
            win=int(wc.number_input("Rolling window (days)",min_value=5,max_value=756,value=63,step=1,key=k+"_wd")); unit="day"
        out=((df["a"].pct_change(win)-df["b"].pct_change(win)).dropna())*100
        if out.empty: st.warning("Window too long for the selected period."); return
        ttl=f"Rolling {win}-{unit} outperformance · {A} − {B} (now {out.iloc[-1]:+.1f}%)"
    else:
        rel=((df["a"]/float(df["a"].iloc[0]))/(df["b"]/float(df["b"].iloc[0]))-1.0)*100
        out=rel.dropna()
        ttl=f"Cumulative outperformance · {A} vs {B} (now {out.iloc[-1]:+.1f}%)"
    col=GREEN if out.iloc[-1]>=0 else RED
    fig.add_trace(go.Scatter(x=out.index,y=out.values,mode="lines",name=f"{A} − {B}",
        line=dict(color=col,width=1.8),fill="tozeroy",
        fillcolor="rgba(63,185,80,0.10)" if out.iloc[-1]>=0 else "rgba(248,81,73,0.10)"))
    fig.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
    add_stat_bands(fig, out.values, ACCENT, f"{A}−{B}", show_avg, show_sd)
    add_today_marker(fig, out)
    yr=yaxis_range_controls(k); fig=base_layout(fig,ttl,"%",h=440); apply_yrange(fig,yr)
    st.plotly_chart(fig,use_container_width=True,key=k+"_chart")
    st.caption(("Positive = A outperforming B. " )+(note or
               "Rolling = difference in trailing-window returns; Cumulative = relative growth since period start."))
    ex=pd.DataFrame({"Date":out.index,f"{A} - {B} (%)":out.values})
    dl(ex,"Export","JAWS_outperformance.xlsx",k+"_dl")

def panel_vix_term(k):
    v=vix_term()
    if v.get("error") or not v["points"]:
        st.warning(f"VIX term structure unavailable: {v.get('error')}"); return
    pts=v["points"]
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=[d for _,d,_ in pts], y=[x for *_,x in pts],
        mode="lines+markers+text", text=[f"{x:.1f}" for *_,x in pts], textposition="top center",
        textfont=dict(size=10,color=TEXT1), line=dict(color=ACCENT,width=2.4), marker=dict(size=8),
        name="Vol (annualized %)"))
    fig.update_xaxes(tickvals=[d for _,d,_ in pts], ticktext=[l.split()[0] for l,_,_ in pts])
    slope=pts[-1][2]-pts[0][2]
    shape="contango — calm now, more vol priced further out" if slope>0 else "backwardation — near-term stress"
    st.plotly_chart(base_layout(fig,f"VIX term structure · {v['as_of']}","",h=310),
        use_container_width=True, key=k+"_chart")
    st.caption(f"Shape: **{shape}**. Constant-maturity CBOE vol indices (free, no futures license). "
               "Upward = contango (roll cost for long vol); inverted = near-term stress. "
               "Slope history is in the *Term-Structure Steepness* section below.")
    dl(pd.DataFrame([{"Label":l,"Maturity_days":d,"Vol":x} for l,d,x in pts]),
       "Export","JAWS_vix_term.xlsx",k+"_dl")

# Term-structure steepness measures with clean free history (vol via CBOE, rates via FRED)
_STEEP={
    "VIX − VIX3M (30d vs 3m vol)":   ("vix","VIX","VIX3M","vol pts","below 0 = contango/calm · above = inverted/stress"),
    "VIX3M − VIX6M (3m vs 6m vol)":  ("vix","VIX3M","VIX6M","vol pts","term-structure slope further out"),
    "VIX9D − VIX (9d vs 30d vol)":   ("vix","VIX9D","VIX","vol pts","very front-end vol kink"),
    "Treasury 10Y − 2Y (2s10s)":     ("fred","T10Y2Y","","%","below 0 = inverted curve (recession signal)"),
    "Treasury 10Y − 3M":             ("fred","T10Y3M","","%","below 0 = inverted vs bills"),
    "Treasury 30Y − 5Y":             ("fdiff","DGS30","DGS5","%","long-end steepness"),
}
@st.cache_data(ttl=1800, show_spinner=False)
def _fred_series(sid):
    import fi_spreads as fs
    d,v=fs._fred_fetch_all(sid)
    return None if not d else pd.Series(v, index=pd.to_datetime(d)).sort_index()

def panel_steepness(k):
    name=st.selectbox("Measure", list(_STEEP), key=k+"_sel")
    kind,a,b,unit,note=_STEEP[name]
    c1,c2,c3=st.columns([1.6,1,1])
    yrs=c1.select_slider("Lookback (years)",[1,2,3,5,10,20],value=5,key=k+"_yr")
    show_avg=c2.checkbox("Avg", value=True, key=k+"_avg")
    show_sd=c3.checkbox("±2σ", value=True, key=k+"_sd")
    try:
        if kind=="vix":
            sa=pd.Series(dict(vix_hist(a))); sb=pd.Series(dict(vix_hist(b)))
            sa.index=pd.to_datetime(sa.index); sb.index=pd.to_datetime(sb.index)
            d=pd.concat([sa.rename("a"),sb.rename("b")],axis=1,join="inner").dropna()
            spr=(d["a"]-d["b"])
        elif kind=="fred":
            spr=_fred_series(a)
        else:  # fdiff
            sa=_fred_series(a); sb=_fred_series(b)
            d=pd.concat([sa.rename("a"),sb.rename("b")],axis=1,join="inner").dropna()
            spr=(d["a"]-d["b"])
    except Exception as e:
        st.warning(f"Data unavailable: {e}"); return
    if spr is None or spr.dropna().empty:
        st.warning("No data for this measure right now."); return
    spr=spr.dropna(); cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs))
    lo,hi=date_window(k,cutoff); spr=spr[(spr.index>=lo)&(spr.index<=hi)]
    if spr.empty: st.warning("No data in that lookback."); return
    cur=float(spr.iloc[-1]); mu=float(spr.mean()); sd=float(spr.std())
    z=(cur-mu)/sd if sd>1e-9 else None
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=spr.index,y=spr.values,mode="lines",line=dict(color=ACCENT,width=1.7),name=name))
    fig.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
    add_stat_bands(fig, spr.values, BLUE, name, show_avg, show_sd)
    add_today_marker(fig, spr)
    yr=yaxis_range_controls(k); fig=base_layout(fig,f"{name} · now {cur:+.2f} {unit}","",h=440); apply_yrange(fig,yr)
    st.plotly_chart(fig, use_container_width=True, key=k+"_chart")
    m=st.columns(4)
    m[0].metric("Current", f"{cur:+.2f}")
    m[1].metric("Average", f"{mu:+.2f}")
    m[2].metric("Std dev", f"{sd:.2f}")
    m[3].metric("Z-score", f"{z:+.2f}" if z is not None else "—",
                help="Rich/cheap vs own history: >0 = steeper/wider than average.")
    st.caption(f"{note}. Vol slopes use CBOE constant-maturity indices; rate slopes use FRED. "
               "Positive z = curve steeper (or spread wider) than its own history.")
    dl(pd.DataFrame({"Date":spr.index, name:spr.values}),"Export","JAWS_steepness.xlsx",k+"_dl")

def panel_energy_curve(k):
    import futures_data as fx
    opts=list(fx.CURVE_PRODUCTS.keys())
    sel=st.multiselect("Futures", opts, default=["WTI Crude ($/bbl)"], key=k+"_sel")
    c2,c3=st.columns([2,1])
    n=int(c2.select_slider("Months out",[6,9,12,18,24],value=12,key=k+"_n"))
    dual=c3.checkbox("Right axis (2nd)", value=False, key=k+"_dual",
                     help="Plot the second selected contract on a separate right-hand axis "
                          "(useful when two markets have very different price scales).")
    if not sel:
        st.info("Pick one or more futures to plot the curve."); return
    curves=commodity_curves(tuple(sel), n)
    fig=go.Figure(); valid=[]
    for i,p in enumerate(sel):
        pts=(curves.get(p) or {}).get("points") or []
        if len(pts)<2: continue
        onR = dual and len(valid)==1          # second plotted series → right axis
        valid.append(p)
        fig.add_trace(go.Scatter(x=[l for l,_ in pts], y=[v for _,v in pts], mode="lines+markers",
            name=p+(" (R)" if onR else ""), line=dict(color=PALETTE[i%len(PALETTE)],width=2),
            marker=dict(size=6), yaxis="y2" if onR else "y"))
    if not valid:
        st.warning("No contract data returned right now — hit ↻ Refresh."); return
    base_layout(fig,"Futures curves","",h=340)
    if dual and len(valid)>=2:
        fig.update_layout(yaxis2=dict(overlaying="y", side="right", gridcolor=BORDER,
                                      color=TEXT1, tickfont=dict(color=TEXT1)))
    st.plotly_chart(fig, use_container_width=True, key=k+"_chart")
    cols=st.columns(len(valid))
    for i,p in enumerate(valid):
        ry=curves[p]["roll_yield_pct"]
        cols[i].metric(f"{p.split('(')[0].strip()} roll yld",
                       f"{ry:+.1f}%" if ry is not None else "—",
                       help="Annualized front-to-next. Positive = backwardation (roll gain for a long); "
                            "negative = contango (roll drag).")
    st.caption("Curve = successive listed expiries (front → deferred; equity-index & Treasury futures are "
               "quarterly). Downward = backwardation (positive roll yield); upward = contango (negative). "
               "For financial futures the roll yield is the annualized calendar carry (financing − dividends "
               "for equities; rate differential for FX). Prices via Yahoo (delayed).")
    rows=[]
    for p in valid:
        for l,v in curves[p]["points"]: rows.append({"Product":p,"Contract":l,"Price":v})
    dl(pd.DataFrame(rows),"Export","JAWS_futures_curves.xlsx",k+"_dl")
    # Equity index futures-vs-spot basis (annualized implied carry = financing − dividends)
    eq={"S&P 500 E-mini (ES)":"^GSPC","Nasdaq-100 E-mini (NQ)":"^IXIC",
        "Dow E-mini (YM)":"^DJI","Russell 2000 E-mini (RTY)":"^RUT"}
    eqsel=[p for p in valid if p in eq]
    if eqsel:
        st.markdown("**Equity futures basis vs cash index** (annualized implied carry)")
        bc=st.columns(len(eqsel))
        for i,p in enumerate(eqsel):
            pts=curves[p]["points"]; F=pts[0][1]; lbl=pts[0][0]
            spot=md_history(eq[p]);
            if spot is None or spot.empty: continue
            s0=float(spot.iloc[-1]); dte=_days_to_expiry(lbl)
            basis=(F/s0-1.0)*(365.0/max(dte,1))*100 if s0 else None
            bc[i].metric(f"{p.split('(')[0].strip()} basis",
                         f"{basis:+.2f}%" if basis is not None else "—",
                         help=f"Front {lbl} future {F:,.0f} vs spot {s0:,.0f}, annualized over ~{dte}d. "
                              "Positive = futures rich (financing > dividends).")

def _days_to_expiry(mon_label):
    """Approx calendar days to a quarterly contract's 3rd-Friday expiry from its 'Mon YY' label."""
    try:
        mon=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"].index(mon_label[:3])+1
        yr=2000+int(mon_label[-2:])
        d=date(yr,mon,1)
        # first Friday, then +14 for the 3rd Friday
        first_fri=1+((4-d.weekday())%7)
        exp=date(yr,mon,first_fri+14)
        return max((exp-date.today()).days,1)
    except Exception:
        return 30

def panel_commodity_spreads(k):
    legs_defs={
        "Brent − WTI ($/bbl)":            (["BZ=F","CL=F"], lambda r: r["BZ=F"]-r["CL=F"], "$/bbl"),
        "3-2-1 Crack ($/bbl)":            (["RB=F","HO=F","CL=F"],
                                           lambda r:(2*r["RB=F"]*42+r["HO=F"]*42-3*r["CL=F"])/3, "$/bbl"),
        "Gasoline Crack (RBOB−WTI)":      (["RB=F","CL=F"], lambda r: r["RB=F"]*42-r["CL=F"], "$/bbl"),
        "Distillate Crack (HO−WTI)":      (["HO=F","CL=F"], lambda r: r["HO=F"]*42-r["CL=F"], "$/bbl"),
        "Soybean Crush ($/bu)":           (["ZM=F","ZL=F","ZS=F"],
                                           lambda r: r["ZM=F"]*0.022+11*r["ZL=F"]/100-r["ZS=F"]/100, "$/bu"),
        "Gold / Silver ratio":            (["GC=F","SI=F"], lambda r: r["GC=F"]/r["SI=F"], "ratio"),
        "Corn / Wheat ratio":             (["ZC=F","ZW=F"], lambda r: r["ZC=F"]/r["ZW=F"], "ratio"),
        "Soybean / Corn ratio":           (["ZS=F","ZC=F"], lambda r: r["ZS=F"]/r["ZC=F"], "ratio"),
    }
    name=st.selectbox("Spread / ratio", list(legs_defs), key=k+"_sel")
    legs,fn,unit=legs_defs[name]
    c1,c2,c3=st.columns([1.4,1,1])
    yrs=c1.select_slider("Lookback (years)",[1,2,3,5,10],value=3,key=k+"_yr")
    show_avg=c2.checkbox("Avg", value=True, key=k+"_avg")
    show_sd=c3.checkbox("±2σ", value=True, key=k+"_sd")
    ser={}
    for s in legs:
        h=md_history(s)
        if h is None or h.empty:
            st.warning(f"Leg {s} unavailable right now — hit ↻ Refresh."); return
        ser[s]=h
    df=pd.concat([ser[s].rename(s) for s in legs],axis=1,join="inner").sort_index().dropna()
    spr=fn(df).dropna()
    cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs)); lo,hi=date_window(k,cutoff)
    spr=spr[(spr.index>=lo)&(spr.index<=hi)]
    if spr.empty:
        st.warning("No overlapping history for that lookback."); return
    cur=float(spr.iloc[-1]); mu=float(spr.mean()); sd=float(spr.std())
    z=(cur-mu)/sd if sd>1e-9 else None
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=spr.index,y=spr.values,mode="lines",line=dict(color=ACCENT,width=1.7),name=name))
    add_stat_bands(fig, spr.values, BLUE, name, show_avg, show_sd)
    add_today_marker(fig, spr)
    yr=yaxis_range_controls(k); fig=base_layout(fig,f"{name} · now {cur:,.2f} {unit}","",h=440); apply_yrange(fig,yr)
    st.plotly_chart(fig, use_container_width=True, key=k+"_chart")
    m=st.columns(4)
    m[0].metric("Current", f"{cur:,.2f}")
    m[1].metric("Average", f"{mu:,.2f}")
    m[2].metric("Std dev", f"{sd:,.2f}")
    m[3].metric("Z-score", f"{z:+.2f}" if z is not None else "—",
                help="Rich/cheap vs own history: >0 = wide/expensive, <0 = narrow/cheap.")
    st.caption("Crack = product value − crude (product $/gal × 42 → $/bbl); 3-2-1 = (2·gasoline + 1·distillate "
               "− 3·crude)/3. Crush ($/bu) = meal×0.022 + oil×11¢ − soybeans. Built from continuous front "
               "contracts (Yahoo, delayed) — absolute levels carry some roll-timing basis, so the **z-score** "
               "(rich vs cheap vs history) is the primary read.")
    dl(pd.DataFrame({"Date":spr.index, name:spr.values}),"Export","JAWS_commodity_spread.xlsx",k+"_dl")

def panel_fed(k):
    import futures_data as fx
    rp=rate_path()
    if not rp.get("error") and rp["points"]:
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=[y for _,y,_ in rp["points"]], y=[val for *_,val in rp["points"]],
            mode="lines+markers+text", text=[f"{val:.2f}" for *_,val in rp["points"]],
            textposition="top center", textfont=dict(size=10,color=TEXT1),
            line=dict(color=ACCENT,width=2.2), marker=dict(size=8), name="Implied avg rate"))
        if rp["effr"] is not None:
            fig.add_hline(y=rp["effr"], line=dict(color=TEXT3,dash="dash"),
                          annotation_text=f"current EFFR {rp['effr']:.2f}%")
        fig.update_xaxes(tickvals=[y for _,y,_ in rp["points"]], ticktext=[l for l,_,_ in rp["points"]])
        st.plotly_chart(base_layout(fig,f"Market-implied expected rate path · as of {rp['as_of']}","%",h=290),
            use_container_width=True, key=k+"_path")
        st.caption("Approximation from the front Treasury curve + EFFR (embeds term/liquidity premium). "
                   "Shows expected direction — NOT true meeting-by-meeting probabilities.")
    st.divider()
    st.markdown("**Meeting-implied hike/cut probabilities — Fed Funds futures (ZQ)**")
    strip=zq_strip_auto(); src="CBOT 30-Day Fed Funds via Yahoo (delayed settlements)" if strip else None
    with st.expander("Override with a manually pasted ZQ strip (optional)"):
        st.caption("Leave blank to use the automatic feed. To override, paste CME settlements as "
                   "`YYYY-MM, price` or `ZQN26, price` (one per line).")
        paste=st.text_area("Pasted strip", key=k+"_paste", height=110, label_visibility="collapsed",
                           placeholder="2026-07, 96.37\n2026-08, 96.32\n2026-09, 96.27")
        rows=[]
        for ln in paste.splitlines():
            parts=[x.strip() for x in ln.replace("\t",",").split(",") if x.strip()]
            if len(parts)>=2: rows.append((parts[0],parts[1]))
        if rows:
            ov=fx.parse_zq_upload(rows)
            if ov: strip=ov; src="pasted strip"
    if not strip:
        st.caption("Fed Funds futures strip is unavailable right now — hit ↻ Refresh, or paste one above.")
    if strip:
        mp=fx.fedwatch_meeting_probs(strip)
        if not mp:
            st.caption("No upcoming FOMC meetings within the available futures horizon."); return
        def _pcell(v, color):
            return f"<td style='color:{TEXT3}'>—</td>" if v<=0 else f"<td style='color:{color}'>{v:.0f}%</td>"
        hdr=["FOMC meeting","Implied rate in→out","Δ bps","Cut ≥25bp","Hold","Hike ≥25bp","Most likely"]
        h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
        for r in mp:
            p_cut=p_hold=p_hike=0.0
            for kk,vv in r["outcomes"].items():
                b=int(kk)
                if b<0: p_cut+=vv
                elif b>0: p_hike+=vv
                else: p_hold+=vv
            mlb=r["most_likely_bps"]
            mlc=GREEN if mlb<0 else (RED if mlb>0 else TEXT2)
            mll="hold" if mlb==0 else (f"{mlb:+d}bp "+("cut" if mlb<0 else "hike"))
            dc=GREEN if r["change_bps"]<-0.5 else (RED if r["change_bps"]>0.5 else TEXT2)
            h+=(f"<tr><td>{r['date']}</td><td>{r['r_in']:.2f} → {r['r_out']:.2f}%</td>"
                f"<td style='color:{dc}'>{r['change_bps']:+.0f}</td>"
                f"{_pcell(p_cut,GREEN)}<td>{p_hold:.0f}%</td>{_pcell(p_hike,RED)}"
                f"<td style='color:{mlc}'>{mll} @ {r['p_most']:.0f}%</td></tr>")
        st.markdown(h+"</table></div>", unsafe_allow_html=True)
        st.caption(f"Source: {src}. **Meeting-date-weighted FedWatch method**: each contract month's "
                   "implied average rate (100 − ZQ price) is split by the FOMC meeting day to solve the "
                   "expected post-meeting rate, then distributed over the nearest 25bp outcomes; rates "
                   "chain meeting-to-meeting. 2027 dates are the Fed's tentative schedule.")
        exp=[{"Meeting":r["date"],"Rate_in":r["r_in"],"Rate_out":r["r_out"],"Change_bps":r["change_bps"],
              "MostLikely_bps":r["most_likely_bps"],"P_most":r["p_most"],
              **{f"P({kk}bp)":vv for kk,vv in r["outcomes"].items()}} for r in mp]
        dl(pd.DataFrame(exp),"Export","JAWS_fed_meeting_probs.xlsx",k+"_dl")

def panel_prediction(k):
    import prediction_markets as pmkt
    c1,c2=st.columns(2)
    srcs=c1.multiselect("Sources",["Polymarket","Kalshi"],default=["Polymarket","Kalshi"],key=k+"_src")
    tops=c2.multiselect("Topics",list(pmkt.TOPICS.keys()),default=list(pmkt.TOPICS.keys()),key=k+"_top")
    if not srcs or not tops:
        st.info("Pick at least one source and topic."); return
    with st.spinner("Fetching prediction markets…"):
        rows=prediction_markets_data(tuple(srcs), tuple(tops))
    if not rows:
        st.info("No matching markets right now — try Refresh."); return
    rows=rows[:40]
    import html as _html
    hdr=["Implied","Contract","Topic","Src","24h Vol","Closes"]
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
    for r in rows:
        p=r["prob"]; pc=GREEN if p>=50 else TEXT1
        oc=f" · {r['outcome']}" if r["outcome"] not in ("Yes","top") else ""
        q=r["question"]; q=(q[:150].rstrip()+"…") if len(q)>150 else q
        q=_html.escape(q)
        h+=(f"<tr><td style='color:{pc};font-weight:700'>{p:.0f}%</td>"
            f"<td style='text-align:left;white-space:normal;min-width:240px;max-width:540px'>"
            f"<a href='{r['url']}' target='_blank' style='color:{TEXT1};text-decoration:none'>"
            f"{q}</a><span style='color:{TEXT3}'>{_html.escape(oc)}</span></td>"
            f"<td style='color:{TEXT3}'>{r['topic']}</td>"
            f"<td style='color:{_src_color(r['source'])}'>{r['source']}</td>"
            f"<td>{r['vol24']:,.0f}</td>"
            f"<td style='color:{TEXT3}'>{r['end']}</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    st.caption("Market-implied probabilities (real-money crowd pricing), **not forecasts**. Polymarket = "
               "'Yes'/top-outcome price; Kalshi = last/mid price. Sorted by 24h volume. 24h Vol units differ "
               "by source (Polymarket ≈ USD, Kalshi = contracts). Click a contract to open it. Public APIs.")
    dl(pd.DataFrame(rows),"Export","JAWS_prediction_markets.xlsx",k+"_dl")

def _holdings_table(sym, subtitle, n=10):
    import html as _html
    rows=etf_top_holdings(sym)
    if not rows:
        st.caption(f"{sym} holdings unavailable right now."); return
    st.markdown(f"**{subtitle}** · <span style='color:{TEXT3};font-size:12px'>{sym}</span>",
                unsafe_allow_html=True)
    hdr=["#","Ticker","Name","Wgt%"]
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
    for i,(tk,nm,w) in enumerate(rows[:n],1):
        h+=(f"<tr><td style='color:{TEXT3}'>{i}</td><td>{_html.escape(tk)}</td>"
            f"<td style='text-align:left;white-space:normal;max-width:230px'>{_html.escape(nm)}</td>"
            f"<td>{w*100:.1f}%</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)

_EQFIN={"S&P 500 (ES)":("S&P 500 E-mini (ES)","^GSPC","SPY","ES=F"),
        "Nasdaq-100 (NQ)":("Nasdaq-100 E-mini (NQ)","^IXIC","QQQ","NQ=F"),
        "Dow (YM)":("Dow E-mini (YM)","^DJI","DIA","YM=F"),
        "Russell 2000 (RTY)":("Russell 2000 E-mini (RTY)","^RUT","IWM","RTY=F")}

def _days_to_next_q(d):
    """Calendar days from date d to the next quarterly (Mar/Jun/Sep/Dec) 3rd-Friday expiry."""
    cands=[]
    for y in (d.year, d.year+1):
        for m in (3,6,9,12):
            first=date(y,m,1); ff=1+((4-first.weekday())%7); cands.append(date(y,m,ff+14))
    fut=[e for e in cands if e>=d]
    return (min(fut)-d).days if fut else None

@st.cache_data(ttl=1800, show_spinner=False)
def eq_financing_series(fut_sym, spot_sym, div_etf, yrs):
    """Historical implied financing spread over SOFR (bps) from the continuous front
    future vs cash index, using days to the next quarterly expiry for annualization."""
    import fi_spreads as fs
    fut=md_history(fut_sym); spot=md_history(spot_sym)
    if fut is None or spot is None or fut.empty or spot.empty: return None
    q=trailing_div_yield(div_etf) or 0.0
    d,v=fs._fred_fetch_all("SOFR")
    if not d: return None
    sofr=pd.Series(v, index=pd.to_datetime(d))/100.0
    df=pd.concat([fut.rename("F"),spot.rename("S")],axis=1,join="inner").dropna()
    cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs)); df=df[df.index>=cutoff]
    if df.empty: return None
    df["sofr"]=sofr.reindex(df.index, method="ffill")
    out={}
    for tm,r in df.iterrows():
        dd=_days_to_next_q(tm.date())
        if not dd or dd<10: continue                 # skip last ~10d before roll (annualization noise)
        t=dd/365.0; net=(r["F"]/r["S"]-1.0)/t
        out[tm]=(net+q-r["sofr"])*10000.0
    s=pd.Series(out)
    s=s[(s>-300)&(s<600)]                            # drop roll/timing outliers
    return s if not s.empty else None

def panel_eq_financing(k):
    idx=st.selectbox("Index", list(_EQFIN), key=k+"_idx")
    prod,spot_sym,etf,futc=_EQFIN[idx]
    curve=(commodity_curves((prod,),12) or {}).get(prod) or {}
    pts=curve.get("points") or []
    spot_s=md_history(spot_sym)
    if spot_s is None or spot_s.empty or len(pts)<1:
        st.warning("Futures or spot data unavailable right now — hit ↻ Refresh."); return
    spot=float(spot_s.iloc[-1])
    q=trailing_div_yield(etf); qv=q if q is not None else 0.0
    sofr_s=_fred_series("SOFR")
    sofr=float(sofr_s.iloc[-1])/100 if (sofr_s is not None and not sofr_s.empty) else None
    rows=[]
    for lbl,F in pts[:4]:
        days=_days_to_expiry(lbl); t=days/365.0
        if t<=0: continue
        net=(F/spot-1.0)/t                 # r − q  (net cost of carry)
        rimp=net+qv                        # implied financing rate r
        spread=(rimp-sofr) if sofr is not None else None
        rows.append((lbl,F,days,net*100,qv*100,rimp*100,(spread*10000 if spread is not None else None)))
    hdr=["Contract","Future","Days","Net carry %","+ Div yld %","= Implied fin %","− SOFR (bps)"]
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
    for lbl,F,days,net,divp,rimp,sp in rows:
        spc=RED if (sp is not None and sp>0) else GREEN
        h+=(f"<tr><td>{lbl}</td><td>{F:,.0f}</td><td>{days}</td><td>{net:+.2f}%</td>"
            f"<td>{divp:.2f}%</td><td>{rimp:+.2f}%</td>"
            f"<td style='color:{spc}'>{(f'{sp:+.0f}' if sp is not None else '—')}</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    front=rows[0] if rows else None
    m=st.columns(4)
    m[0].metric("Spot", f"{spot:,.0f}")
    m[1].metric("Div yield (12m)", f"{qv*100:.2f}%")
    m[2].metric("SOFR", f"{sofr*100:.2f}%" if sofr is not None else "—")
    if front and front[6] is not None:
        m[3].metric("Front financing spread", f"{front[6]:+.0f} bps",
                    help="Implied financing rate on the front contract minus SOFR.")
    st.caption("Implied financing = **(future ÷ spot − 1) annualized + dividend yield**; the spread is that "
               "minus SOFR — the market's synthetic cost to finance long index exposure. **Market-implied, "
               "not a dealer TRS quote** (bank total-return-swap spreads are bilateral/private).")
    dl(pd.DataFrame(rows,columns=["Contract","Future","Days","NetCarry%","DivYld%","ImpliedFin%","SpreadBps"]),
       "Export","JAWS_equity_financing.xlsx",k+"_dl")
    # ── Financing spread over time (the quarter-end funding-pressure pattern) ──
    st.divider()
    t1,t2,t3=st.columns([1.6,1,1])
    yrs=t1.select_slider("History (years)",[1,2,3,5],value=3,key=k+"_yr")
    show_avg=t2.checkbox("Avg", value=True, key=k+"_avg")
    show_sd=t3.checkbox("±2σ", value=True, key=k+"_sd")
    lo,hi=date_window(k, pd.Timestamp(datetime.today()-relativedelta(years=yrs)))
    with st.spinner("Building financing-spread history…"):
        s=eq_financing_series(futc, spot_sym, etf, max(yrs, (date.today()-lo.date()).days//365+1))
    if s is not None and not s.empty:
        s=s[(s.index>=lo)&(s.index<=hi)]
    if s is None or s.empty:
        st.caption("Financing-spread history unavailable for that range (SOFR history starts 2018).")
    else:
        f=go.Figure()
        f.add_trace(go.Scatter(x=s.index,y=s.values,mode="lines",line=dict(color=ACCENT,width=1.3),
            name="Implied financing spread"))
        f.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
        add_stat_bands(f, s.values, BLUE, "spread", show_avg, show_sd)
        add_today_marker(f, s)
        base_layout(f,f"{idx} implied financing spread vs SOFR · now {float(s.iloc[-1]):+.0f} bps","",h=440)
        f.update_layout(margin=dict(l=60,r=16,t=64,b=70)); f.update_yaxes(title="Spread over SOFR (bps)")
        apply_yrange(f, yaxis_range_controls(k))
        st.plotly_chart(f, use_container_width=True, key=k+"_ts")
        st.caption("From the **continuous front future** vs cash index (days to next quarterly expiry used for "
                   "annualization; dividend yield held at the current trailing rate). Watch the **spikes into "
                   "quarter-ends** — that's dealer balance-sheet/funding pressure, the signal this metric is best "
                   "for. Absolute level is approximate (spot/future timing); the *pattern* is the value.")
        dl(pd.DataFrame({"Date":s.index,"SpreadBps":s.values}),"Export history","JAWS_equity_financing_ts.xlsx",k+"_dl2")

def panel_crowding(k):
    c1,c2=st.columns(2)
    with c1:
        _holdings_table("GVIP","Crowded LONGS — GS Hedge Fund VIP")
    with c2:
        _holdings_table("HDGE","Crowded SHORTS — Ranger Equity Bear book")
    st.caption("**GVIP** = the stocks appearing most often among hedge funds' top-10 long positions "
               "(Goldman 'Hedge Fund VIP' basket) — the free proxy for crowded longs. **HDGE** = an "
               "actively-managed short fund; its book is a proxy for high-conviction shorts (no free ETF "
               "cleanly replicates the GS 'most-shorted' basket). Holdings from issuer daily files (via "
               "yfinance), updated daily — this is **not** GS/MS prime brokerage positioning, which is licensed.")

def panel_skew(k):
    c1,c2=st.columns([1,1])
    sym=c1.text_input("Underlying (optionable ticker)", "SPY", key=k+"_sym").strip().upper()
    dte=c2.select_slider("Target days to expiry",[7,14,30,60,90,120,180],value=30,key=k+"_dte")
    with st.spinner(f"Loading {sym} option chain…"):
        d=option_skew(sym, dte) if sym else None
    if not d:
        st.warning(f"No usable option chain for **{sym}** (not optionable, or data unavailable right now).")
    else:
        fig=go.Figure()
        mp=[(m,iv) for m,iv in zip(d["m"],d["iv"]) if m<=100]
        mc=[(m,iv) for m,iv in zip(d["m"],d["iv"]) if m>=100]
        if mp: fig.add_trace(go.Scatter(x=[m for m,_ in mp],y=[iv for _,iv in mp],mode="lines+markers",
            name="OTM puts (downside protection)",line=dict(color=RED,width=2),marker=dict(size=5)))
        if mc: fig.add_trace(go.Scatter(x=[m for m,_ in mc],y=[iv for _,iv in mc],mode="lines+markers",
            name="OTM calls (upside participation)",line=dict(color=GREEN,width=2),marker=dict(size=5)))
        fig.add_vline(x=100,line=dict(color=TEXT3,dash="dash"),annotation_text="ATM (spot)")
        base_layout(fig,f"{sym} implied-vol skew · exp {d['expiry']} ({d['dte']}d)","%",h=340)
        fig.update_layout(margin=dict(l=64,r=16,t=64,b=64))
        fig.update_xaxes(title="Strike as % of spot  (100 = at-the-money)")
        fig.update_yaxes(title="Implied volatility (annualized %)")
        st.plotly_chart(fig, use_container_width=True, key=k+"_curve")
        m=st.columns(4)
        m[0].metric("ATM IV", f"{d['atm']:.1f}%" if d['atm'] is not None else "—")
        m[1].metric("Risk reversal 90/110", f"{d['rr']:+.1f}" if d['rr'] is not None else "—",
                    help="Put IV(90% strike) − Call IV(110%). Positive = downside protection pricier than upside.")
        m[2].metric("Risk reversal 95/105", f"{d['rr5']:+.1f}" if d['rr5'] is not None else "—")
        m[3].metric("Spot", f"{d['spot']:,.2f}")
        if d['rr'] is not None:
            tone=("downside protection is **richer** than upside — the market is paying up to hedge (fearful/skewed)"
                  if d['rr']>0 else
                  "**upside** is priced above downside — unusual, a melt-up/greed signal")
            st.caption(f"Skew (90/110 risk reversal) = **{d['rr']:+.1f} vol pts** → {tone}. "
                       "Moneyness-based (not true 25-delta); yfinance IVs are delayed and can be noisy at thin strikes.")
    st.caption("Live option-implied skew from the yfinance chain. The **CBOE SKEW index history** "
               "(tail-risk over time) is in its own full-width section below.")

def panel_skew_index(k):
    st.markdown(f'<span style="color:{TEXT2};font-family:Consolas;font-size:12px;">CBOE SKEW index — '
                'tail-risk pricing over time (100 = symmetric; higher = more crash-hedging demand)</span>',
                unsafe_allow_html=True)
    cc1,cc2,cc3=st.columns([1.6,1,1])
    yrs=cc1.select_slider("Lookback (years)",[1,2,3,5,10,20],value=5,key=k+"_yr")
    show_avg=cc2.checkbox("Avg", value=True, key=k+"_avg")
    show_sd=cc3.checkbox("±2σ", value=True, key=k+"_sd")
    lo,hi=date_window(k, pd.Timestamp(datetime.today()-relativedelta(years=yrs)))
    s=md_history("^SKEW")
    if s is None or s.empty:
        st.caption("CBOE SKEW index unavailable right now."); return
    s=s[(s.index>=lo)&(s.index<=hi)]
    if s.empty:
        st.caption("No SKEW data in that range."); return
    f2=go.Figure()
    f2.add_trace(go.Scatter(x=s.index,y=s.values,mode="lines",line=dict(color=ACCENT,width=1.6),name="CBOE SKEW"))
    add_stat_bands(f2, s.values, BLUE, "SKEW", show_avg, show_sd)
    base_layout(f2,f"CBOE SKEW index · now {float(s.iloc[-1]):.0f}","",h=440)
    f2.update_layout(margin=dict(l=64,r=16,t=64,b=70))
    add_today_marker(f2, s)
    f2.update_yaxes(title="SKEW index level (100 = symmetric)")
    apply_yrange(f2, yaxis_range_controls(k))
    st.plotly_chart(f2, use_container_width=True, key=k+"_skewidx")
    st.caption("CBOE SKEW distills S&P 500 option prices into a single tail-risk gauge — higher = the market "
               "is paying more for crash protection. Above the average/+2σ band = tail hedging is rich.")
    dl(pd.DataFrame({"Date":s.index,"SKEW":s.values}),"Export","JAWS_skew_index.xlsx",k+"_dl")

def panel_news(k):
    import time as _t
    with st.spinner("Fetching markets news…"):
        try: items=markets_news()
        except Exception as e: items=[]; st.error(f"News error: {e}")
    now=_t.time()
    # Keep today/yesterday (last ~36h). If feeds carried no usable dates, don't
    # drop everything — fall back to the full list so the section never goes blank.
    dated=[it for it in items if it.get("ts")]
    recent=[it for it in dated if (now-it["ts"])<=36*3600]
    pool=recent or dated or items
    # Cap to 3 per source, then rank newest-first (proxy for "most read today"),
    # with source quality as the tie-break.
    per={}; capped=[]
    for it in sorted(pool, key=lambda x: x.get("ts") or 0, reverse=True):
        s=it.get("source","")
        if per.get(s,0)>=3: continue
        per[s]=per.get(s,0)+1; capped.append(it)
    for it in capped:
        it["_w"]=max((v for kk,v in NEWS_WEIGHT.items() if kk in (it.get("source") or "").lower()), default=4)
    capped.sort(key=lambda it:(it.get("ts") or 0, it["_w"]), reverse=True)
    capped=capped[:20]
    if not capped:
        st.info("No recent stories available right now."); return
    cols=st.columns(2)
    for i,it in enumerate(capped):
        title=it.get("title") or "(no title)"; url=it.get("url") or "#"
        src=it.get("source") or "Unknown"; age=_fmt_age(it.get("ts"), now)
        scol=_src_color(src)
        with cols[i%2]:
            st.markdown(f'<div style="background:{CARD2};border:1px solid {BORDER};border-left:3px solid {scol};'
                f'border-radius:4px;padding:3px 7px;margin-bottom:4px;line-height:1.25;">'
                f'<span style="color:{scol};font-weight:700;font-size:10px;">{src}</span>'
                f'<span style="color:{TEXT3};font-size:9px;"> · {age}</span><br>'
                f'<a href="{url}" target="_blank" style="color:{TEXT1};text-decoration:none;font-size:12px;">'
                f'{title}</a></div>', unsafe_allow_html=True)

def panel_valuation(k):
    # ── Current multiples cross-section ──
    ek=k+"_stk"
    if ek not in st.session_state: st.session_state[ek]={}
    if _HAS_SEARCHBOX:
        sel=st_searchbox(search_instruments, placeholder="Type to search & add a stock…", key=k+"_sb")
        if sel: st.session_state[ek][sel]=sel
    else:
        c1,c2=st.columns([3,1])
        q=c1.text_input("Add stock", key=k+"_q", label_visibility="collapsed",
                        placeholder="Add a stock by ticker or name…")
        if c2.button("Add", key=k+"_add") and q.strip():
            raw=q.strip()
            if len(raw)<=6 and raw.replace(".","").isalnum(): st.session_state[ek][raw.upper()]=raw.upper()
            else:
                res=yf_search(raw)
                if res: sym,nm=res[0]; st.session_state[ek][f"{nm[:18]} ({sym})"]=sym
    universe={**VAL_INDEX_ETFS, **st.session_state[ek]}
    hdr=["Name","Fwd P/E","Trail P/E","P/B","P/S","Fwd P/S","EV/EBITDA","PEG","EPS Gr%","Div%"]
    def fnum(v,suf=""): return f'<span style="color:{TEXT3}">—</span>' if not isinstance(v,(int,float)) else f"{v:.1f}{suf}"
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
    exp=[]
    with st.spinner("Loading multiples…"):
        for name,sym in universe.items():
            m=yf_multiples(sym)
            gr=m['EPSgr']; grc=GREEN if (isinstance(gr,(int,float)) and gr>=0) else (RED if isinstance(gr,(int,float)) else TEXT3)
            h+=("<tr>"f"<td>{name}</td><td>{fnum(m['FwdPE'])}</td><td>{fnum(m['PE'])}</td>"
                f"<td>{fnum(m['PB'])}</td><td>{fnum(m['PS'])}</td><td>{fnum(m['FwdPS'])}</td>"
                f"<td>{fnum(m['EVEBITDA'])}</td><td>{fnum(m['PEG'])}</td>"
                f"<td style='color:{grc}'>{fnum(gr,'%')}</td><td>{fnum(m['DivYld'])}</td></tr>")
            exp.append({"Name":name,"Ticker":sym,"FwdPE":m['FwdPE'],"TrailPE":m['PE'],"PB":m['PB'],
                        "PS":m['PS'],"FwdPS":m['FwdPS'],"EV/EBITDA":m['EVEBITDA'],"PEG":m['PEG'],
                        "EPSgr%":m['EPSgr'],"DivYld":m['DivYld']})
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    st.caption("Forward P/E, Fwd P/S and EPS growth are built from consensus estimates — "
               "single stocks only. Index ETFs show trailing P/E, P/B, yield (Yahoo doesn't "
               "publish forward data for funds; index forward multiples need the JPM feed).")
    dl(pd.DataFrame(exp), "Export multiples", "JAWS_valuation.xlsx", k+"_dl")

    # ── S&P 500 valuation vs history ──
    st.divider()
    st.markdown(f'<span style="color:{TEXT2};font-family:Consolas;font-size:12px;">'
                'S&amp;P 500 valuation vs history</span>', unsafe_allow_html=True)
    cc1,cc2=st.columns([3,1])
    metric=cc1.radio("Metric", list(MULTPL), horizontal=True, key=k+"_m", label_visibility="collapsed")
    win=cc2.selectbox("Window", ["All","30Y","20Y","10Y"], key=k+"_w")
    try:
        series=multpl_series(MULTPL[metric])
    except Exception as e:
        st.info(f"History source unavailable: {e}"); return
    if not series: st.info("No history available."); return
    if win!="All":
        yrs=int(win[:-1]); cutoff=date.today()-relativedelta(years=yrs)
        series=[(d,v) for d,v in series if d>=cutoff]
    ds=[d for d,_ in series]; vs=[v for _,v in series]
    cur=vs[-1]; n=len(vs)
    import statistics
    mean=statistics.mean(vs); std=statistics.pstdev(vs) if n>1 else 0
    pct=round(sum(1 for v in vs if v<=cur)/n*100)
    z=round((cur-mean)/std,2) if std else None
    pc = RED if pct>=80 else (GREEN if pct<=20 else YELLOW)
    m1,m2,m3=st.columns(3)
    m1.metric("Current", f"{cur:.1f}")
    m2.markdown(f'<div style="font-family:Consolas"><span style="color:{TEXT2};font-size:12px">Percentile vs history</span><br>'
                f'<span style="color:{pc};font-size:22px;font-weight:700">{pct}th</span></div>', unsafe_allow_html=True)
    m3.markdown(f'<div style="font-family:Consolas"><span style="color:{TEXT2};font-size:12px">Z-score</span><br>'
                f'<span style="color:{pc};font-size:22px;font-weight:700">{(f"{z:+.2f}σ" if z is not None else "—")}</span></div>', unsafe_allow_html=True)
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=ds,y=vs,mode="lines",line=dict(color=ACCENT,width=1.4)))
    fig.add_hline(y=mean,line=dict(color=TEXT3,dash="dash"),annotation_text=f"avg {mean:.1f}")
    st.plotly_chart(base_layout(fig,f"S&P 500 {metric} — {ds[0].year}–{ds[-1].year} "
                    f"({'expensive' if pct>=80 else 'cheap' if pct<=20 else 'mid'} vs history)",h=300),
                    use_container_width=True, key=k+"_chart")
    dl(pd.DataFrame({"Date":ds,metric:vs}), "Export history", f"JAWS_SP500_{metric.replace('/','_')}.xlsx", k+"_dl2")

# ════════════════════════════════════════════════════════════════
# REGRESSION TOOL
# ════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def reg_factors():
    """Flat {label: (dates, decimal_returns, is_daily)} for all L/S factors."""
    fd=factor_data()
    out={}
    for sect in ("daily","monthly"):
        for r in fd.get(sect,[]):
            if r.get("error"): continue
            out[f"{r['name']} ({'D' if r['is_daily'] else 'M'})"]=(
                r["raw_dates"], r["raw_rets"], r["is_daily"])
    return out

def _reg_build_series(src, sym, fred_id, upfile, fac, tf, freq):
    """Return a pd.Series (datetime index) for one regression variable."""
    s=None; is_factor=False
    if src=="Market ticker" and sym.strip():
        s=md_history(sym.strip())
    elif src=="FRED series" and fred_id.strip():
        import fi_spreads as fs
        d,v=fs._fred_fetch_all(fred_id.strip())
        if d: s=pd.Series(v, index=pd.to_datetime(d))
    elif src=="L/S Factor" and fac:
        facs=reg_factors()
        if fac in facs:
            d,r,_=facs[fac]
            s=pd.Series(r, index=pd.to_datetime(d)); is_factor=True   # decimal periodic returns
    elif src=="Upload CSV" and upfile is not None:
        try:
            df=pd.read_csv(upfile)
            df.iloc[:,0]=pd.to_datetime(df.iloc[:,0], errors="coerce")
            s=pd.Series(pd.to_numeric(df.iloc[:,1],errors="coerce").values, index=df.iloc[:,0]).dropna()
        except Exception: s=None
    if s is None or len(s)==0: return None
    s=s.sort_index()
    if is_factor:
        # Factor values are periodic RETURNS already. Compound to the chosen
        # frequency, express in %. (Transform is ignored except 'Level' = cum.)
        if freq=="Monthly": s=(1+s).resample("ME").prod()-1
        if tf=="Level":     s=((1+s).cumprod()-1)*100   # cumulative growth %
        else:               s=s*100                     # periodic return %
        return s.dropna()
    if freq=="Monthly": s=s.resample("ME").last()
    s=s.dropna()
    if tf=="Return %":   s=s.pct_change()*100
    elif tf=="YoY %":    s=s.pct_change(12 if freq=="Monthly" else 252)*100
    elif tf=="Change":   s=s.diff()
    return s.dropna()

def _reg_var_ui(side, k):
    st.markdown(f"**{side} variable**")
    src=st.radio("Source",["Market ticker","FRED series","L/S Factor","Upload CSV"],
                 horizontal=True,key=f"{k}_{side}_src",label_visibility="collapsed")
    sym=fred=fac=""; up=None
    if src=="Market ticker":
        deflt="SPY" if side=="X" else "AGG"
        if _HAS_SEARCHBOX:
            sel=st_searchbox(search_instruments, placeholder=f"Type to search (default {deflt})…",
                             key=f"{k}_{side}_sb")
            sym=sel or deflt
        else:
            sym=st.text_input("Ticker", deflt, key=f"{k}_{side}_sym")
        if sym.strip():
            nm,px=resolve_ticker(sym.strip())
            if nm or px:
                st.markdown(f'<span style="color:{GREEN};font-size:12px;">✅ {sym.strip().upper()} — '
                            f'{nm or "found"}{f" · {px:,.2f}" if px else ""}</span>',
                            unsafe_allow_html=True)
            else:
                st.markdown(f'<span style="color:{RED};font-size:12px;">❌ {sym.strip().upper()} '
                            f'not recognized</span>', unsafe_allow_html=True)
    elif src=="FRED series":
        fred=st.text_input("FRED series id (e.g. BAA10Y, DGS10)", "BAA10Y", key=f"{k}_{side}_fred")
        if fred.strip():
            t=fred_title(fred.strip())
            if t:
                st.markdown(f'<span style="color:{GREEN};font-size:12px;">✅ {fred.strip().upper()} — '
                            f'{t[:48]}</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span style="color:{YELLOW};font-size:12px;">⚠ {fred.strip().upper()} '
                            f'— could not verify (will still try)</span>', unsafe_allow_html=True)
    elif src=="L/S Factor":
        facs=list(reg_factors().keys())
        fac=st.selectbox("Factor", facs, key=f"{k}_{side}_fac") if facs else ""
        if fac:
            st.markdown(f'<span style="color:{GREEN};font-size:12px;">✅ {fac} · academic L/S return</span>',
                        unsafe_allow_html=True)
    else:
        up=st.file_uploader("CSV: first col = Date, second = Value", type=["csv"],
                            key=f"{k}_{side}_up")
        if up is not None:
            st.markdown(f'<span style="color:{GREEN};font-size:12px;">✅ {up.name} uploaded</span>',
                        unsafe_allow_html=True)
    # Factors are already returns → fix transform to Return %; others default Return %.
    if src=="L/S Factor":
        tf="Return %"; st.caption("Factor is already a return series.")
    else:
        tf=st.selectbox("Transform",["Level","Return %","YoY %","Change"],
                        index=1, key=f"{k}_{side}_tf")
    return src,sym,fred,fac,up,tf

def _ols_fit(y, X):
    """OLS with intercept. X: (n,k) design WITHOUT constant. Returns coeffs, t, p, R²,
    fitted, residuals — no statsmodels dependency (numpy + scipy)."""
    import numpy as np
    from scipy import stats
    y=np.asarray(y,float); X=np.atleast_2d(np.asarray(X,float))
    if X.shape[0]!=len(y): X=X.T
    n=len(y); Xd=np.column_stack([np.ones(n), X]); k=Xd.shape[1]
    if n<=k: return None
    beta,_,_,_=np.linalg.lstsq(Xd,y,rcond=None)
    resid=y-Xd@beta; sse=float(resid@resid); dof=n-k
    try: XtX_inv=np.linalg.inv(Xd.T@Xd)
    except np.linalg.LinAlgError: return None
    se=np.sqrt(np.maximum(np.diag((sse/dof)*XtX_inv),0)); se[se==0]=1e-12
    t=beta/se; p=2*(1-stats.t.cdf(np.abs(t),dof))
    sst=float(((y-y.mean())**2).sum()); r2=1-sse/sst if sst>0 else 0.0
    adj=1-(1-r2)*(n-1)/dof if dof>0 else r2
    return {"beta":beta,"se":se,"t":t,"p":p,"resid":resid,"fitted":Xd@beta,
            "r2":r2,"adj_r2":adj,"n":n,"dof":dof}

def _stepwise_backward(y, Xdf, cutoff):
    """Backward elimination: drop the least-significant factor while its p-value > cutoff."""
    import numpy as np
    cols=list(Xdf.columns)
    while len(cols)>1:
        fit=_ols_fit(y, Xdf[cols].values)
        if fit is None: break
        pv=fit["p"][1:]
        worst=int(np.argmax(pv))
        if pv[worst]>cutoff: cols.pop(worst)
        else: break
    return cols

def panel_regression():
    st.markdown(f'<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<span class="jaws-logo" style="font-size:16px;padding:3px 10px;">REG</span> '
                    '<span class="jaws-title" style="font-size:15px;">Regression Lab</span> '
                    '<span class="jaws-sub">OLS · any tool data or your own monthly CSV</span>',
                    unsafe_allow_html=True)
        import numpy as np
        from scipy import stats
        cf1,cf2,cf3=st.columns([1,1,1])
        freq=cf1.radio("Frequency",["Monthly","Daily"],horizontal=True,key="reg_freq")
        use_step=cf2.checkbox("Stepwise elimination", value=True, key="reg_step",
                              help="Backward-eliminate factors whose p-value exceeds the cutoff. "
                                   "On by default to keep the factor breakout readable.")
        cutoff=cf3.number_input("p-value cutoff", min_value=0.01, max_value=0.5, value=0.05,
                                step=0.01, key="reg_cut", disabled=not use_step)
        ydict=ticker_picker("reg_y", ["S&P 500"])
        ylabel=list(ydict.keys())[0] if ydict else None
        st.caption("Dependent variable **Y** above; explanatory variable(s) **X** below. Pick **one X** for a "
                   "simple regression, or **several** to run multi-factor. Default X = the monthly L/S factors.")
        _fac_default=[l for l in factor_labels() if "(M)" in l]
        xdict=ticker_picker("reg_x", _fac_default or ["US 10Y"])
        d1,d2=st.columns(2)
        start=d1.date_input("Start", value=date.today()-relativedelta(years=10),
                            min_value=date(1950,1,1), key="reg_start")
        end=d2.date_input("End", value=date.today(), key="reg_end")
        if not ylabel or not xdict:
            st.caption("Select a Y series and at least one X."); return
        ys=_corr_change_series("auto", ydict[ylabel], freq)
        xser={lbl:_corr_change_series("auto", sym, freq) for lbl,sym in xdict.items()}
        xser={l:s for l,s in xser.items() if s is not None and not s.empty}
        if ys is None or ys.empty or not xser:
            st.warning("Couldn't resolve the Y series or any X for that setup."); return
        frame=pd.concat([ys.rename("__Y__")]+[s.rename(l) for l,s in xser.items()],
                        axis=1, join="inner").dropna()
        frame=frame[(frame.index>=pd.Timestamp(start))&(frame.index<=pd.Timestamp(end))]
        Xall=frame.drop(columns="__Y__"); yv=frame["__Y__"]
        if len(frame)<len(Xall.columns)+3:
            st.warning(f"Only {len(frame)} overlapping points — widen the range or reduce factors."); return
        cols=list(Xall.columns)
        if use_step: cols=_stepwise_backward(yv.values, Xall, cutoff)
        fit=_ols_fit(yv.values, Xall[cols].values)
        if fit is None:
            st.warning("Regression could not be estimated (singular design or too few points)."); return
        beta=fit["beta"]; tvals=fit["t"]; pvals=fit["p"]
        hdr=["Term","Beta","t-stat","p-value"]
        h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
        for i,term in enumerate(["Alpha (intercept)"]+cols):
            sig=GREEN if pvals[i]<0.05 else (YELLOW if pvals[i]<0.10 else TEXT2)
            h+=(f"<tr><td>{term}</td><td>{beta[i]:+.4f}</td>"
                f"<td>{tvals[i]:+.2f}</td><td style='color:{sig}'>{pvals[i]:.4f}</td></tr>")
        st.markdown(h+"</table></div>", unsafe_allow_html=True)
        m=st.columns(4)
        m[0].metric("R²", f"{fit['r2']:.3f}")
        m[1].metric("Adj R²", f"{fit['adj_r2']:.3f}")
        m[2].metric("N obs", f"{fit['n']}")
        m[3].metric("Factors", f"{len(cols)}"+(" (stepwise)" if use_step else ""))
        if use_step and len(cols)<len(Xall.columns):
            st.caption(f"Stepwise dropped (p > {cutoff}): {', '.join(c for c in Xall.columns if c not in cols)}")
        # Scatter + fit line — only meaningful for a single X
        if len(cols)==1:
            xc=Xall[cols[0]].values
            fig=go.Figure()
            fig.add_trace(go.Scatter(x=xc,y=yv.values,mode="markers",
                marker=dict(color=BLUE,size=6,opacity=0.7),name="obs"))
            xr=np.array([xc.min(),xc.max()])
            fig.add_trace(go.Scatter(x=xr,y=beta[0]+beta[1]*xr,mode="lines",
                line=dict(color=ACCENT,width=2),name=f"fit β={beta[1]:.3f}"))
            base_layout(fig,f"{ylabel} vs {cols[0]}",h=320)
            fig.update_xaxes(title=cols[0]); fig.update_yaxes(title=ylabel)
            st.plotly_chart(fig, use_container_width=True, key="reg_chart")

        # ── Return attribution: Beta (β·X) vs idiosyncratic, by horizon ──
        st.markdown(f'<span style="color:{TEXT2};font-family:Consolas;font-size:12px;">'
                    'Return attribution — return split into Beta-driven (β·X) vs '
                    'idiosyncratic (α + residual) over each horizon</span>', unsafe_allow_html=True)
        ppy=12 if freq=="Monthly" else 252
        hz=[("1M",21),("1Y",252),("3Y",756),("5Y",1260),("10Y",2520),("Full",None)]
        if freq=="Monthly": hz=[("1M",1),("1Y",12),("3Y",36),("5Y",60),("10Y",120),("Full",None)]
        labels=[]; facv=[]; idiov=[]; totv=[]
        for lbl,N in hz:
            sub=frame if N is None else (frame.iloc[-N:] if N<=len(frame) else None)
            if sub is None or len(sub)<1: continue
            ysub=sub["__Y__"].values; fac=float((sub[cols].values@beta[1:]).sum())
            tot=float(ysub.sum()); idio=tot-fac
            # Annualize only horizons longer than 1 year; 1M/1Y shown as their raw period return.
            ann=ppy/len(sub) if len(sub)>ppy else 1.0
            labels.append(lbl); facv.append(fac*ann*100); idiov.append(idio*ann*100); totv.append(tot*ann*100)
        if labels:
            bar=go.Figure()
            bar.add_trace(go.Bar(x=labels,y=facv,name="From Beta(s) (β·X)",marker_color=BLUE))
            bar.add_trace(go.Bar(x=labels,y=idiov,name="Idiosyncratic (α+resid)",marker_color=YELLOW))
            base_layout(bar,f"{ylabel} — return attribution by horizon (annualized for >1Y)","%",h=330)
            bar.update_layout(barmode="relative")
            bar.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
            for i,l in enumerate(labels):
                bar.add_annotation(x=l,y=totv[i],text=f"{totv[i]:+.0f}%",showarrow=False,
                                   yshift=11 if totv[i]>=0 else -13,font=dict(size=11,color=TEXT1))
            st.plotly_chart(bar, use_container_width=True, key="reg_attr_bar")
            # Companion: share of return (each bar sums to 100%)
            pf=[(facv[i]/totv[i]*100 if abs(totv[i])>1e-9 else 0.0) for i in range(len(labels))]
            pi=[(idiov[i]/totv[i]*100 if abs(totv[i])>1e-9 else 0.0) for i in range(len(labels))]
            pbar=go.Figure()
            pbar.add_trace(go.Bar(x=labels,y=pf,name="From Beta(s) %",marker_color=BLUE,
                text=[f"{v:.0f}%" for v in pf],textposition="inside",insidetextanchor="middle"))
            pbar.add_trace(go.Bar(x=labels,y=pi,name="Idiosyncratic %",marker_color=YELLOW,
                text=[f"{v:.0f}%" for v in pi],textposition="inside",insidetextanchor="middle"))
            base_layout(pbar,f"{ylabel} — share of return (Beta(s) vs idiosyncratic = 100%)","%",h=300)
            pbar.update_layout(barmode="relative")
            pbar.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
            pbar.add_hline(y=100,line=dict(color=TEXT3,dash="dot"))
            st.plotly_chart(pbar, use_container_width=True, key="reg_attr_share")
            atab=pd.DataFrame({"Horizon":labels,"Total %":[round(x,1) for x in totv],
                               "From Beta(s) %":[round(x,1) for x in facv],
                               "Idiosyncratic %":[round(x,1) for x in idiov],
                               "Beta share %":[round(x,1) for x in pf],
                               "Idiosyncratic share %":[round(x,1) for x in pi]})
            st.caption("Top bars = total return split into **Beta-driven** (β·X, blue) and **idiosyncratic** "
                       "(α + residual, yellow); label is the total. **1M and 1Y are the raw period return; "
                       "3Y/5Y/10Y/Full are annualized.** Bottom bars = the same split as a **share of total "
                       "(sums to 100%)**. When Beta and idiosyncratic returns have opposite signs, a share can "
                       "exceed 100% while the other goes negative (they still net to 100%). Horizons longer "
                       "than the loaded history are skipped.")
            dl(atab, "Export attribution", "JAWS_regression_attribution.xlsx", "reg_attr_dl")

            # ── Per-factor breakout: return contribution & risk (variance) contribution ──
            import numpy as np
            hz_lbls=[]; ret_by={c:[] for c in cols}; ret_idio=[]
            rsk_by={c:[] for c in cols}; rsk_idio=[]
            vol_by={c:[] for c in cols}; vol_idio=[]; vol_tot=[]
            for hlbl,N in hz:
                sub=frame if N is None else (frame.iloc[-N:] if (N is not None and N<=len(frame)) else None)
                if sub is None or len(sub)<3: continue
                hz_lbls.append(hlbl)
                ysub=sub["__Y__"].values; Xsub=sub[cols].values
                ann=ppy/len(sub) if len(sub)>ppy else 1.0
                fac_tot=0.0
                for j,c in enumerate(cols):
                    contrib=float((Xsub[:,j]*beta[j+1]).sum())
                    ret_by[c].append(contrib*ann*100); fac_tot+=contrib
                ret_idio.append((float(ysub.sum())-fac_tot)*ann*100)
                resid=ysub-(beta[0]+Xsub@beta[1:])
                parts={c:float(beta[j+1]*np.cov(ysub,Xsub[:,j],ddof=1)[0,1]) for j,c in enumerate(cols)}
                iv=float(np.var(resid,ddof=1)); tot=sum(parts.values())+iv
                if abs(tot)<1e-12: tot=1.0
                vol_ann=float(np.std(ysub,ddof=1))*np.sqrt(ppy)*100     # annualized vol of Y (%)
                vol_tot.append(vol_ann)
                for c in cols:
                    share=parts[c]/tot                                  # share of variance
                    rsk_by[c].append(share*100); vol_by[c].append(share*vol_ann)
                rsk_idio.append(iv/tot*100); vol_idio.append((iv/tot)*vol_ann)
            if hz_lbls:
                def _stacked(series_map, idio_vals, title, ysuf, key, tots=None, hundred=False):
                    fg=go.Figure()
                    for j,c in enumerate(cols):
                        fg.add_trace(go.Bar(x=hz_lbls,y=series_map[c],name=c,marker_color=PALETTE[j%len(PALETTE)]))
                    fg.add_trace(go.Bar(x=hz_lbls,y=idio_vals,name="Idiosyncratic",marker_color=TEXT3))
                    base_layout(fg,title,ysuf,h=340); fg.update_layout(barmode="relative")
                    fg.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
                    if hundred: fg.add_hline(y=100,line=dict(color=TEXT3,dash="dot"))
                    if tots:
                        for i,l in enumerate(hz_lbls):
                            fg.add_annotation(x=l,y=tots[i],text=f"{tots[i]:.1f}%",showarrow=False,
                                              yshift=10,font=dict(size=10,color=TEXT1))
                    st.plotly_chart(fg, use_container_width=True, key=key)
                _stacked(ret_by, ret_idio, f"{ylabel} — return contribution by factor (annualized >1Y)","%","reg_attr_byfac")
                _stacked(rsk_by, rsk_idio, f"{ylabel} — contribution to risk (variance %)","%","reg_attr_risk", hundred=True)
                _stacked(vol_by, vol_idio, f"{ylabel} — contribution to volatility (annualized %)","%","reg_attr_vol", tots=vol_tot)
                st.caption("**Return contribution** (top): each factor's βᵢ·Xᵢ per horizon + idiosyncratic → sums to "
                           "total return. **Risk (variance %)** (middle): each factor's share of total variance "
                           "(βᵢ·Cov(Y,Xᵢ)), normalized to 100%. **Volatility (bottom):** the same risk shares scaled by "
                           "the annualized vol so the bars sum to Y's annualized vol (e.g. a factor that is 50% of risk "
                           "on 15% vol = 7.5%). Stepwise is on by default to keep the breakout readable.")

        # ── Rolling beta & p-value (own choice menu) ──
        st.divider()
        st.markdown(f'<span style="color:{TEXT2};font-family:Consolas;font-size:12px;">'
                    'Rolling beta &amp; p-value — pick X &amp; Y, window, and time frame</span>',
                    unsafe_allow_html=True)
        rb1,rb2=st.columns(2)
        bx=rb1.text_input("X (ticker / FRED id)", "SPY", key="reg_rbx").strip()
        by=rb2.text_input("Y (ticker / FRED id)", "AGG", key="reg_rby").strip()
        unitf="months" if freq=="Monthly" else "days"
        rb3,rb4,rb5=st.columns([1,1,1])
        w=int(rb3.number_input(f"Rolling window ({unitf})", min_value=3, max_value=2000,
                               value=(24 if freq=="Monthly" else 120), step=1, key="reg_rw"))
        bs=rb4.date_input("Series start", value=date.today()-relativedelta(years=10),
                          min_value=date(1950,1,1), key="reg_rbs")
        be=rb5.date_input("Series end", value=date.today(), key="reg_rbe")
        bb1,bb2=st.columns(2)
        beta_avg=bb1.checkbox("Beta: show average", value=True, key="reg_rb_avg")
        beta_sd=bb2.checkbox("Beta: show ±2σ bands", value=True, key="reg_rb_sd")
        for lbl,sym in [("X",bx),("Y",by)]:
            if sym:
                nm,px=resolve_ticker(sym)
                col = GREEN if (nm or px) else YELLOW
                txtc = f"{nm or 'found'}" if (nm or px) else "trying as FRED id"
                st.markdown(f'<span style="color:{col};font-size:12px;">'
                            f'{"✅" if (nm or px) else "⚠"} {lbl}: {sym.upper()} — {txtc}</span>',
                            unsafe_allow_html=True)
        if not bx or not by or bx.upper()==by.upper():
            st.caption("Enter two different series for rolling beta."); return
        sxx=_corr_change_series("auto", bx, freq); syy=_corr_change_series("auto", by, freq)
        blo=pd.Timestamp(bs); bhi=pd.Timestamp(be)
        if sxx is not None: sxx=sxx[(sxx.index>=blo)&(sxx.index<=bhi)]
        if syy is not None: syy=syy[(syy.index>=blo)&(syy.index<=bhi)]
        rdf=pd.concat([sxx.rename("x"),syy.rename("y")],axis=1,join="inner").dropna() \
            if (sxx is not None and syy is not None) else pd.DataFrame()
        if len(rdf) <= w:
            st.caption(f"Need more than {w} overlapping points — widen the time frame "
                       f"or shrink the window."); return
        xv=rdf["x"].values; yv=rdf["y"].values; idx=rdf.index
        betas=[]; pvals=[]; rix=[]
        for i in range(w, len(rdf)+1):
            lr_w=stats.linregress(xv[i-w:i], yv[i-w:i])
            betas.append(lr_w.slope); pvals.append(lr_w.pvalue); rix.append(idx[i-1])
        rb=pd.Series(betas,index=rix); rp=pd.Series(pvals,index=rix)
        unit="mo" if freq=="Monthly" else "d"
        xlbl=bx.upper(); ylbl=by.upper()
        bcol,pcol=st.columns(2)
        with bcol:
            bf=go.Figure()
            bf.add_trace(go.Scatter(x=rb.index,y=rb.values,mode="lines",line=dict(color=ACCENT,width=1.6)))
            if beta_avg:
                bf.add_hline(y=float(rb.mean()),line=dict(color=BLUE,dash="dot"),
                             annotation_text=f"avg {float(rb.mean()):.2f}")
            if beta_sd:
                _bmu=float(rb.mean()); _bsd=float(rb.std())
                bf.add_hline(y=_bmu+2*_bsd,line=dict(color=RED,dash="dash"),annotation_text="+2σ")
                bf.add_hline(y=_bmu-2*_bsd,line=dict(color=GREEN,dash="dash"),annotation_text="-2σ")
            bf.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
            base_layout(bf,f"Rolling {w}{unit} Beta · {ylbl} on {xlbl}  (now {rb.iloc[-1]:.2f})",h=290)
            st.plotly_chart(bf, use_container_width=True, key="reg_rbeta")
        with pcol:
            pf=go.Figure()
            pf.add_trace(go.Scatter(x=rp.index,y=rp.values,mode="lines",
                line=dict(color=YELLOW,width=1.6)))
            pf.add_hline(y=0.05,line=dict(color=GREEN,dash="dash"),annotation_text="0.05 sig")
            pf.add_hline(y=0.01,line=dict(color=GREEN,dash="dot"),annotation_text="0.01")
            base_layout(pf,f"Rolling {w}{unit} p-value  (now {rp.iloc[-1]:.4f})",h=320)
            # extend axis a little below 0 so near-zero (highly significant) values
            # are clearly visible instead of pinned to the bottom edge
            top=min(1.0, max(0.15, float(rp.max())*1.1))
            pf.update_yaxes(range=[-0.03, top])
            st.plotly_chart(pf, use_container_width=True, key="reg_rp")
        rolldf=pd.DataFrame({"Date":rb.index,"Beta":rb.values,"p_value":rp.values})
        dl(rolldf, "Export rolling beta/p-value", "JAWS_rolling_regression.xlsx", "reg_roll_dl")

# ════════════════════════════════════════════════════════════════
# BULK DATA EXPORTER
# ════════════════════════════════════════════════════════════════
@st.cache_data(ttl=1800, show_spinner=False)
def tool_series_catalog():
    """Named time-series from the tool itself → {label: (kind, (dates, values))}.
    kind 'factor' = decimal periodic returns; kind 'level' = level series (already scaled)."""
    cat={}
    try:
        fd=factor_data()
        for sect in ("daily","monthly"):
            for r in fd.get(sect,[]):
                if r.get("error"): continue
                cat[f"Factor: {r['name']} ({'D' if r['is_daily'] else 'M'})"]=(
                    "factor",(r["raw_dates"], r["raw_rets"]))
    except Exception: pass
    for loader,pfx in [(spreads_analytics,"Spread"),(rates_analytics,"Rate"),
                       (funding_analytics,"Funding"),(inflation_analytics,"Inflation")]:
        try:
            for r in loader():
                if r.get("error") or not r.get("raw_dates"): continue
                cat[f"{pfx}: {r['name']}"]=("level",(r["raw_dates"], r["raw_values"]))
        except Exception: pass
    return cat

# ════════════════════════════════════════════════════════════════
# CORRELATION MATRIX
# ════════════════════════════════════════════════════════════════
@st.cache_data(ttl=900, show_spinner=False)
def seg_catalog():
    import market_data as md
    return {"Equity Indices":dict(md.INDICES),"Volatility & Correlation":dict(md.VOLATILITY),
            "FX":dict(md.FX),"Fixed Income":dict(md.FIXED_INCOME),"Municipals":dict(md.MUNIS),
            "Factor ETFs":dict(md.FACTORS),"Commodities":dict(md.COMMODITIES),"US Sectors":dict(md.SECTORS),
            "Hedge Funds":dict(getattr(md,"HEDGE_FUNDS",{})),
            "Risk Premia":dict(getattr(md,"RISK_PREMIA",{})),
            "AQR Strategies":dict(getattr(md,"AQR_FUNDS",{})),
            "Crypto":dict(getattr(md,"CRYPTO",{}))}

def _corr_change_series(kind, payload, freq):
    """Return a period-change series (returns for prices/factors, diff for levels)."""
    import fi_spreads as fs
    s=None
    if isinstance(payload,str) and payload.startswith("FRED:"):
        kind="level_series"                  # macro pseudo-instrument → diff, not pct
        s=md_history(payload)
    elif kind=="ticker":
        s=md_history(payload)
    elif kind=="auto":                       # individual entry: ticker, else FRED
        s=md_history(payload)
        if s is None or s.empty:
            d,v=fs._fred_fetch_all(payload)
            if d: s=pd.Series(v,index=pd.to_datetime(d)); kind="level"
    elif kind=="level":
        d,v=payload; s=pd.Series(v,index=pd.to_datetime(d))
    elif kind=="factor":
        d,v=payload; s=pd.Series(v,index=pd.to_datetime(d))
    if s is None or len(s)==0: return None
    s=s.sort_index()
    if kind=="factor":
        if freq=="Monthly": s=(1+s).resample("ME").prod()-1
        return s.dropna()                    # periodic return (corr is scale-invariant)
    if freq=="Monthly": s=s.resample("ME").last()
    chg = s.diff() if kind in ("level","level_series") else s.pct_change()
    return chg.dropna()

def panel_corr():
    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<span class="jaws-logo" style="font-size:16px;padding:3px 10px;">CORR</span> '
                    '<span class="jaws-title" style="font-size:15px;">Correlation Matrix</span> '
                    '<span class="jaws-sub">returns/changes · green = low, red = high</span>',
                    unsafe_allow_html=True)
        c1,c2,c3=st.columns([1,1,1])
        freq=c1.radio("Frequency",["Monthly","Daily"],horizontal=True,key="corr_freq")
        start=c2.date_input("Start", value=date.today()-relativedelta(years=3),
                            min_value=date(1950,1,1), key="corr_start")
        end=c3.date_input("End", value=date.today(), key="corr_end")

        segs=seg_catalog()
        seg_pick=st.multiselect("Add whole table segments", list(segs.keys()),
                                default=["FX"], key="corr_segs")
        catalog=tool_series_catalog()
        tool_pick=st.multiselect("Add factors · spreads · rates · funding",
                                 list(catalog.keys()), key="corr_tools")
        if "corr_syms" not in st.session_state: st.session_state["corr_syms"]=[]
        if _HAS_SEARCHBOX:
            sel=st_searchbox(search_instruments, placeholder="Search & add an individual ticker…",
                             key="corr_sb")
            if sel and sel not in st.session_state["corr_syms"]:
                st.session_state["corr_syms"].append(sel)
        import re as _re
        paste=st.text_input("…or paste tickers/IDs (comma separated)", "", key="corr_paste")
        pasted=[t.strip() for t in _re.split(r"[,\s]+", paste) if t.strip()]

        if st.button("Clear selections", key="corr_clear"):
            st.session_state["corr_syms"]=[]; st.rerun()

        # ── assemble selected items: label -> (kind, payload) ──
        items={}
        for seg in seg_pick:
            for name,sym in segs[seg].items(): items[name]=("ticker",sym)
        for t in tool_pick:
            kind,payload=catalog[t]; items[t.split(": ",1)[-1]]=(kind,payload)
        for sym in list(dict.fromkeys(st.session_state["corr_syms"]+pasted)):
            items[sym]=("auto",sym)
        if len(items)<2:
            st.info("Add at least 2 series (segments, factors, or tickers) to build the matrix.")
            return
        if len(items)>45:
            st.warning(f"{len(items)} series selected — showing first 45 for readability.")
            items=dict(list(items.items())[:45])

        lo=pd.Timestamp(start); hi=pd.Timestamp(end)
        cols={}
        with st.spinner(f"Building {freq.lower()} correlation for {len(items)} series…"):
            for label,(kind,payload) in items.items():
                s=_corr_change_series(kind,payload,freq)
                if s is None or s.empty: continue
                s=s[(s.index>=lo)&(s.index<=hi)]
                if len(s)>=3: cols[label]=s
        if len(cols)<2:
            st.warning("Not enough overlapping data — widen the date range."); return
        df=pd.concat(cols, axis=1, sort=True)
        corr=df.corr()                       # pairwise complete observations
        labels=list(corr.columns); n=len(labels)
        import numpy as np
        vals=corr.values                     # correlations (-1..1), shown as 2-dp decimals
        fsize=11 if n<=14 else (9 if n<=22 else 7)
        # Mask the diagonal (self-correlation = 1.00): no color, no number → black
        z=vals.astype(float).copy()
        np.fill_diagonal(z, np.nan)
        txt=np.empty((n,n), dtype=object)
        for i in range(n):
            for j in range(n):
                txt[i,j]="" if i==j else f"{vals[i,j]:.2f}"
        fig=go.Figure(go.Heatmap(
            z=z, x=labels, y=labels, zmin=-1, zmax=1,
            # Excel-style 3-colour scale: green (low) → yellow → red (high)
            colorscale=[[0.0,"#63be7b"],[0.5,"#ffeb84"],[1.0,"#f8696b"]],
            showscale=False, xgap=1, ygap=1, hoverongaps=False,
            text=txt, texttemplate="%{text}",
            textfont=dict(size=fsize, color="#1a1a1a")))
        fig.update_layout(template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=BG,
            height=max(420, 30*n+150), margin=dict(l=10,r=10,t=34,b=10),
            font=dict(family="Consolas", color=TEXT2, size=10),
            title=dict(text=f"{freq} return correlation · {df.index[0].date()} → {df.index[-1].date()}",
                       font=dict(size=13)))
        fig.update_xaxes(side="top", tickangle=-90, tickfont=dict(size=10,color=TEXT1))
        fig.update_yaxes(autorange="reversed", tickfont=dict(size=10,color=TEXT1))
        st.plotly_chart(fig, use_container_width=True, key="corr_chart")
        out=corr.copy(); out.insert(0,"Series",out.index)
        dl(out, "Export matrix", "JAWS_correlation.xlsx", "corr_dl")

        # ── Rolling correlation between two chosen series ──
        st.divider()
        st.markdown(f'<span style="color:{TEXT2};font-family:Consolas;font-size:12px;">'
                    'Rolling correlation — pick two series, window, and time frame</span>',
                    unsafe_allow_html=True)
        # Standalone pair (any ticker / FRED id) — defaults SPY vs AGG, 6-mo, 10yr
        rc1,rc2=st.columns(2)
        a=rc1.text_input("Series A (ticker / FRED id)", "SPY", key="corr_a").strip()
        b=rc2.text_input("Series B (ticker / FRED id)", "AGG", key="corr_b").strip()
        unit="months" if freq=="Monthly" else "days"
        rc3,rc4,rc5=st.columns([1,1,1])
        win=rc3.number_input(f"Rolling window ({unit})", min_value=2, max_value=2000,
                             value=(6 if freq=="Monthly" else 90), step=1, key="corr_win")
        rs=rc4.date_input("Series start", value=date.today()-relativedelta(years=10),
                          min_value=date(1950,1,1), key="corr_rstart")
        re_=rc5.date_input("Series end", value=date.today(), key="corr_rend")
        rcb1,rcb2=st.columns(2)
        rc_avg=rcb1.checkbox("Show average", value=True, key="corr_roll_avg")
        rc_sd=rcb2.checkbox("Show ±2σ bands", value=True, key="corr_roll_sd")
        # live confirmation
        for lbl,sym in [("A",a),("B",b)]:
            if sym:
                nm,px=resolve_ticker(sym)
                if nm or px:
                    st.markdown(f'<span style="color:{GREEN};font-size:12px;">✅ {lbl}: {sym.upper()} — '
                                f'{nm or "found"}</span>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span style="color:{YELLOW};font-size:12px;">⚠ {lbl}: {sym.upper()} '
                                f'— trying as FRED id</span>', unsafe_allow_html=True)
        if not a or not b or a.upper()==b.upper():
            st.caption("Enter two different series for a rolling correlation.")
        else:
            sa=_corr_change_series("auto", a, freq); sb=_corr_change_series("auto", b, freq)
            rlo=pd.Timestamp(rs); rhi=pd.Timestamp(re_)
            if sa is not None: sa=sa[(sa.index>=rlo)&(sa.index<=rhi)]
            if sb is not None: sb=sb[(sb.index>=rlo)&(sb.index<=rhi)]
            pair=pd.concat([sa.rename("a"),sb.rename("b")],axis=1,join="inner").dropna() \
                 if (sa is not None and sb is not None) else pd.DataFrame()
            roll=pair["a"].rolling(int(win)).corr(pair["b"]).dropna() if not pair.empty else pd.Series(dtype=float)
            if roll.empty:
                st.caption("Not enough overlapping data for that window / time frame.")
            else:
                rfig=go.Figure()
                rfig.add_trace(go.Scatter(x=roll.index,y=roll.values,mode="lines",
                    line=dict(color=ACCENT,width=1.6)))
                rfig.add_hline(y=0,line=dict(color=TEXT3,dash="dash"))
                if rc_avg:
                    rfig.add_hline(y=float(roll.mean()),line=dict(color=BLUE,dash="dot"),
                                   annotation_text=f"avg {float(roll.mean()):.2f}")
                if rc_sd:
                    _mu=float(roll.mean()); _sd=float(roll.std())
                    rfig.add_hline(y=_mu+2*_sd,line=dict(color=RED,dash="dash"),annotation_text="+2σ")
                    rfig.add_hline(y=_mu-2*_sd,line=dict(color=GREEN,dash="dash"),annotation_text="-2σ")
                base_layout(rfig,f"Rolling {win}-{'mo' if freq=='Monthly' else 'd'} correlation · "
                            f"{a} vs {b}  (now {roll.iloc[-1]:+.2f})", h=300)
                rfig.update_yaxes(range=[-1,1])
                st.plotly_chart(rfig, use_container_width=True, key="corr_roll")
                rdf=pd.DataFrame({"Date":roll.index,"RollingCorr":roll.values})
                dl(rdf, "Export rolling corr", "JAWS_rolling_corr.xlsx", "corr_roll_dl")

def panel_exporter():
    import re as _re
    st.markdown('<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<span class="jaws-logo" style="font-size:16px;padding:3px 10px;">DATA</span> '
                    '<span class="jaws-title" style="font-size:15px;">Bulk Data Export</span> '
                    '<span class="jaws-sub">add any tickers / FRED IDs → download prices or returns</span>',
                    unsafe_allow_html=True)
        if "exp_syms" not in st.session_state: st.session_state["exp_syms"]=[]
        if _HAS_SEARCHBOX:
            sel=st_searchbox(search_instruments, placeholder="Type to search & add a ticker…", key="exp_sb")
            if sel and sel not in st.session_state["exp_syms"]:
                st.session_state["exp_syms"].append(sel)
        paste=st.text_area("Or paste tickers / FRED IDs (comma, space, or new-line separated)", "",
                           key="exp_paste", height=70,
                           placeholder="e.g.  SPY, QQQ, AAPL, ^TNX, BAA10Y, CL=F")
        pasted=[t.strip() for t in _re.split(r"[,\s]+", paste) if t.strip()]
        syms=list(dict.fromkeys(st.session_state["exp_syms"]+pasted))

        # Tool's own named series: L/S factors, spreads, rates, funding
        catalog=tool_series_catalog()
        tool_pick=st.multiselect("Add tool series — L/S factors · spreads · rates · funding",
                                 list(catalog.keys()), key="exp_tool")

        c1,c2,c3,c4=st.columns(4)
        freq=c1.radio("Frequency",["Daily","Monthly"],horizontal=True,key="exp_freq")
        dtp =c2.radio("Data",["Prices","Returns"],horizontal=True,key="exp_dt")
        start=c3.date_input("Start", value=date.today()-relativedelta(years=5),
                            min_value=date(1950,1,1), key="exp_start")
        end =c4.date_input("End", value=date.today(), key="exp_end")
        # Price basis toggle (returns are always total-return / adjusted)
        if dtp=="Prices":
            basis=st.radio("Price basis",
                           ["Adjusted (total return)","Actual (unadjusted)"],
                           horizontal=True, key="exp_basis")
            adjusted = basis.startswith("Adjusted")
        else:
            adjusted = True   # total-return basis for returns

        cc1,cc2=st.columns([1,4])
        if cc1.button("Clear added", key="exp_clear"):
            st.session_state["exp_syms"]=[]; st.rerun()
        total=len(syms)+len(tool_pick)
        cc2.caption(f"Series queued ({total}): " +
                    (", ".join(syms+tool_pick) if total else "none — add some above"))
        if total==0:
            return

        lo=pd.Timestamp(start); hi=pd.Timestamp(end)
        cols={}; missing=[]
        with st.spinner(f"Building {freq.lower()} {dtp.lower()} for {total} series…"):
            # 1) tickers / FRED IDs
            for sym in syms:
                s=md_history(sym, adjusted=adjusted)
                if s is None or s.empty:           # fall back to FRED for economic IDs
                    import fi_spreads as fs
                    d,v=fs._fred_fetch_all(sym)
                    if d: s=pd.Series(v, index=pd.to_datetime(d))
                if s is None or s.empty:
                    missing.append(sym); continue
                s=s.sort_index()
                if freq=="Monthly": s=s.resample("ME").last()
                if dtp=="Returns":  s=s.pct_change()*100
                s=s[(s.index>=lo)&(s.index<=hi)]
                if not s.empty: cols[sym]=s
            # 2) tool series (factors / spreads / rates / funding)
            for label in tool_pick:
                kind,(d,v)=catalog[label]
                s=pd.Series(v, index=pd.to_datetime(d)).sort_index().dropna()
                if kind=="factor":                 # values are decimal returns
                    if freq=="Monthly": s=(1+s).resample("ME").prod()-1
                    s=((1+s).cumprod()*100) if dtp=="Prices" else (s*100)
                else:                              # level series (spreads/rates/funding)
                    if freq=="Monthly": s=s.resample("ME").last()
                    if dtp=="Returns": s=s.pct_change()*100
                s=s[(s.index>=lo)&(s.index<=hi)].dropna()
                if not s.empty: cols[label]=s
        if missing:
            st.warning("No data found for: " + ", ".join(missing))
        if not cols:
            st.info("Nothing to export yet."); return
        df=pd.concat(cols, axis=1, sort=True).dropna(how="all")
        df.insert(0,"Date",df.index)
        st.dataframe(df.tail(12), use_container_width=True, height=240, hide_index=True)
        st.caption(f"{len(df)} rows × {len(cols)} series · {freq.lower()} {dtp.lower()} · "
                   f"{df['Date'].iloc[0].date()} → {df['Date'].iloc[-1].date()}")
        rmode = (dtp=="Returns")
        e1,e2=st.columns(2)
        with e1:
            st.download_button("⬇ Download Excel",
                export_series_xlsx(df, rmode),
                f"JAWS_export_{freq.lower()}_{dtp.lower()}.xlsx", key="exp_xls",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with e2:
            csv_df=df.copy()
            csv_df["Date"]=pd.to_datetime(csv_df["Date"]).dt.strftime("%m/%d/%Y")
            st.download_button("⬇ Download CSV", csv_df.to_csv(index=False).encode(),
                f"JAWS_export_{freq.lower()}_{dtp.lower()}.csv", "text/csv", key="exp_csv")

# ── Slot dispatcher ─────────────────────────────────────────────
RETURN_CATS={"Equity Indices":"indices","Volatility & Correlation":"volatility","FX":"fx",
             "Fixed Income":"fixed_income","Municipals":"munis","Factor ETFs":"factors",
             "Commodities":"commodities","US Sectors":"sectors","Hedge Funds":"hedge_funds",
             "Risk Premia":"risk_premia","AQR Strategies":"aqr","Crypto":"crypto"}
# Tabs shown above each quadrant (radio = lazy: only the selected one loads).
TABLE_TABS=["Watchlist","Custom Data"]+list(RETURN_CATS.keys())+["FI Spreads","Rates","Funding","Inflation","L/S Factors","Valuation"]
PANEL_TABS=["Yield Curve","Chart","Realized Vol","Scanner","News"]

def _dispatch(sel, k):
    if sel in RETURN_CATS:    panel_returns(RETURN_CATS[sel], sel, k)
    elif sel=="FI Spreads":   panel_analytics(spreads_analytics,"Spreads","JAWS_FI_Spreads.xlsx",k)
    elif sel=="Rates":        panel_analytics(rates_analytics,"Rates","JAWS_Rates.xlsx",k)
    elif sel=="Funding":      panel_analytics(funding_analytics,"Funding","JAWS_Funding.xlsx",k)
    elif sel=="Inflation":    panel_analytics(inflation_analytics,"Inflation","JAWS_Inflation.xlsx",k)
    elif sel=="L/S Factors":  panel_factors(k)
    elif sel=="Valuation":    panel_valuation(k)
    elif sel=="Yield Curve":  panel_yield(k)
    elif sel=="Chart":        panel_chart(k)
    elif sel=="Realized Vol": panel_rvol(k)
    elif sel=="Scanner":      panel_scanner(k)
    elif sel=="News":         panel_news(k)
    elif sel=="Watchlist":    panel_watchlist(k)
    elif sel=="Custom Data":  panel_custom(k)

def render_slot(k, tabs, default):
    # Horizontal radio acts as a tab strip but only renders the selected panel
    sel=st.radio("tabs", tabs, index=tabs.index(default), key=k+"_sel",
                 horizontal=True, label_visibility="collapsed")
    try:
        _dispatch(sel, k)
    except Exception as e:
        import traceback
        st.error(f"⚠ {sel}: {type(e).__name__}: {e}")
        with st.expander("details"):
            st.code(traceback.format_exc())

# Style the radio strips to read like tabs
st.markdown(f"""
<style>
  div[role="radiogroup"] {{ gap:3px !important; flex-wrap:wrap; }}
  div[role="radiogroup"] label {{ background:{CARD2}; border:1px solid {BORDER};
      border-radius:5px 5px 0 0; padding:3px 11px !important; margin:0 !important; }}
  div[role="radiogroup"] label:hover {{ background:{BORDER}; }}
  /* Bright, bold tab text */
  div[role="radiogroup"] label p {{ color:#ffffff !important; font-weight:700 !important;
      font-size:13px !important; }}
  /* Selected tab: accent highlight */
  div[role="radiogroup"] label:has(input:checked) {{ background:{ACCENT}; border-color:{ACCENT}; }}
  div[role="radiogroup"] label:has(input:checked) p {{ color:#0d1117 !important; }}
</style>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════
# TOP BAR + 4-QUADRANT GRID  (top = data tables, bottom = panels)
# ════════════════════════════════════════════════════════════════
def _now_et():
    """Current time in US Eastern (market) time — the server runs in UTC."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return datetime.utcnow()-timedelta(hours=4)   # crude EDT fallback
tb1,tb2,tb3=st.columns([4,1.3,1])
with tb1:
    _ts=_now_et().strftime("%a %b %d, %Y · %I:%M %p ET").replace(" 0"," ").replace("·  ","· ")
    st.markdown('<div class="topbar"><span class="jaws-logo">JAWS</span>'
                '<span class="jaws-title">JW Market &amp; News Monitor</span>'
                f'<span class="jaws-sub">&nbsp;&nbsp;Updated {_ts}</span>'
                '</div>', unsafe_allow_html=True)
with tb2:
    st.markdown("<div style='height:34px'></div>", unsafe_allow_html=True)
    nc=len(custom_store())
    with st.popover(f"⬆ Upload data{f' ({nc})' if nc else ''}", use_container_width=True):
        st.caption("Upload a spreadsheet of time series. **Column 1 = dates**, each other "
                   "column = one identifier (its header becomes the ticker). Series become "
                   "available in every section (chart, correlation, regression, scanner, watchlist…).")
        st.download_button("⬇ Download template (.xlsx)", data=build_upload_template(),
                           file_name="JAWS_upload_template.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           use_container_width=True, key="cust_tmpl",
                           help="Pre-formatted sheet — paste your dates/tickers/values in, then upload.")
        up=st.file_uploader("CSV or Excel (.csv, .xlsx, .xls)", type=["csv","xlsx","xls"], key="cust_up")
        kind=st.radio("Values are", ["Prices","Returns %","Returns (decimal)"],
                      horizontal=True, key="cust_kind",
                      help="Returns are compounded into a price index (base 100) so all tools work.")
        if up is not None and st.button("Add to dashboard", key="cust_add", use_container_width=True):
            try:
                parsed=parse_uploaded_series(up, kind)
                for sym,(nm,px) in parsed.items():
                    custom_store()[sym]={"name":nm,"prices":px}
                st.cache_data.clear()
                st.success(f"Added {len(parsed)}: {', '.join(parsed.keys())}")
                st.rerun()
            except Exception as e:
                st.error(f"Could not parse: {type(e).__name__}: {e}")
with tb3:
    st.markdown("<div style='height:34px'></div>", unsafe_allow_html=True)
    if st.button("↻ Refresh", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    _AUTO_OPTS={"Off":0,"5 min":5,"15 min":15,"30 min":30,"60 min":60}
    auto_choice=st.selectbox("Auto-refresh", list(_AUTO_OPTS), index=2, key="auto_rf",
                             help="Re-pull data on this interval automatically.") \
                if _HAS_AUTOREFRESH else "Off"
_auto_min=_AUTO_OPTS.get(auto_choice,0) if _HAS_AUTOREFRESH else 0
if _auto_min>0:
    # Rerun on the chosen interval; cache TTLs mean data re-fetches when stale.
    try:
        st_autorefresh(interval=_auto_min*60*1000, key="auto_refresh_tick")
    except Exception:
        pass

r1=st.columns(2)
with r1[0]:
    with st.container(border=True): render_slot("q1", TABLE_TABS, "Equity Indices")
with r1[1]:
    with st.container(border=True): render_slot("q2", TABLE_TABS, "Factor ETFs")
import traceback as _tb
def _hdr(tag, title):
    st.markdown(f'<span class="jaws-logo" style="font-size:15px;padding:2px 9px;">{tag}</span> '
                f'<span class="jaws-title" style="font-size:15px;">{title}</span>',
                unsafe_allow_html=True)
def _sec(tag, title, fn, *a):
    with st.container(border=True):
        _hdr(tag, title)
        try: fn(*a)
        except Exception as e:
            st.error(f"⚠ {title}: {type(e).__name__}: {e}")
            with st.expander("details"): st.code(_tb.format_exc())

# ── Half-width grid: curves & rate/vol snapshots right under the two tables ──
_g1=st.columns(2)
with _g1[0]: _sec("CRV","Curves", panel_curves, "q3")
with _g1[1]: _sec("FED","Fed Rate Expectations & Hike/Cut Odds", panel_fed, "secfed")
_g2=st.columns(2)
with _g2[0]:
    _sec("VIXT","VIX Term Structure", panel_vix_term, "secvixt")
    _sec("SKEW","Volatility Skew (protection vs upside)", panel_skew, "secskew")
with _g2[1]: _sec("CURV","Futures Curves & Roll Yield", panel_energy_curve, "secenrg")

# ── Full-width sections (stacked) ──
_sec("STEEP","Term-Structure Steepness (vol & rates)", panel_steepness, "secsteep")
_sec("CROWD","Crowded Positioning (longs & shorts)", panel_crowding, "seccrowd")
_sec("EQFIN","Implied Equity Financing (futures vs SOFR)", panel_eq_financing, "seceqfin")
_sec("SKEWIX","CBOE SKEW Index (tail-risk over time)", panel_skew_index, "secskewix")
_sec("PRED","Prediction Markets (implied odds)", panel_prediction, "secpred")
_sec("M/T","Muni / Treasury Ratio (rich vs cheap)", panel_muni_ratio, "secmt")
_sec("NEWS","Top Stories", panel_news, "q4")
_sec("RRET","Rolling Returns", panel_rolling_returns, "secrr")
_sec("RSHP","Rolling Sharpe Ratio (ex-T-bill)", panel_rolling_sharpe, "secrshp")
_sec("CHRT","Chart", panel_chart, "secchart")
_sec("REL","Relative Performance (A vs B)", panel_outperf, "secrel")
_sec("RVOL","Realized Volatility", panel_rvol, "secrvol")
_sec("SPRD","Commodity Spreads (crack · crush · ratios)", panel_commodity_spreads, "secsprd")
_sec("DISL","Dislocation Scanner", panel_scanner, "secscan")

# Self-headed analytical sections
for _name,_fn in [("Correlation",panel_corr),("Regression",panel_regression),
                  ("Bulk Export",panel_exporter)]:
    try:
        _fn()
    except Exception as _e:
        st.error(f"⚠ {_name}: {type(_e).__name__}: {_e}")
        with st.expander("details"):
            st.code(_tb.format_exc())
