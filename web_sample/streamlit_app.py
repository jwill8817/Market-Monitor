"""
JW Market & News Monitor — full web app (Streamlit).
Reuses the desktop data modules (market_data, fi_spreads, factors_data,
yield_curve, categorized_news) unchanged. Dark Bloomberg theme + Plotly charts.
"""
import os, sys, io
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

# Make repo-root data modules importable when run from web_sample/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

# Bridge Streamlit secrets → environment BEFORE importing data modules
for _k in ("FRED_API_KEY", "NEWS_API_KEY"):
    try:
        if _k in st.secrets:
            os.environ[_k] = str(st.secrets[_k])
    except Exception:
        pass

import pandas as pd
import plotly.graph_objects as go

# ── Theme ───────────────────────────────────────────────────────
BG="#0d1117"; SIDEBAR="#161b22"; CARD="#1c2128"; CARD2="#21262d"; BORDER="#30363d"
ACCENT="#f78166"; BLUE="#58a6ff"; GREEN="#3fb950"; RED="#f85149"
YELLOW="#e3b341"; PURPLE="#bc8cff"; CYAN="#79c0ff"
TEXT1="#e6edf3"; TEXT2="#8b949e"; TEXT3="#484f58"
ROW_A="#1c2128"; ROW_B="#21262d"

