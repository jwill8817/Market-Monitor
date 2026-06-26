"""
JW Market & News Monitor — DASH SAMPLE
Representative slice to test look/feel + reachability on your work computer
before the full build. This is the framework for Render/Railway hosting.

Run locally:   python web_sample/dash_app.py   → http://127.0.0.1:8050
Password: set env APP_USER / APP_PASS (defaults: jaws / jaws2026)
"""
import os
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from dash import Dash, dcc, html, Input, Output
import dash_auth

# ── Bloomberg dark theme (matches the desktop app) ──────────────
BG="#0d1117"; CARD="#1c2128"; CARD2="#21262d"; BORDER="#30363d"
ACCENT="#f78166"; BLUE="#58a6ff"; GREEN="#3fb950"; RED="#f85149"
TEXT1="#e6edf3"; TEXT2="#8b949e"

TICKERS={"S&P 500":"^GSPC","NASDAQ":"^IXIC","Dow":"^DJI",
         "Russell 2000":"^RUT","VIX":"^VIX","10Y Yield":"^TNX","Gold":"GC=F"}

_cache={}
def hist(ticker):
    if ticker not in _cache:
        h=yf.Ticker(ticker).history(period="1y")
        if not h.empty and h.index.tz is not None: h.index=h.index.tz_localize(None)
        _cache[ticker]=h["Close"] if not h.empty else pd.Series(dtype=float)
    return _cache[ticker]

def table_rows():
    out=[]
    for name,t in TICKERS.items():
        c=hist(t)
        if c.empty: continue
        cur=float(c.iloc[-1]); prev=float(c.iloc[-2])
        ytd=c[c.index>=pd.Timestamp(c.index[-1].year,1,1)]
        d1=(cur-prev)/prev*100
        y=(cur-float(ytd.iloc[0]))/float(ytd.iloc[0])*100 if len(ytd) else 0
        out.append((name,t,cur,d1,y))
    return out

app=Dash(__name__, title="JW Market & News Monitor")
server=app.server   # for gunicorn on Render/Railway

# Single shared password (friends & family)
dash_auth.BasicAuth(app, {os.environ.get("APP_USER","jaws"):
                          os.environ.get("APP_PASS","jaws2026")})

def pct(v):
    col=GREEN if v>=0 else RED
    return html.Span(f'{"+" if v>=0 else ""}{v:.2f}%', style={"color":col})

def market_table():
    header=html.Tr([html.Th(h, style={"textAlign":"left" if h=="Name" else "right",
                    "padding":"8px 10px","color":TEXT2,"borderBottom":f"1px solid {BORDER}"})
                    for h in ["Name","Ticker","Price","1D%","YTD%"]])
    body=[]
    for i,(name,t,price,d1,y) in enumerate(table_rows()):
        bg=CARD2 if i%2 else CARD
        pr=f"{price:,.2f}" if price<10000 else f"{price:,.0f}"
        cells=[html.Td(name,style={"padding":"7px 10px","color":TEXT1}),
               html.Td(t,style={"padding":"7px 10px","textAlign":"right","color":TEXT2}),
               html.Td(pr,style={"padding":"7px 10px","textAlign":"right","color":TEXT1}),
               html.Td(pct(d1),style={"padding":"7px 10px","textAlign":"right"}),
               html.Td(pct(y),style={"padding":"7px 10px","textAlign":"right"})]
        body.append(html.Tr(cells, style={"background":bg}))
    return html.Table([header]+body,
        style={"width":"100%","borderCollapse":"collapse",
               "fontFamily":"Consolas,monospace","fontSize":"14px"})

app.layout=html.Div(style={"background":BG,"minHeight":"100vh","padding":"18px",
                           "fontFamily":"Segoe UI,sans-serif"}, children=[
    html.Div([
        html.Span("JAWS", style={"background":ACCENT,"color":BG,"fontWeight":"700",
            "fontSize":"22px","padding":"6px 14px","borderRadius":"6px",
            "fontFamily":"Consolas,monospace"}),
        html.Span("  JW Market & News Monitor — web sample",
            style={"color":TEXT2,"fontFamily":"Consolas,monospace","marginLeft":"10px"}),
    ], style={"marginBottom":"18px"}),
    html.Div([
        html.Div([html.H3("Equity Indices", style={"color":TEXT1}), market_table()],
                 style={"flex":"1","background":CARD,"padding":"14px",
                        "borderRadius":"8px","border":f"1px solid {BORDER}"}),
        html.Div([
            html.H3("Chart", style={"color":TEXT1}),
            dcc.Dropdown(id="pick", options=[{"label":k,"value":k} for k in TICKERS],
                         value="S&P 500", clearable=False,
                         style={"background":CARD2,"color":"#000","marginBottom":"8px"}),
            dcc.Graph(id="chart", config={"displayModeBar":False}),
        ], style={"flex":"1","background":CARD,"padding":"14px","marginLeft":"14px",
                  "borderRadius":"8px","border":f"1px solid {BORDER}"}),
    ], style={"display":"flex"}),
    html.Div("Sample to verify the platform loads on your machine. "
             "The full build will reproduce all tabs, panels, and exports.",
             style={"color":TEXT2,"fontSize":"12px","marginTop":"14px",
                    "fontFamily":"Consolas,monospace"}),
])

@app.callback(Output("chart","figure"), Input("pick","value"))
def _chart(pick):
    s=hist(TICKERS[pick])
    fig=go.Figure()
    if not s.empty:
        base=float(s.iloc[0]); ret=(s-base)/base*100
        fig.add_trace(go.Scatter(x=s.index,y=ret.values,mode="lines",
            line=dict(color=ACCENT,width=2), fill="tozeroy",
            fillcolor="rgba(247,129,102,0.12)"))
    fig.update_layout(template="plotly_dark",paper_bgcolor=BG,plot_bgcolor=CARD,
        height=360,margin=dict(l=40,r=20,t=30,b=30),
        title=f"{pick} — cumulative return (1Y)",
        font=dict(family="Consolas",color=TEXT2))
    fig.update_xaxes(gridcolor=BORDER); fig.update_yaxes(gridcolor=BORDER,ticksuffix="%")
    return fig

if __name__=="__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT",8050)))
