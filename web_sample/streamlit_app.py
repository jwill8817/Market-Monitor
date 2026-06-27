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

# ── Slot dispatcher ─────────────────────────────────────────────
RETURN_CATS={"Equity Indices":"indices","Volatility & Correlation":"volatility","FX":"fx",
             "Fixed Income":"fixed_income","Municipals":"munis","Factor ETFs":"factors",
             "Commodities":"commodities","US Sectors":"sectors"}
# Tabs shown above each quadrant (radio = lazy: only the selected one loads).
TABLE_TABS=list(RETURN_CATS.keys())+["FI Spreads","Rates","Funding","L/S Factors"]
PANEL_TABS=["Yield Curve","Chart","Realized Vol","Scanner","News"]

def _dispatch(sel, k):
    if sel in RETURN_CATS:    panel_returns(RETURN_CATS[sel], sel, k)
    elif sel=="FI Spreads":   panel_analytics(spreads_analytics,"Spreads","JAWS_FI_Spreads.xlsx",k)
    elif sel=="Rates":        panel_analytics(rates_analytics,"Rates","JAWS_Rates.xlsx",k)
    elif sel=="Funding":      panel_analytics(funding_analytics,"Funding","JAWS_Funding.xlsx",k)
    elif sel=="L/S Factors":  panel_factors(k)
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
  div[role="radiogroup"] {{ gap:2px !important; flex-wrap:wrap; }}
  div[role="radiogroup"] label {{ background:{CARD2}; border:1px solid {BORDER};
      border-radius:5px 5px 0 0; padding:2px 9px !important; margin:0 !important; }}
  div[role="radiogroup"] label:hover {{ background:{BORDER}; }}
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