st.set_page_config(page_title="JW Market & News Monitor", page_icon="📈",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown(f"""
<style>
  .stApp {{ background:{BG}; color:{TEXT1}; }}
  header[data-testid="stHeader"] {{ background:{BG}; }}
  section[data-testid="stSidebar"] {{ background:{SIDEBAR}; }}
  .block-container {{ padding-top:1.0rem; padding-bottom:1rem; max-width:100%; }}
  h1,h2,h3,h4,h5 {{ color:{TEXT1}; font-family:'Segoe UI',sans-serif; }}
  .jaws-logo {{ background:{ACCENT}; color:{BG}; font-weight:700; font-size:22px;
               padding:6px 16px; border-radius:6px; display:inline-block;
               font-family:Consolas,monospace; letter-spacing:1px; }}
  .jaws-sub {{ color:{TEXT2}; font-family:Consolas,monospace; font-size:13px; }}
  table.jaws {{ width:100%; border-collapse:collapse; font-family:Consolas,monospace; font-size:13px; }}
  table.jaws th {{ background:{CARD2}; color:{TEXT2}; text-align:right; padding:7px 9px;
                  border-bottom:1px solid {BORDER}; position:sticky; top:0; }}
  table.jaws th:first-child {{ text-align:left; }}
  table.jaws td {{ padding:6px 9px; border-bottom:1px solid {BORDER}; text-align:right; color:{TEXT1};
                  white-space:nowrap; }}
  table.jaws td:first-child {{ text-align:left; }}
  table.jaws tr:nth-child(even) td {{ background:{CARD2}; }}
  table.jaws tr:nth-child(odd)  td {{ background:{CARD}; }}
  .jaws-cat {{ background:#161b22; color:{ACCENT}; font-family:Consolas; font-weight:700;
              padding:5px 9px; font-size:12px; }}
  .tbl-wrap {{ max-height:460px; overflow:auto; border:1px solid {BORDER}; border-radius:6px; }}
  div[data-testid="stMetricValue"] {{ font-family:Consolas; }}
</style>
""", unsafe_allow_html=True)

# ── Auth ────────────────────────────────────────────────────────
def _auth():
    try:    pw = st.secrets.get("app_password", "jaws2026")
    except Exception: pw = "jaws2026"
    if st.session_state.get("auth_ok"): return True
    st.markdown('<span class="jaws-logo">JAWS</span> '
                '<span class="jaws-sub">JW Market &amp; News Monitor</span>',
                unsafe_allow_html=True); st.write("")
    e = st.text_input("Enter access password", type="password")
    if e:
        if e == pw: st.session_state["auth_ok"]=True; st.rerun()
        else: st.error("Incorrect password")
    return False
if not _auth(): st.stop()

# ── Formatting ──────────────────────────────────────────────────
def f_pct(v):
    if v is None: return f'<span style="color:{TEXT3}">—</span>'
    c = GREEN if v>=0 else RED
    return f'<span style="color:{c}">{"+" if v>=0 else ""}{v:.2f}%</span>'

def f_abs(v):  # absolute change (rates/funding return cols)
    if v is None: return f'<span style="color:{TEXT3}">—</span>'
    c = GREEN if v>=0 else RED
    return f'<span style="color:{c}">{"+" if v>=0 else ""}{v:.2f}</span>'

def f_price(v, name=""):
    if v is None: return "—"
    if any(x in name for x in ["EUR/","GBP/","AUD/","JPY","CNY","MXN","CAD","CHF"]): return f"{v:,.4f}"
    if v < 10: return f"{v:.4f}"
    if v < 1000: return f"{v:,.2f}"
    return f"{v:,.0f}"

def z_color(z):
    if z is None: return TEXT2
    if z>2: return RED
    if z>1: return YELLOW
    if z<-1: return GREEN
    return TEXT2

# ── Cached data loaders ─────────────────────────────────────────
@st.cache_data(ttl=900, show_spinner=False)
def md_returns(key, absolute=False, custom_start=None):
    import market_data as md
    dmap = {"indices":md.INDICES,"volatility":md.VOLATILITY,"fx":md.FX,
            "fixed_income":md.FIXED_INCOME,"munis":md.MUNIS,"factors":md.FACTORS,
            "commodities":md.COMMODITIES,"sectors":md.SECTORS,"rates":md.RATES,
            "funding":md.FUNDING}
    cs = pd.Timestamp(custom_start).date() if custom_start else None
    return md.fetch_returns(dmap[key], custom_start=cs, absolute=absolute), dmap[key]

@st.cache_data(ttl=900, show_spinner=False)
def md_history(sym, start=None):
    import market_data as md
    return md.price_history(sym, start=start)

@st.cache_data(ttl=1800, show_spinner=False)
def spreads_analytics(): import fi_spreads; return fi_spreads.fetch_spread_analytics()
@st.cache_data(ttl=1800, show_spinner=False)
def rates_analytics():   import fi_spreads; return fi_spreads.fetch_rates_analytics()
@st.cache_data(ttl=1800, show_spinner=False)
def funding_analytics(): import fi_spreads; return fi_spreads.fetch_funding_analytics()
@st.cache_data(ttl=3600, show_spinner=False)
def factor_data(cs=None, ce=None):
    import factors_data as fd
    return fd.fetch_factors(custom_start=cs, custom_end=ce)
@st.cache_data(ttl=3600, show_spinner=False)
def news_data():
    from categorized_news import fetch_all_news_categorized
    return fetch_all_news_categorized()

NEWS_WEIGHT={"bloomberg":10,"wsj":9,"wall street journal":9,"reuters":8,
             "financial times":8,"ft":8,"cnbc":7,"yahoo finance":6,
             "seeking alpha":5,"zero hedge":4}
CAT_LABELS={"hedge_fund":"HF","ipo":"IPO","ma":"M&A","issuance":"ISS"}
CAT_COLORS={"hedge_fund":CYAN,"ipo":GREEN,"ma":YELLOW,"issuance":PURPLE}

# ── Generic table renderers ─────────────────────────────────────
RET_HDR = ["Name","Ticker","Price","1D%","MTD%","YTD%","1Y%","3Y%","5Y%","10Y%","Custom%"]

def returns_table_html(data, tmap, absolute=False):
    fc = f_abs if absolute else f_pct
    h = '<div class="tbl-wrap"><table class="jaws"><tr>'+ "".join(f"<th>{c}</th>" for c in RET_HDR)+"</tr>"
    for name, info in data.items():
        r = info.get("returns",{}); sym=tmap.get(name,"—")
        h += ("<tr>"
              f"<td>{name}</td><td>{sym}</td><td>{f_price(info.get('price'),name)}</td>"
              f"<td>{fc(info.get('change_1d'))}</td><td>{fc(r.get('MTD'))}</td>"
              f"<td>{fc(r.get('YTD'))}</td><td>{fc(r.get('1Y'))}</td><td>{fc(r.get('3Y'))}</td>"
              f"<td>{fc(r.get('5Y'))}</td><td>{fc(r.get('10Y'))}</td><td>{fc(r.get('Custom'))}</td></tr>")
    return h+"</table></div>"

def returns_to_df(data, tmap, absolute=False):
    rows=[]
    for name,info in data.items():
        r=info.get("returns",{})
        rows.append({"Name":name,"Ticker":tmap.get(name,""),"Price":info.get("price"),
            "1D":info.get("change_1d"),"MTD":r.get("MTD"),"YTD":r.get("YTD"),"1Y":r.get("1Y"),
            "3Y":r.get("3Y"),"5Y":r.get("5Y"),"10Y":r.get("10Y"),"Custom":r.get("Custom")})
    return pd.DataFrame(rows)

ANA_HDR=["Name","Unit","Current","1M","3M","1Y","3Y","5Y","10Y","Min","Max","Z-Score"]
def analytics_table_html(rows):
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in ANA_HDR)+"</tr>"
    cats={}
    for r in rows: cats.setdefault(r.get("category",""),[]).append(r)
    for cat,crows in cats.items():
        h+=f'<tr><td class="jaws-cat" colspan="{len(ANA_HDR)}">{cat}</td></tr>'
        for r in crows:
            if r.get("error"): continue
            dec=r.get("decimals",0); unit=r.get("unit","")
            def fn(v):
                if v is None: return f'<span style="color:{TEXT3}">—</span>'
                return f"{v:.{dec}f}"
            z=r.get("z_score"); hh=r.get("hist",{})
            zc=z_color(z); zt=f'{z:+.2f}σ' if z is not None else "—"
            h+=("<tr>"
                f"<td>{r['name']}</td><td style='color:{TEXT3}'>{unit}</td>"
                f"<td style='color:{zc}'>{fn(r.get('current'))}</td>"
                f"<td>{fn(hh.get('1M'))}</td><td>{fn(hh.get('3M'))}</td><td>{fn(hh.get('1Y'))}</td>"
                f"<td>{fn(hh.get('3Y'))}</td><td>{fn(hh.get('5Y'))}</td><td>{fn(hh.get('10Y'))}</td>"
                f"<td style='color:{GREEN}'>{fn(r.get('all_min'))}</td>"
                f"<td style='color:{RED}'>{fn(r.get('all_max'))}</td>"
                f"<td style='color:{zc}'>{zt}</td></tr>")
    return h+"</table></div>"

