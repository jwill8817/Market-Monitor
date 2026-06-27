"""
JW Market & News Monitor — full web app (Streamlit), 4-quadrant dashboard.
Reuses desktop data modules unchanged. Dark Bloomberg theme + Plotly.
"""
import os, sys, io
from datetime import datetime, date
from dateutil.relativedelta import relativedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
for _k in ("FRED_API_KEY", "NEWS_API_KEY"):
    try:
        if _k in st.secrets: os.environ[_k] = str(st.secrets[_k])
    except Exception: pass

import pandas as pd
import plotly.graph_objects as go

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
  div[data-testid="stVerticalBlockBorderWrapper"] {{ background:{CARD};
       border:1px solid {BORDER} !important; border-radius:8px; }}
  div[data-baseweb="select"] > div {{ background:{CARD2}; border-color:{BORDER}; }}
  .stRadio label, .stCheckbox label {{ color:{TEXT2}; }}
</style>
""", unsafe_allow_html=True)

# ── Auth ────────────────────────────────────────────────────────
def _auth():
    try:    pw = st.secrets.get("app_password", "jaws2026")
    except Exception: pw = "jaws2026"
    if st.session_state.get("auth_ok"): return True
    st.markdown('<div class="topbar"><span class="jaws-logo">JAWS</span>'
                '<span class="jaws-title">JW Market &amp; News Monitor</span></div>',
                unsafe_allow_html=True)
    e = st.text_input("Enter access password", type="password")
    if e:
        if e == pw: st.session_state["auth_ok"]=True; st.rerun()
        else: st.error("Incorrect password")
    return False
if not _auth(): st.stop()

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
def md_returns(key, custom_start=None, absolute=False):
    import market_data as md
    dmap={"indices":md.INDICES,"volatility":md.VOLATILITY,"fx":md.FX,
          "fixed_income":md.FIXED_INCOME,"munis":md.MUNIS,"factors":md.FACTORS,
          "commodities":md.COMMODITIES,"sectors":md.SECTORS}
    cs=pd.Timestamp(custom_start).date() if custom_start else None
    return md.fetch_returns(dmap[key], custom_start=cs, absolute=absolute), dmap[key]

@st.cache_data(ttl=900, show_spinner=False)
def md_history(sym, start=None):
    import market_data as md
    return md.price_history(sym, start=start)

@st.cache_data(ttl=900, show_spinner=False)
def all_tickers():
    import market_data as md
    d={}
    for dd in (md.INDICES,md.RATES,md.VOLATILITY,md.FX,md.FIXED_INCOME,md.MUNIS,
               md.FACTORS,md.FUNDING,md.COMMODITIES,md.SECTORS): d.update(dd)
    return d

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
@st.cache_data(ttl=3600, show_spinner=False)
def factor_data(cs=None, ce=None):
    import factors_data as fd; return fd.fetch_factors(custom_start=cs, custom_end=ce)
@st.cache_data(ttl=3600, show_spinner=False)
def news_data():
    from categorized_news import fetch_all_news_categorized
    return fetch_all_news_categorized()

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

NEWS_WEIGHT={"bloomberg":10,"wsj":9,"wall street journal":9,"reuters":8,
             "financial times":8,"ft":8,"cnbc":7,"yahoo finance":6,"seeking alpha":5,"zero hedge":4}
CAT_LABELS={"hedge_fund":"HF","ipo":"IPO","ma":"M&A","issuance":"ISS"}
CAT_COLORS={"hedge_fund":CYAN,"ipo":GREEN,"ma":YELLOW,"issuance":PURPLE}

def xlsx_bytes(df, sheet="Data"):
    buf=io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df.to_excel(w, index=False, sheet_name=sheet[:31])
    return buf.getvalue()
def dl(df, label, fname, key):
    st.download_button("⬇ "+label, data=xlsx_bytes(df), file_name=fname, key=key,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

def base_layout(fig, title, ysuffix="", h=330):
    fig.update_layout(template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=CARD,
        height=h, margin=dict(l=44,r=14,t=40,b=28), title=dict(text=title,font=dict(size=13)),
        font=dict(family="Consolas",color=TEXT2,size=11), legend=dict(bgcolor=CARD2,font=dict(size=10)))
    fig.update_xaxes(gridcolor=BORDER); fig.update_yaxes(gridcolor=BORDER,ticksuffix=ysuffix)
    return fig

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
    with st.spinner(f"Loading {label}…"):
        data,tmap = md_returns(catkey, custom_start=cs.isoformat() if cs else None, absolute=absolute)
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
    c1,c2=st.columns([1,1])
    c1.date_input("Custom start", value=cs, key=k+"_cs", min_value=date(1970,1,1))
    df=pd.DataFrame([{"Name":n,"Ticker":tmap.get(n,""),"Price":i.get("price"),
        **{p:i.get("returns",{}).get(p) for p in ["MTD","YTD","1Y","3Y","5Y","10Y","Custom"]}}
        for n,i in data.items()])
    with c2: dl(df, "Export", f"JAWS_{catkey}.xlsx", k+"_dl")

ANA_HDR=["Name","Unit","Cur","1M","3M","1Y","3Y","5Y","10Y","Min","Max","Z"]
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
            dec=r.get("decimals",0)
            def fn(v): return f'<span style="color:{TEXT3}">—</span>' if v is None else f"{v:.{dec}f}"
            z=r.get("z_score"); hh=r.get("hist",{}); zc=z_color(z)
            zt=f'{z:+.2f}σ' if z is not None else "—"
            h+=("<tr>"f"<td>{r['name']}</td><td style='color:{TEXT3}'>{r.get('unit','')}</td>"
                f"<td style='color:{zc}'>{fn(r.get('current'))}</td><td>{fn(hh.get('1M'))}</td>"
                f"<td>{fn(hh.get('3M'))}</td><td>{fn(hh.get('1Y'))}</td><td>{fn(hh.get('3Y'))}</td>"
                f"<td>{fn(hh.get('5Y'))}</td><td>{fn(hh.get('10Y'))}</td>"
                f"<td style='color:{GREEN}'>{fn(r.get('all_min'))}</td>"
                f"<td style='color:{RED}'>{fn(r.get('all_max'))}</td><td style='color:{zc}'>{zt}</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
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
    keys=["1D","1W","1M","MTD","QTD","3M","YTD","1Y","3Y","5Y","7Y","10Y","Custom"]
    FCOLS=["Factor"]+keys
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in FCOLS)+"</tr>"
    for sect,lbl in [("daily","DAILY (Ken French US)"),("monthly","MONTHLY (US/Dev/EM + AQR)")]:
        h+=f'<tr><td class="jaws-cat" colspan="{len(FCOLS)}">{lbl}</td></tr>'
        for r in fdata.get(sect,[]):
            if r.get("error"): continue
            w=r["windows"]
            h+="<tr><td>"+r["name"]+"</td>"+"".join(f"<td>{f_pct(w.get(x))}</td>" for x in keys)+"</tr>"
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
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
    tmap=all_tickers()
    ek=k+"_extra"
    if ek not in st.session_state: st.session_state[ek]={}
    sc1,sc2=st.columns([3,1])
    q=sc1.text_input("Search/add ticker or name", key=k+"_q", label_visibility="collapsed",
                     placeholder="Search any ticker or name, then Add →")
    if sc2.button("Add", key=k+"_add") and q.strip():
        raw=q.strip()
        if len(raw)<=6 and raw.replace("^","").replace("=","").replace(".","").isalnum():
            st.session_state[ek][raw.upper()]=raw.upper()
        else:
            res=yf_search(raw)
            if res:
                sym,nm=res[0]; st.session_state[ek][f"{nm[:22]} ({sym})"]=sym
    opts=list(tmap.keys())+list(st.session_state[ek].keys())
    full={**tmap, **st.session_state[ek]}
    defs=[d for d in default_labels if d in opts] or opts[:1]
    picks=st.multiselect("Instruments (add multiple to overlay)", opts, default=defs, key=k+"_ms")
    return {p:full.get(p,p) for p in picks}

def panel_chart(k):
    chosen=ticker_picker(k, ["S&P 500"])
    picks=list(chosen.keys()); full=chosen
    c1,c2,c3=st.columns([2,1,1])
    per=c1.select_slider("Period",["MTD","3M","6M","YTD","1Y","3Y","5Y","10Y","Custom"],
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
                "5Y":date.today()-relativedelta(years=5),"10Y":date.today()-relativedelta(years=10)}[per]
        cend=date.today()
    single = len(picks)==1
    mode=c2.radio("Type",["Line","Bar"],horizontal=True,key=k+"_mode",disabled=not single)
    dt=c3.radio("Data",["Price","Returns"],horizontal=True,key=k+"_dt",disabled=not single)
    fig=go.Figure(); exp={}
    for i,nm in enumerate(picks):
        sym=full.get(nm,nm)
        c=md_history(sym, start=cstart.strftime("%Y-%m-%d"))
        if c.empty: continue
        c=c[c.index<=pd.Timestamp(cend)]
        if c.empty: continue
        col=PALETTE[i%len(PALETTE)]
        if single and mode=="Bar":
            m=c.resample("ME").last().pct_change().dropna()*100
            fig.add_trace(go.Bar(x=m.index,y=m.values,marker_color=[GREEN if v>=0 else RED for v in m.values]))
            exp[nm+" m%"]=m
        elif single and dt=="Price":
            fig.add_trace(go.Scatter(x=c.index,y=c.values,mode="lines",line=dict(color=ACCENT,width=2),
                fill="tozeroy",fillcolor="rgba(247,129,102,0.10)")); exp[nm]=c
        else:
            base=float(c.iloc[0]); r=(c-base)/base*100
            fig.add_trace(go.Scatter(x=c.index,y=r.values,mode="lines",name=f"{nm} ({r.iloc[-1]:+.1f}%)",
                line=dict(color=col,width=1.8))); exp[nm+" %"]=r
    suffix="%" if not (single and dt=="Price") else ""
    ttl="Comparison · normalized %" if len(picks)>1 else (picks[0] if picks else "Chart")
    st.plotly_chart(base_layout(fig,f"{ttl} · {per}",suffix,h=320),use_container_width=True,key=k+"_chart")
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

def panel_rvol(k):
    chosen=ticker_picker(k, ["S&P 500","Nasdaq 100"])
    wins=st.multiselect("Windows",[21,63,126,252],default=[21,63],
                        format_func=lambda d:{21:"1M",63:"3M",126:"6M",252:"1Y"}[d],key=k+"_w")
    yrs=st.select_slider("Lookback",[1,2,3,5,10],value=3,format_func=lambda x:f"{x}Y",key=k+"_yr")
    fig=go.Figure(); cutoff=pd.Timestamp(datetime.today()-relativedelta(years=yrs))
    styles={21:"solid",63:"dash",126:"dashdot",252:"dot"}; exp={}
    for i,(label,sym) in enumerate(chosen.items()):
        c=md_history(sym)
        if c.empty: continue
        rets=c.pct_change().dropna(); col=PALETTE[i%len(PALETTE)]
        for w in wins:
            if len(rets)<w: continue
            rv=(rets.rolling(w).std()*(252**0.5)*100).dropna(); rv=rv[rv.index>=cutoff]
            if rv.empty: continue
            nm=f"{label} {({21:'1M',63:'3M',126:'6M',252:'1Y'})[w]}"
            fig.add_trace(go.Scatter(x=rv.index,y=rv.values,mode="lines",name=nm,
                line=dict(color=col,width=1.4,dash=styles[w]))); exp[nm]=rv
    st.plotly_chart(base_layout(fig,"Realized Volatility (annualized)","%",h=320),use_container_width=True,key=k+"_chart")
    if exp:
        df=pd.DataFrame(exp); df.insert(0,"Date",df.index)
        dl(df,"Export","JAWS_realizedvol.xlsx",k+"_dl")

def panel_scanner(k):
    UNIV={"S&P 500":"^GSPC","Nasdaq 100":"^NDX","Russell 2000":"^RUT","EAFE":"EFA","EM":"EEM",
          "Tech":"XLK","Financials":"XLF","Energy":"XLE","Health":"XLV","Utilities":"XLU",
          "10Y Yield":"^TNX","HY Bond":"HYG","IG Bond":"LQD","Gold":"GC=F","Oil":"CL=F",
          "Copper":"HG=F","EUR/USD":"EURUSD=X","USD/JPY":"JPY=X","VIX":"^VIX","MOVE":"^MOVE"}
    win=st.select_slider("Z window",[5,21,63,252],value=21,
                         format_func=lambda d:f"{d}d",key=k+"_w")
    @st.cache_data(ttl=900, show_spinner=True)
    def scan(win):
        import numpy as np; out=[]
        for name,sym in UNIV.items():
            try:
                c=md_history(sym)
                if c.empty or len(c)<win+10: continue
                rets=c.pct_change().dropna(); window=rets.iloc[-win:]; hist=rets.iloc[:-win]
                if len(hist)<5: continue
                roll=float(window.sum())
                hr=[float(rets.iloc[j:j+win].sum()) for j in range(0,len(hist)-win,max(1,win//5))]
                if len(hr)<3: continue
                mu=float(np.mean(hr)); sd=float(np.std(hr,ddof=1))
                z=(roll-mu)/sd if sd>1e-9 else None
                out.append({"Instrument":name,"Ticker":sym,"Last":float(c.iloc[-1]),
                    "Move%":float(rets.iloc[-1])*100,"Z":z})
            except Exception: continue
        out.sort(key=lambda r:-(abs(r["Z"]) if r["Z"] is not None else 0)); return out
    rows=scan(win)
    hdr=["Instrument","Tkr","Last","1d%","Z","σ"]
    h='<div class="tbl-wrap"><table class="jaws"><tr>'+"".join(f"<th>{c}</th>" for c in hdr)+"</tr>"
    for r in rows:
        z=r["Z"]; az=abs(z) if z is not None else 0
        zc=RED if az>=2 else (YELLOW if az>=1 else TEXT2); flag=f"{az:.1f}σ" if az>=1 else ""
        mv=r["Move%"]; mc=GREEN if mv>=0 else RED
        h+=(f"<tr><td>{r['Instrument']}</td><td style='color:{TEXT3}'>{r['Ticker']}</td>"
            f"<td>{f_price(r['Last'],r['Instrument'])}</td><td style='color:{mc}'>{mv:+.2f}%</td>"
            f"<td style='color:{zc}'>{(f'{z:+.2f}' if z is not None else '—')}</td>"
            f"<td style='color:{zc}'>{flag}</td></tr>")
    st.markdown(h+"</table></div>", unsafe_allow_html=True)
    dl(pd.DataFrame(rows),"Export","JAWS_scanner.xlsx",k+"_dl")

def panel_news(k):
    flt=st.radio("Filter",["All","HF","IPO","M&A","ISS"],horizontal=True,key=k+"_f")
    with st.spinner("Fetching news…"):
        try: allnews=news_data()
        except Exception as e: allnews={}; st.error(f"News error: {e}")
    scored=[]
    for cat,items in allnews.items():
        for it in items:
            src=(it.get("source") or it.get("publisher") or "").lower()
            w=max((v for kk,v in NEWS_WEIGHT.items() if kk in src), default=3)
            scored.append((w,cat,it))
    scored.sort(key=lambda x:(x[0],x[2].get("published","") or ""),reverse=True)
    st.markdown(f'<div style="max-height:430px;overflow:auto;">', unsafe_allow_html=True)
    shown=0
    for rank,(score,cat,it) in enumerate(scored):
        lbl=CAT_LABELS.get(cat,cat.upper())
        if flt!="All" and lbl!=flt: continue
        if shown>=60: break
        title=it.get("title") or it.get("headline") or "(no title)"
        url=it.get("url") or it.get("link") or "#"
        src=it.get("source") or it.get("publisher") or "Unknown"
        pub=(it.get("published") or it.get("date") or "")[:16]; col=CAT_COLORS.get(cat,TEXT2)
        st.markdown(f'<div style="background:{CARD2};border:1px solid {BORDER};border-radius:5px;'
            f'padding:6px 9px;margin-bottom:6px;">'
            f'<span style="color:{TEXT3};font-family:Consolas;font-size:10px;">#{rank+1}</span> '
            f'<span style="background:{col};color:{BG};font-family:Consolas;font-size:9px;'
            f'font-weight:700;padding:1px 4px;border-radius:3px;">{lbl}</span> '
            f'<span style="color:{col};font-weight:600;font-size:12px;">{src}</span> '
            f'<span style="color:{TEXT3};font-size:10px;">{pub}</span><br>'
            f'<a href="{url}" target="_blank" style="color:{TEXT1};text-decoration:none;font-size:13px;">'
            f'{title}</a></div>', unsafe_allow_html=True)
        shown+=1
    st.markdown("</div>", unsafe_allow_html=True)
    if shown==0: st.info("No stories (check NEWS_API_KEY in app secrets).")

def panel_valuation(k):
    # ── Current multiples cross-section ──
    ek=k+"_stk"
    if ek not in st.session_state: st.session_state[ek]={}
    c1,c2=st.columns([3,1])
    q=c1.text_input("Add stock", key=k+"_q", label_visibility="collapsed",
                    placeholder="Add a stock by ticker or name (e.g. AAPL, Nvidia)…")
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
        sym=st.text_input("Ticker (e.g. ^GSPC, SPY, CL=F)", "SPY" if side=="X" else "AAPL",
                          key=f"{k}_{side}_sym")
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

def panel_regression():
    st.markdown(f'<div style="margin-top:8px;"></div>', unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown('<span class="jaws-logo" style="font-size:16px;padding:3px 10px;">REG</span> '
                    '<span class="jaws-title" style="font-size:15px;">Regression Lab</span> '
                    '<span class="jaws-sub">OLS · any tool data or your own monthly CSV</span>',
                    unsafe_allow_html=True)
        freq=st.radio("Frequency",["Monthly","Daily"],horizontal=True,key="reg_freq")
        cX,cY=st.columns(2)
        with cX: xsrc,xsym,xfred,xfac,xup,xtf=_reg_var_ui("X","reg")
        with cY: ysrc,ysym,yfred,yfac,yup,ytf=_reg_var_ui("Y","reg")
        d1,d2,d3=st.columns([1,1,1])
        start=d1.date_input("Start", value=date.today()-relativedelta(years=10),
                            min_value=date(1950,1,1), key="reg_start")
        end=d2.date_input("End", value=date.today(), key="reg_end")
        run=d3.button("▶ Run regression", use_container_width=True, key="reg_run")
        if not run:
            st.caption("Pick X and Y, then Run. Beta = slope of Y on X. "
                       "Upload your own monthly series (Date, Value) to test against any tool data.")
            return
        sx=_reg_build_series(xsrc,xsym,xfred,xup,xfac,xtf,freq)
        sy=_reg_build_series(ysrc,ysym,yfred,yup,yfac,ytf,freq)
        # ── Verify each series resolved correctly ──
        def _ver(s, label, src, sym, fred, fac=""):
            who = sym or fred or fac or "uploaded CSV"
            if s is None or len(s)==0:
                return False, f"❌ **{label}** — `{who}` returned NO data (check the ticker/id)"
            return True, (f"✅ **{label}** — `{who}` · {len(s)} pts · "
                          f"{s.index[0].date()} → {s.index[-1].date()} · last {s.iloc[-1]:.2f}")
        okx,mx=_ver(sx,"X",xsrc,xsym,xfred,xfac); oky,my=_ver(sy,"Y",ysrc,ysym,yfred,yfac)
        st.markdown(mx); st.markdown(my)
        if xtf!=ytf:
            st.warning(f"⚠ X uses **{xtf}** but Y uses **{ytf}**. For a beta vs an index, set "
                       f"**both** to *Return %*.")
        if not okx or not oky:
            st.error("Fix the series above and re-run."); return
        df=pd.concat([sx.rename("x"),sy.rename("y")],axis=1,join="inner").dropna()
        df=df[(df.index>=pd.Timestamp(start))&(df.index<=pd.Timestamp(end))]
        if len(df)<3:
            st.error(f"Only {len(df)} overlapping points — widen the date range or check frequency."); return
        from scipy import stats
        lr=stats.linregress(df["x"].values, df["y"].values)
        tstat = lr.slope/lr.stderr if lr.stderr else float("nan")
        r2=lr.rvalue**2
        xlbl=f"{xsym or xfred or xfac or 'X'} ({xtf})"; ylbl=f"{ysym or yfred or yfac or 'Y'} ({ytf})"
        m=st.columns(6)
        m[0].metric("R²", f"{r2:.3f}")
        m[1].metric("Beta (slope)", f"{lr.slope:.4f}")
        m[2].metric("Intercept", f"{lr.intercept:.4f}")
        m[3].metric("t-stat", f"{tstat:.2f}")
        m[4].metric("p-value", f"{lr.pvalue:.4f}")
        m[5].metric("N obs", f"{len(df)}")
        sig = "significant" if lr.pvalue<0.05 else "not significant"
        st.caption(f"Correlation r = {lr.rvalue:+.3f} · slope {sig} at 95% · "
                   f"{df.index[0].date()} → {df.index[-1].date()} · {freq.lower()}")
        # Scatter + fit
        import numpy as np
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=df["x"],y=df["y"],mode="markers",
            marker=dict(color=BLUE,size=6,opacity=0.7),name="obs"))
        xr=np.array([df["x"].min(),df["x"].max()])
        fig.add_trace(go.Scatter(x=xr,y=lr.intercept+lr.slope*xr,mode="lines",
            line=dict(color=ACCENT,width=2),name=f"fit  y={lr.slope:.3f}x+{lr.intercept:.2f}"))
        fig.update_layout(template="plotly_dark",paper_bgcolor=BG,plot_bgcolor=CARD,height=380,
            margin=dict(l=50,r=20,t=40,b=44),title=dict(text=f"{ylbl}  vs  {xlbl}",font=dict(size=13)),
            font=dict(family="Consolas",color=TEXT2,size=11),legend=dict(bgcolor=CARD2,font=dict(size=10)))
        fig.update_xaxes(gridcolor=BORDER,title=xlbl); fig.update_yaxes(gridcolor=BORDER,title=ylbl)
        st.plotly_chart(fig, use_container_width=True, key="reg_chart")
        out=df.copy(); out.insert(0,"Date",out.index)
        dl(out.rename(columns={"x":xlbl,"y":ylbl}), "Export aligned data", "JAWS_regression.xlsx", "reg_dl")

# ── Slot dispatcher ─────────────────────────────────────────────
RETURN_CATS={"Equity Indices":"indices","Volatility & Correlation":"volatility","FX":"fx",
             "Fixed Income":"fixed_income","Municipals":"munis","Factor ETFs":"factors",
             "Commodities":"commodities","US Sectors":"sectors"}
# Tabs shown above each quadrant (radio = lazy: only the selected one loads).
TABLE_TABS=list(RETURN_CATS.keys())+["FI Spreads","Rates","Funding","L/S Factors","Valuation"]
PANEL_TABS=["Yield Curve","Chart","Realized Vol","Scanner","News"]

def _dispatch(sel, k):
    if sel in RETURN_CATS:    panel_returns(RETURN_CATS[sel], sel, k)
    elif sel=="FI Spreads":   panel_analytics(spreads_analytics,"Spreads","JAWS_FI_Spreads.xlsx",k)
    elif sel=="Rates":        panel_analytics(rates_analytics,"Rates","JAWS_Rates.xlsx",k)
    elif sel=="Funding":      panel_analytics(funding_analytics,"Funding","JAWS_Funding.xlsx",k)
    elif sel=="L/S Factors":  panel_factors(k)
    elif sel=="Valuation":    panel_valuation(k)
    elif sel=="Yield Curve":  panel_yield(k)
    elif sel=="Chart":        panel_chart(k)
    elif sel=="Realized Vol": panel_rvol(k)
    elif sel=="Scanner":      panel_scanner(k)
    elif sel=="News":         panel_news(k)

def render_slot(k, tabs, default):
    # Horizontal radio acts as a tab strip but only renders the selected panel
    sel=st.radio("tabs", tabs, index=tabs.index(default), key=k+"_sel",
                 horizontal=True, label_visibility="collapsed")
    _dispatch(sel, k)

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
tb1,tb2=st.columns([5,1])
with tb1:
    st.markdown('<div class="topbar"><span class="jaws-logo">JAWS</span>'
                '<span class="jaws-title">JW Market &amp; News Monitor</span>'
                f'<span class="jaws-sub">&nbsp;&nbsp;{datetime.now().strftime("%Y-%m-%d %H:%M")}</span>'
                '</div>', unsafe_allow_html=True)
with tb2:
    if st.button("↻ Refresh", use_container_width=True):
        st.cache_data.clear(); st.rerun()

r1=st.columns(2)
with r1[0]:
    with st.container(border=True): render_slot("q1", TABLE_TABS, "Equity Indices")
with r1[1]:
    with st.container(border=True): render_slot("q2", TABLE_TABS, "Factor ETFs")
r2=st.columns(2)
with r2[0]:
    with st.container(border=True): render_slot("q3", PANEL_TABS, "Yield Curve")
with r2[1]:
    with st.container(border=True): render_slot("q4", PANEL_TABS, "News")

# ── Regression Lab (full width, below the grid) ─────────────────
panel_regression()
