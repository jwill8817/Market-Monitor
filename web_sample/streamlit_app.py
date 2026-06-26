"""
JW Market & News Monitor — STREAMLIT SAMPLE
A small, representative slice of the full app to test look/feel + reachability
on your work computer before committing to the full build.

Run locally:   streamlit run web_sample/streamlit_app.py
Default password: jaws2026  (override with .streamlit/secrets.toml -> app_password)
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf

# ── Bloomberg dark theme (matches the desktop app) ──────────────
BG="#0d1117"; CARD="#1c2128"; CARD2="#21262d"; BORDER="#30363d"
ACCENT="#f78166"; BLUE="#58a6ff"; GREEN="#3fb950"; RED="#f85149"
TEXT1="#e6edf3"; TEXT2="#8b949e"

st.set_page_config(page_title="JW Market & News Monitor",
                   page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
  .stApp {{ background:{BG}; color:{TEXT1}; }}
  header[data-testid="stHeader"] {{ background:{BG}; }}
  .block-container {{ padding-top:1.2rem; max-width:100%; }}
  h1,h2,h3,h4 {{ color:{TEXT1}; font-family:'Segoe UI',sans-serif; }}
  .jaws-logo {{ background:{ACCENT}; color:{BG}; font-weight:700; font-size:22px;
               padding:6px 14px; border-radius:6px; display:inline-block;
               font-family:Consolas,monospace; }}
  .jaws-sub {{ color:{TEXT2}; font-family:Consolas,monospace; font-size:13px; }}
  table.jaws {{ width:100%; border-collapse:collapse; font-family:Consolas,monospace; font-size:14px; }}
  table.jaws th {{ background:{CARD2}; color:{TEXT2}; text-align:right; padding:8px 10px;
                  border-bottom:1px solid {BORDER}; }}
  table.jaws th:first-child {{ text-align:left; }}
  table.jaws td {{ padding:7px 10px; border-bottom:1px solid {BORDER}; text-align:right; color:{TEXT1}; }}
  table.jaws td:first-child {{ text-align:left; color:{TEXT1}; }}
  table.jaws tr:nth-child(even) {{ background:{CARD2}; }}
  table.jaws tr:nth-child(odd)  {{ background:{CARD}; }}
</style>
""", unsafe_allow_html=True)

# ── Password gate ───────────────────────────────────────────────
def _check_password():
    pw = st.secrets.get("app_password", "jaws2026") if hasattr(st, "secrets") else "jaws2026"
    if st.session_state.get("auth_ok"):
        return True
    st.markdown('<span class="jaws-logo">JAWS</span>  '
                '<span class="jaws-sub">JW Market &amp; News Monitor</span>',
                unsafe_allow_html=True)
    st.write("")
    entered = st.text_input("Enter access password", type="password")
    if entered:
        if entered == pw:
            st.session_state["auth_ok"] = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False

if not _check_password():
    st.stop()

# ── Sample data ─────────────────────────────────────────────────
TICKERS = {"S&P 500":"^GSPC","NASDAQ":"^IXIC","Dow":"^DJI",
           "Russell 2000":"^RUT","VIX":"^VIX","10Y Yield":"^TNX","Gold":"GC=F"}

@st.cache_data(ttl=600)
def load_table():
    rows=[]
    for name,t in TICKERS.items():
        try:
            h=yf.Ticker(t).history(period="1y")
            if h.empty: continue
            c=h["Close"]; cur=float(c.iloc[-1]); prev=float(c.iloc[-2])
            ytd=c[c.index>=pd.Timestamp(c.index[-1].year,1,1)]
            d1=(cur-prev)/prev*100
            y=(cur-float(ytd.iloc[0]))/float(ytd.iloc[0])*100 if len(ytd) else 0
            rows.append((name,t,cur,d1,y))
        except Exception:
            pass
    return rows

@st.cache_data(ttl=600)
def load_hist(ticker):
    h=yf.Ticker(ticker).history(period="1y")
    if h.index.tz is not None: h.index=h.index.tz_localize(None)
    return h["Close"]

# ── Header ──────────────────────────────────────────────────────
c1,c2=st.columns([3,1])
with c1:
    st.markdown('<span class="jaws-logo">JAWS</span>  '
                '<span class="jaws-sub">JW Market &amp; News Monitor — web sample</span>',
                unsafe_allow_html=True)
with c2:
    st.caption("Live data · Yahoo Finance")

st.write("")
left,right=st.columns([1,1])

# ── Market table ────────────────────────────────────────────────
with left:
    st.subheader("Equity Indices")
    data=load_table()
    def fmt_pct(v):
        col=GREEN if v>=0 else RED
        return f'<span style="color:{col}">{"+" if v>=0 else ""}{v:.2f}%</span>'
    html='<table class="jaws"><tr><th>Name</th><th>Ticker</th><th>Price</th><th>1D%</th><th>YTD%</th></tr>'
    for name,t,price,d1,ytd in data:
        pr=f"{price:,.2f}" if price<10000 else f"{price:,.0f}"
        html+=f"<tr><td>{name}</td><td>{t}</td><td>{pr}</td><td>{fmt_pct(d1)}</td><td>{fmt_pct(ytd)}</td></tr>"
    html+="</table>"
    st.markdown(html, unsafe_allow_html=True)

# ── Interactive chart ───────────────────────────────────────────
with right:
    st.subheader("Chart")
    pick=st.selectbox("Instrument", list(TICKERS.keys()))
    s=load_hist(TICKERS[pick])
    base=float(s.iloc[0]); ret=(s-base)/base*100
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=s.index, y=ret.values, mode="lines",
                             line=dict(color=ACCENT, width=2), name=pick,
                             fill="tozeroy", fillcolor="rgba(247,129,102,0.12)"))
    fig.update_layout(template="plotly_dark", paper_bgcolor=BG, plot_bgcolor=CARD,
                      height=360, margin=dict(l=40,r=20,t=30,b=30),
                      title=f"{pick} — cumulative return (1Y)",
                      font=dict(family="Consolas", color=TEXT2))
    fig.update_xaxes(gridcolor=BORDER); fig.update_yaxes(gridcolor=BORDER, ticksuffix="%")
    st.plotly_chart(fig, use_container_width=True)

st.write("")
st.caption("This is a small sample to verify the platform loads on your machine. "
           "The full build will reproduce all tabs, panels, and exports.")