def analytics_to_df(rows):
    out=[]
    for r in rows:
        if r.get("error"): continue
        hh=r.get("hist",{})
        out.append({"Name":r["name"],"Category":r.get("category"),"Unit":r.get("unit"),
            "Current":r.get("current"),"1M":hh.get("1M"),"3M":hh.get("3M"),"1Y":hh.get("1Y"),
            "3Y":hh.get("3Y"),"5Y":hh.get("5Y"),"10Y":hh.get("10Y"),
            "Min":r.get("all_min"),"Max":r.get("all_max"),"Z":r.get("z_score")})
    return pd.DataFrame(out)

def xlsx_bytes(df, sheet="Data"):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name=sheet[:31])
    return buf.getvalue()

def dl_button(df, label, fname):
    st.download_button("⬇ "+label, data=xlsx_bytes(df),
        file_name=fname, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── Plotly chart helpers ────────────────────────────────────────
def base_layout(fig, title, ysuffix=""):
    fig.update_layout(template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=CARD,
        height=420, margin=dict(l=46,r=20,t=44,b=34), title=title,
        font=dict(family="Consolas", color=TEXT2), legend=dict(bgcolor=CARD2))
    fig.update_xaxes(gridcolor=BORDER); fig.update_yaxes(gridcolor=BORDER, ticksuffix=ysuffix)
    return fig

PERIODS={"MTD":relativedelta(day=1),"3M":relativedelta(months=3),"6M":relativedelta(months=6),
         "YTD":None,"1Y":relativedelta(years=1),"3Y":relativedelta(years=3),
         "5Y":relativedelta(years=5),"10Y":relativedelta(years=10)}
def period_start(p):
    t=datetime.today()
    if p=="YTD": return t.replace(month=1,day=1)
    if p=="MTD": return t.replace(day=1)
    return t-PERIODS[p]

def ticker_chart(sym, name, period, mode, data_t, compare=None):
    start=period_start(period)
    fig=go.Figure()
    if compare:  # normalized % overlay
        combo={sym:name}; combo.update(compare)
        for i,(s,nm) in enumerate(combo.items()):
            c=md_history(s, start=start.strftime("%Y-%m-%d"))
            if c.empty: continue
            base=float(c.iloc[0]); r=(c-base)/base*100
            col=[ACCENT,BLUE,GREEN,YELLOW,PURPLE,CYAN][i%6]
            fig.add_trace(go.Scatter(x=c.index,y=r.values,mode="lines",name=f"{nm} ({r.iloc[-1]:+.1f}%)",line=dict(color=col,width=1.8)))
        return base_layout(fig, f"Comparison · normalized return · {period}", "%")
    c=md_history(sym, start=start.strftime("%Y-%m-%d"))
    if c.empty:
        return base_layout(fig, f"{name} — no data")
    if mode=="Bar":
        m=c.resample("ME").last().pct_change().dropna()*100
        cols=[GREEN if v>=0 else RED for v in m.values]
        fig.add_trace(go.Bar(x=m.index,y=m.values,marker_color=cols))
        return base_layout(fig, f"{name} · monthly return · {period}", "%")
    if data_t=="Returns":
        base=float(c.iloc[0]); s=(c-base)/base*100; suf="%"; ttl=f"{name} · cumulative return · {period}"
    else:
        s=c; suf=""; ttl=f"{name} · price · {period}"
    fig.add_trace(go.Scatter(x=c.index,y=s.values,mode="lines",line=dict(color=ACCENT,width=2),
        fill="tozeroy" if data_t=="Returns" else None, fillcolor="rgba(247,129,102,0.12)"))
    return base_layout(fig, ttl, suf)

# ════════════════════════════════════════════════════════════════
# SIDEBAR NAV
# ════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown('<span class="jaws-logo">JAWS</span>', unsafe_allow_html=True)
    st.markdown('<div class="jaws-sub">JW Market &amp; News Monitor</div>', unsafe_allow_html=True)
    st.write("")
    page = st.radio("Navigate", [
        "📊 Markets","💵 FI Spreads","📈 Rates","🏦 Funding","🧮 L/S Factors",
        "📉 Yield Curve","📐 Charts","🌊 Realized Vol","🔎 Scanner","📰 News"
    ], label_visibility="collapsed")
    st.write("")
    if st.button("↻ Refresh all data", use_container_width=True):
        st.cache_data.clear(); st.rerun()
    st.caption(f"Updated {datetime.now().strftime('%H:%M:%S')}")
    st.caption("Data: Yahoo Finance · FRED · US Treasury · Ken French · AQR · NewsAPI")

def header(title, sub=""):
    st.markdown(f'<span class="jaws-logo">JAWS</span>  '
                f'<span class="jaws-sub">{title}{("  ·  "+sub) if sub else ""}</span>',
                unsafe_allow_html=True); st.write("")

# ════════════════════════════════════════════════════════════════
# PAGE: MARKETS
# ════════════════════════════════════════════════════════════════
if page.endswith("Markets"):
    header("Markets")
    CATS={"Equity Indices":"indices","Volatility":"volatility","FX":"fx",
          "Fixed Income":"fixed_income","Municipals":"munis","Factor ETFs":"factors",
          "Commodities":"commodities","US Sectors":"sectors"}
    c1,c2=st.columns([2,2])
    cat=c1.selectbox("Category", list(CATS.keys()))
    cs=c2.date_input("Custom return start (optional)", value=None)
    key=CATS[cat]
    with st.spinner(f"Loading {cat}…"):
        data,tmap = md_returns(key, custom_start=cs.isoformat() if cs else None)
    st.markdown(returns_table_html(data,tmap), unsafe_allow_html=True)
    dl_button(returns_to_df(data,tmap), f"Export {cat}", f"JAWS_{key}.xlsx")
    st.divider()
    st.subheader("Chart")
    names=list(data.keys())
    cc1,cc2,cc3,cc4=st.columns([3,1,1,2])
    pick=cc1.selectbox("Instrument", names, key="mkt_pick")
    mode=cc2.radio("Type",["Line","Bar"],horizontal=True,key="mkt_mode")
    dt=cc3.radio("Data",["Price","Returns"],horizontal=True,key="mkt_dt")
    per=cc4.select_slider("Period",["MTD","3M","6M","YTD","1Y","3Y","5Y","10Y"],value="1Y",key="mkt_per")
    st.plotly_chart(ticker_chart(tmap.get(pick,pick),pick,per,mode,dt), use_container_width=True)

# ════════════════════════════════════════════════════════════════
# PAGE: FI SPREADS / RATES / FUNDING  (analytics panels)
# ════════════════════════════════════════════════════════════════
def analytics_page(title, loader, fname, unit_note):
    header(title, unit_note)
    with st.spinner("Loading from FRED…"):
        rows=loader()
    st.markdown(analytics_table_html(rows), unsafe_allow_html=True)
    dl_button(analytics_to_df(rows), f"Export {title}", fname)
    st.divider()
    st.subheader("History")
    valid=[r for r in rows if not r.get("error") and r.get("raw_dates")]
    names=[r["name"] for r in valid]
    if not names: return
    c1,c2=st.columns([3,2])
    pick=c1.selectbox("Series", names, key=fname+"pick")
    yrs=c2.select_slider("Period (years)",[1,3,5,10,99],value=5,
                         format_func=lambda x:"All" if x==99 else f"{x}Y",key=fname+"yr")
    r=next(x for x in valid if x["name"]==pick)
    cutoff=None if yrs==99 else pd.Timestamp(datetime.today()-relativedelta(years=yrs))
    ds=r["raw_dates"]; vs=r["raw_values"]
    pairs=[(d,v) for d,v in zip(ds,vs) if cutoff is None or pd.Timestamp(d)>=cutoff]
    fig=go.Figure()
    if pairs:
        xs,ys=zip(*pairs); mean=sum(ys)/len(ys)
        fig.add_trace(go.Scatter(x=list(xs),y=list(ys),mode="lines",line=dict(color=ACCENT,width=1.7)))
        fig.add_hline(y=mean, line=dict(color=TEXT3,dash="dash"), annotation_text=f"avg {mean:.0f}")
    st.plotly_chart(base_layout(fig,f"{pick} — history ({r.get('unit','')})"),use_container_width=True)

if page.endswith("FI Spreads"):
    analytics_page("Credit Spreads (ICE BofA / Moody's / FRED)", spreads_analytics,
                   "JAWS_FI_Spreads.xlsx", "bps · z-score vs own history")
elif page.endswith("Rates"):
    analytics_page("US Treasury Rates (FRED)", rates_analytics,
                   "JAWS_Rates.xlsx", "levels in %")
elif page.endswith("Funding"):
    analytics_page("Funding Markets (FRED)", funding_analytics,
                   "JAWS_Funding.xlsx", "levels in %")

# ════════════════════════════════════════════════════════════════
# PAGE: L/S FACTORS
# ════════════════════════════════════════════════════════════════
elif page.endswith("L/S Factors"):
    header("Academic L/S Factors", "Ken French + AQR · cumulative total return %")
    c1,c2=st.columns(2)
    cstart=c1.date_input("Custom start", value=None, key="fac_cs")
    cend=c2.date_input("Custom end", value=None, key="fac_ce")
    with st.spinner("Downloading factor data…"):
        fdata=factor_data(cstart, cend)
    FCOLS=["Factor","1D","1W","1M","MTD","QTD","3M","YTD","1Y","3Y","5Y","7Y","10Y","Custom"]
    keys=["1D","1W","1M","MTD","QTD","3M","YTD","1Y","3Y","5Y","7Y","10Y","Custom"]
    def fac_html(d):
        h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in FCOLS)+"</tr>"
        for sect,lbl in [("daily","DAILY (Ken French US)"),("monthly","MONTHLY (US/Dev/EM + AQR)")]:
            h+=f'<tr><td class="jaws-cat" colspan="{len(FCOLS)}">{lbl}</td></tr>'
            for r in d.get(sect,[]):
                if r.get("error"): continue
                w=r["windows"]
                h+="<tr><td>"+r["name"]+"</td>"+"".join(f"<td>{f_pct(w.get(k))}</td>" for k in keys)+"</tr>"
        return h+"</table></div>"
    st.markdown(fac_html(fdata), unsafe_allow_html=True)
    # export
    erows=[]
    for sect in ("daily","monthly"):
        for r in fdata.get(sect,[]):
            if r.get("error"): continue
            row={"Factor":r["name"],"Section":sect}; row.update({k:r["windows"].get(k) for k in keys})
            erows.append(row)
    dl_button(pd.DataFrame(erows), "Export Factors", "JAWS_LS_Factors.xlsx")
    st.divider(); st.subheader("Cumulative growth")
    import factors_data as fd
    allf=[r for s in ("daily","monthly") for r in fdata.get(s,[]) if not r.get("error")]
    names=[r["name"]+(" (D)" if r["is_daily"] else " (M)") for r in allf]
    c1,c2=st.columns([3,2])
    idx=c1.selectbox("Factor", range(len(names)), format_func=lambda i:names[i], key="fac_pick")
    yrs=c2.select_slider("Period",[1,3,5,7,10,99],value=5,
                         format_func=lambda x:"All" if x==99 else f"{x}Y",key="fac_yr")
    r=allf[idx]
    start=None if yrs==99 else date.today()-relativedelta(years=yrs)
    ds,vs=fd.cumulative_series(r["raw_dates"],r["raw_rets"],start)
    fig=go.Figure()
    if ds:
        col=GREEN if vs[-1]>=0 else RED
        fig.add_trace(go.Scatter(x=ds,y=vs,mode="lines",line=dict(color=col,width=1.7),fill="tozeroy",
            fillcolor="rgba(63,185,80,0.12)" if vs[-1]>=0 else "rgba(248,81,73,0.12)"))
        fig.add_hline(y=0, line=dict(color=TEXT3,dash="dash"))
    st.plotly_chart(base_layout(fig,f"{r['name']} — cumulative L/S return","%"),use_container_width=True)

# ════════════════════════════════════════════════════════════════
# PAGE: YIELD CURVE
# ════════════════════════════════════════════════════════════════
elif page.endswith("Yield Curve"):
    header("Yield Curve", "US Treasury par yields + TIPS real")
    import yield_curve as yc
    opts={"Today":0,"-1W":7,"-1M":30,"-3M":91,"-6M":182,"-1Y":365,"-2Y":730,"-3Y":1095}
    picks=st.multiselect("Curves to overlay", list(opts.keys()), default=["Today","-1Y"])
    add_tips=st.checkbox("Add TIPS real-yield curve (latest)")
    fig=go.Figure()
    @st.cache_data(ttl=1800, show_spinner=False)
    def _curve(days):
        return yc.fetch_curve_for_date(datetime.today()-relativedelta(days=days))
    for i,p in enumerate(picks):
        try:
            row=_curve(opts[p])
            if not row: continue
            mats=yc.MATURITIES; xs=[m for m in mats if row["yields"].get(m) is not None]
            ys=[row["yields"][m] for m in xs]
            col=[ACCENT,BLUE,GREEN,YELLOW,PURPLE,CYAN][i%6]
            fig.add_trace(go.Scatter(x=xs,y=ys,mode="lines+markers",name=f"{p} ({row.get('date','')})",line=dict(color=col,width=2)))
        except Exception as e:
            st.warning(f"{p}: {e}")
    if add_tips:
        try:
            t=yc.fetch_tips_curve_for_date(datetime.today())
            if t:
                xs=[m for m in yc.TIPS_MATURITIES if t["yields"].get(m) is not None]
                ys=[t["yields"][m] for m in xs]
                fig.add_trace(go.Scatter(x=xs,y=ys,mode="lines+markers",name="TIPS real",line=dict(color=GREEN,dash="dash")))
        except Exception: pass
    st.plotly_chart(base_layout(fig,"US Treasury Yield Curve","%"),use_container_width=True)

# ════════════════════════════════════════════════════════════════
# PAGE: CHARTS  (any instrument, full modes + compare)
# ════════════════════════════════════════════════════════════════
elif page.endswith("Charts"):
    header("Charts", "any ticker · line/bar · price/returns · compare")
    @st.cache_data(ttl=900, show_spinner=False)
    def all_tickers():
        import market_data as md
        d={}
        for dd in (md.INDICES,md.RATES,md.VOLATILITY,md.FX,md.FIXED_INCOME,md.MUNIS,
                   md.FACTORS,md.FUNDING,md.COMMODITIES,md.SECTORS):
            d.update(dd)
        return d
    tmap=all_tickers()
    c1,c2,c3,c4=st.columns([3,1,1,2])
    pick=c1.selectbox("Instrument", list(tmap.keys()))
    mode=c2.radio("Type",["Line","Bar"],horizontal=True)
    dt=c3.radio("Data",["Price","Returns"],horizontal=True)
    per=c4.select_slider("Period",["MTD","3M","6M","YTD","1Y","3Y","5Y","10Y"],value="1Y")
    cmp_raw=st.text_input("Compare tickers (comma-separated, e.g. SPY, QQQ, ^VIX)","")
    compare=None
    if cmp_raw.strip():
        compare={s.strip().upper():s.strip().upper() for s in cmp_raw.split(",") if s.strip()}
    st.plotly_chart(ticker_chart(tmap.get(pick,pick),pick,per,mode,dt,compare),use_container_width=True)
    s=md_history(tmap.get(pick,pick), start=period_start(per).strftime("%Y-%m-%d"))
    if not s.empty:
        dl_button(pd.DataFrame({"Date":s.index,"Close":s.values}), "Export series", f"JAWS_{pick}.xlsx")

# ════════════════════════════════════════════════════════════════
# PAGE: REALIZED VOL
# ════════════════════════════════════════════════════════════════
elif page.endswith("Realized Vol"):
    header("Realized Volatility", "annualized · rolling windows")
    default=["^GSPC","^NDX","TLT"]
    syms=st.text_input("Tickers (comma-separated)", "^GSPC, ^NDX, TLT")
    wins=st.multiselect("Rolling windows (days)", [21,63,126,252], default=[21,63],
                        format_func=lambda d:{21:"1M",63:"3M",126:"6M",252:"1Y"}[d])
    yrs=st.select_slider("Lookback",[1,2,3,5,10],value=3,format_func=lambda x:f"{x}Y")
    fig=go.Figure(); cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs))
    styles={21:"solid",63:"dash",126:"dashdot",252:"dot"}
    palette=[ACCENT,BLUE,GREEN,YELLOW,PURPLE,CYAN]
    for i,sym in enumerate([s.strip() for s in syms.split(",") if s.strip()]):
        c=md_history(sym, start=None)
        if c.empty: continue
        rets=c.pct_change().dropna(); col=palette[i%len(palette)]
        for w in wins:
            if len(rets)<w: continue
            rv=(rets.rolling(w).std()*(252**0.5)*100).dropna()
            rv=rv[rv.index>=cutoff]
            if rv.empty: continue
            fig.add_trace(go.Scatter(x=rv.index,y=rv.values,mode="lines",
                name=f"{sym} {({21:'1M',63:'3M',126:'6M',252:'1Y'})[w]}",
                line=dict(color=col,width=1.4,dash=styles[w])))
    st.plotly_chart(base_layout(fig,"Realized Volatility (annualized)","%"),use_container_width=True)

# ════════════════════════════════════════════════════════════════
# PAGE: SCANNER
# ════════════════════════════════════════════════════════════════
elif page.endswith("Scanner"):
    header("Market Scanner", "rolling z-scores · std-dev moves")
    UNIV={"S&P 500":"^GSPC","Nasdaq 100":"^NDX","Russell 2000":"^RUT","EAFE":"EFA","EM":"EEM",
          "Tech":"XLK","Financials":"XLF","Energy":"XLE","Health":"XLV","Utilities":"XLU",
          "10Y Yield":"^TNX","HY Bond":"HYG","IG Bond":"LQD","Gold":"GC=F","Oil":"CL=F",
          "Copper":"HG=F","EUR/USD":"EURUSD=X","USD/JPY":"JPY=X","VIX":"^VIX","MOVE":"^MOVE"}
    win=st.select_slider("Z-score window",[5,21,63,252],value=21,
                         format_func=lambda d:{5:"5d",21:"21d",63:"63d",252:"252d"}[d])
    @st.cache_data(ttl=900, show_spinner=True)
    def scan(univ, win):
        import numpy as np
        out=[]
        for name,sym in univ.items():
            try:
                c=md_history(sym)
                if c.empty or len(c)<win+10: continue
                rets=c.pct_change().dropna()
                window=rets.iloc[-win:]; hist=rets.iloc[:-win]
                if len(hist)<5: continue
                roll=float(window.sum())
                hr=[float(rets.iloc[j:j+win].sum()) for j in range(0,len(hist)-win,max(1,win//5))]
                if len(hr)<3: continue
                mu=float(np.mean(hr)); sd=float(np.std(hr,ddof=1))
                z=(roll-mu)/sd if sd>1e-9 else None
                out.append({"Instrument":name,"Ticker":sym,"Last":float(c.iloc[-1]),
                    "Move% (1d)":float(rets.iloc[-1])*100,"Z":z})
            except Exception: continue
        out.sort(key=lambda r:-(abs(r["Z"]) if r["Z"] is not None else 0))
        return out
    rows=scan(UNIV, win)
    hdr=["Instrument","Ticker","Last","1d Move%","Z-Score","σ Flag"]
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
    for r in rows:
        z=r["Z"]; az=abs(z) if z is not None else 0
        zc=RED if az>=2 else (YELLOW if az>=1 else TEXT2)
        flag=f"{az:.1f}σ" if az>=1 else ""
        mv=r["Move% (1d)"]; mc=GREEN if mv>=0 else RED
        h+=(f"<tr><td>{r['Instrument']}</td><td style='color:{TEXT3}'>{r['Ticker']}</td>"
            f"<td>{f_price(r['Last'],r['Instrument'])}</td>"
            f"<td style='color:{mc}'>{mv:+.2f}%</td>"
            f"<td style='color:{zc}'>{(f'{z:+.2f}' if z is not None else '—')}</td>"
            f"<td style='color:{zc}'>{flag}</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    dl_button(pd.DataFrame(rows), "Export Scan", "JAWS_Scanner.xlsx")

# ════════════════════════════════════════════════════════════════
# PAGE: NEWS
# ════════════════════════════════════════════════════════════════
elif page.endswith("News"):
    header("Top Stories", "ranked by source quality")
    flt=st.radio("Filter",["All","HF","IPO","M&A","ISS"],horizontal=True)
    with st.spinner("Fetching news…"):
        try: allnews=news_data()
        except Exception as e: allnews={}; st.error(f"News error: {e}")
    scored=[]
    for cat,items in allnews.items():
        for it in items:
            src=(it.get("source") or it.get("publisher") or "").lower()
            w=max((v for k,v in NEWS_WEIGHT.items() if k in src), default=3)
            scored.append((w,cat,it))
    scored.sort(key=lambda x:(x[0],x[2].get("published","") or ""),reverse=True)
    shown=0; cols=st.columns(2)
    for rank,(score,cat,it) in enumerate(scored):
        lbl=CAT_LABELS.get(cat,cat.upper())
        if flt!="All" and lbl!=flt: continue
        if shown>=80: break
        title=it.get("title") or it.get("headline") or "(no title)"
        url=it.get("url") or it.get("link") or "#"
        src=it.get("source") or it.get("publisher") or "Unknown"
        pub=(it.get("published") or it.get("date") or "")[:16]
        col=CAT_COLORS.get(cat,TEXT2)
        with cols[shown%2]:
            st.markdown(
                f'<div style="background:{CARD};border:1px solid {BORDER};border-radius:6px;'
                f'padding:8px 10px;margin-bottom:8px;">'
                f'<span style="color:{TEXT3};font-family:Consolas;font-size:11px;">#{rank+1}</span> '
                f'<span style="background:{col};color:{BG};font-family:Consolas;font-size:10px;'
                f'font-weight:700;padding:1px 5px;border-radius:3px;">{lbl}</span> '
                f'<span style="color:{col};font-weight:600;">{src}</span> '
                f'<span style="color:{TEXT3};font-size:11px;">{pub}</span><br>'
                f'<a href="{url}" target="_blank" style="color:{TEXT1};text-decoration:none;'
                f'font-size:14px;">{title}</a></div>', unsafe_allow_html=True)
        shown+=1
    if shown==0: st.info("No stories (check NEWS_API_KEY in app secrets).")
