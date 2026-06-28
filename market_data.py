import yfinance as yf
import datetime
import urllib.request
import io
from dateutil.relativedelta import relativedelta

# ── CBOE direct history (Yahoo only serves a live quote for these) ──
# Maps Yahoo-style symbol → CBOE history-CSV symbol.
_CBOE_MAP = {"^VIXEQ": "VIXEQ", "^COR1M": "COR1M", "^COR3M": "COR3M", "^COR6M": "COR6M"}
_CBOE_CACHE = {}

def _cboe_history(cboe_sym):
    """Daily close Series for a CBOE index from cboe.com (tz-naive index)."""
    if cboe_sym in _CBOE_CACHE:
        return _CBOE_CACHE[cboe_sym]
    import pandas as pd
    url = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{cboe_sym}_History.csv"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        txt = r.read().decode("utf-8", "replace")
    df = pd.read_csv(io.StringIO(txt))
    date_col  = df.columns[0]
    close_col = "CLOSE" if "CLOSE" in df.columns else df.columns[-1]
    s = pd.Series(df[close_col].values, index=pd.to_datetime(df[date_col]))
    s = s.dropna()
    s = s.sort_index()
    _CBOE_CACHE[cboe_sym] = s
    return s

def price_history(symbol, start=None, period="max", adjusted=True):
    """Return a tz-naive daily Close Series for any symbol.
    Routes CBOE-only indices (VIXEQ, COR1M/3M/6M) to cboe.com; everything
    else uses yfinance. Optional `start` (date/str) trims the series.
    adjusted=True → dividend+split adjusted close (TOTAL RETURN basis, default).
    adjusted=False → actual unadjusted market price."""
    import pandas as pd
    if symbol in _CBOE_MAP:
        s = _cboe_history(_CBOE_MAP[symbol])   # index levels — no adjustment concept
    else:
        if start is not None:
            h = yf.Ticker(symbol).history(start=str(start), auto_adjust=adjusted)
        else:
            h = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=adjusted)
        if h.empty:
            return pd.Series(dtype=float)
        if h.index.tz is not None:
            h.index = h.index.tz_localize(None)
        s = h["Close"]
    if start is not None:
        s = s[s.index >= pd.Timestamp(start)]
    return s.dropna()

INDICES = {
    "S&P 500":    "^GSPC",
    "NASDAQ":     "^IXIC",
    "DOW":        "^DJI",
    "FTSE 100":   "^FTSE",
    "DAX":        "^GDAXI",
    "Nikkei 225": "^N225",
    "Hang Seng":  "^HSI",
    "CAC 40":     "^FCHI",
    "ASX 200":    "^AXJO",
    "MSCI EM":    "EEM",
}

# Treasury benchmark yields only
RATES = {
    "Fed Funds (proxy)": "^IRX",   # 3M T-bill ≈ effective fed funds
    "US 3M":    "^IRX",
    "US 2Y":    "^FVX",            # closest yfinance proxy
    "US 5Y":    "^FVX",
    "US 10Y":   "^TNX",
    "US 30Y":   "^TYX",
    "UK 10Y":   "GBGB10YR=X",
    "DE 10Y":   "^TNX",            # placeholder — DE Bund not on yfinance
    "JP 10Y":   "JPGB10Y=X",
}

# Volatility instruments — separated from rates
VOLATILITY = {
    # Equity vol
    "VIX (S&P500 30d)":      "^VIX",
    "VIX9D (9-Day)":         "^VIX9D",
    "VVIX (VIX of VIX)":     "^VVIX",
    "SKEW (Tail Risk)":      "^SKEW",
    "VXEEM (EM Vol)":        "^VXEEM",
    "RVX (Russell 2000)":    "^RVX",
    # Dispersion / correlation / single-stock vol
    "VIXEQ (Avg Stock Vol)":  "^VIXEQ",  # CBOE S&P500 Constituent Vol Index
    "DSPX (Dispersion)":      "^DSPX",   # CBOE S&P500 Dispersion Index
    "Implied Corr 1M":        "^COR1M",  # CBOE 1-Month Implied Correlation
    "Implied Corr 3M":        "^COR3M",  # CBOE 3-Month Implied Correlation
    # Fixed income vol
    "MOVE (Treasury Vol)":   "^MOVE",   # ICE BofAML MOVE Index
    "FI Vol (IVOL ETF)":     "IVOL",
    # FX vol
    "EUR/USD Vol (EVZ)":     "^EVZ",    # CBOE EuroCurrency Vol Index
    # Commodity vol
    "Oil Vol (OVX)":         "^OVX",
    "Gold Vol (GVZ)":        "^GVZ",
}

FX = {
    "EUR/USD":  "EURUSD=X",
    "GBP/USD":  "GBPUSD=X",
    "USD/JPY":  "JPY=X",
    "USD/CHF":  "CHF=X",
    "AUD/USD":  "AUDUSD=X",
    "USD/CNY":  "CNY=X",
    "USD/CAD":  "CAD=X",
    "USD/MXN":  "MXN=X",
}

FIXED_INCOME = {
    "US Agg Bond":       "AGG",
    "Global Agg Bond":   "BNDW",
    "US High Yield":     "HYG",
    "US Inv Grade Corp": "LQD",
    "EM USD Debt":       "EMB",
    "EM Local Debt":     "EMLC",
    "US Treasury 1-3Y":  "SHY",
    "US Treasury 7-10Y": "IEF",
    "US Treasury 20Y+":  "TLT",
    "US TIPS":           "TIP",
    "Mortgage-Backed":   "MBB",
    "Senior Loans":      "BKLN",
    "Convertibles":      "CWB",
}

# Municipal bonds — organised by duration / type
MUNIS = {
    # Broad
    "National Muni (Blend)":  "MUB",
    "Vanguard Tax-Exempt":    "VTEB",
    # Short duration (1-5yr)
    "Short Muni (SHM)":       "SHM",
    "Short IG Muni (SUB)":    "SUB",
    # Intermediate (5-10yr)
    "Intermediate Muni (ITM)":"ITM",
    # Long duration (10yr+)
    "Long Muni (TFI)":        "TFI",
    "WisdomTree Muni Yld":    "MLN",
    # High yield / credit
    "HY Muni (HYD)":          "HYD",
    "HY Muni (HYMB)":         "HYMB",
    # AMT-free
    "AMT-Free Muni (AFTX)":   "AFTX",
    # State-specific
    "CA Munis (CMF)":         "CMF",
    "NY Munis (NYF)":         "NYF",
}

FACTORS = {
    "US Value":          "VTV",
    "US Growth":         "VUG",
    "US Small Cap":      "IWM",
    "US Large Cap":      "IVV",
    "US Momentum":       "MTUM",
    "US Min Volatility": "USMV",
    "US Quality":        "QUAL",
    "US High Dividend":  "HDV",
    "US Equal Weight":   "RSP",
    "Intl Value":        "EFV",
    "Intl Momentum":     "IMTM",
    "Intl Min Vol":      "EFAV",
    "Global Value":      "VLUE",
    "Small Cap Value":   "VBR",
}

# Funding markets — actual money-market rates from FRED (name → FRED series id)
# Rates are in percent; the UI shows current level + absolute (bps) changes.
FUNDING = {
    "SOFR":                "SOFR",
    "SOFR 30D Avg":        "SOFR30DAYAVG",
    "SOFR 90D Avg":        "SOFR90DAYAVG",
    "Fed Funds (EFFR)":    "EFFR",
    "Overnight Bank (OBFR)":"OBFR",
    "Interest on Reserves":"IORB",
    "Fed Funds Tgt Upper": "DFEDTARU",
    "Prime Rate":          "DPRIME",
    "1M T-Bill":           "DTB4WK",
    "3M T-Bill":           "DTB3",
    "6M T-Bill":           "DTB6",
    "3M AA Fin CP":        "DCPF3M",
    "3M Nonfin CP":        "DCPN3M",
    "ESTR (Euro O/N)":     "ECBESTRVOLWGTTRMDMNRT",
    "SONIA (UK O/N)":      "IUDSOIA",
    "30Y Mortgage":        "MORTGAGE30US",
}

COMMODITIES = {
    "Gold":            "GC=F",
    "Silver":          "SI=F",
    "Crude Oil (WTI)": "CL=F",
    "Brent Crude":     "BZ=F",
    "Natural Gas":     "NG=F",
    "Copper":          "HG=F",
    "Corn":            "ZC=F",
    "Wheat":           "ZW=F",
    "Soybeans":        "ZS=F",
    "Coffee":          "KC=F",
    "Sugar":           "SB=F",
    "Platinum":        "PL=F",
    "Palladium":       "PA=F",
}

# US equity sectors — SPDR Select Sector ETFs (GICS) + benchmark
SECTORS = {
    "Technology (XLK)":     "XLK",
    "Financials (XLF)":     "XLF",
    "Health Care (XLV)":    "XLV",
    "Cons. Discr. (XLY)":   "XLY",
    "Cons. Staples (XLP)":  "XLP",
    "Energy (XLE)":         "XLE",
    "Industrials (XLI)":    "XLI",
    "Materials (XLB)":      "XLB",
    "Utilities (XLU)":      "XLU",
    "Real Estate (XLRE)":   "XLRE",
    "Comm. Services (XLC)": "XLC",
    "S&P 500 (SPY)":        "SPY",
}

# Hedge-fund-strategy proxies — investable liquid-alt / HF-replication ETFs & funds.
# (HFRI / Pivotal Path proprietary indices are subscription-only, not free; these
#  tradeable vehicles are the closest freely-available read on HF strategy returns.)
HEDGE_FUNDS = {
    "HF Multi-Strat (QAI)":      "QAI",
    "HF Replication (HDG)":      "HDG",
    "Merger Arb (MNA)":          "MNA",
    "Merger Arb (MERFX)":        "MERFX",
    "Mkt-Neutral Anti-Beta (BTAL)":"BTAL",
    "Hedged Equity (JHQAX)":     "JHQAX",
    "Managed Futures (DBMF)":    "DBMF",
    "Managed Futures (KMLM)":    "KMLM",
    "Managed Futures (CTA)":     "CTA",
    "Managed Futures (WTMF)":    "WTMF",
    "Managed Futures (FMF)":     "FMF",
    "Global Macro/Multi (BLNDX)":"BLNDX",
    "Global Momentum (GMOM)":    "GMOM",
    "Liquid Alts (LALT)":        "LALT",
    "Tactical (CPITX)":          "CPITX",
    # ── Positioning / crowding ──
    "GS Hedge VIP — Crowded Longs (GVIP)": "GVIP",  # tracks GS Hedge Fund VIP basket
    "Most-Shorted / Meme (MEME)":          "MEME",  # high short-interest + retail-crowded names
    "Short Innovation (SARK)":             "SARK",  # inverse ARKK (short crowded growth)
    "Active Short / Bear (HDGE)":          "HDGE",  # actively shorts deteriorating crowded names
    "Long Online / Short Stores (CLIX)":   "CLIX",  # long/short thematic
}

# Alternative / multi-asset risk premia — liquid ETFs & funds.
RISK_PREMIA = {
    "Risk Parity (RPAR)":        "RPAR",
    "Ultra Risk Parity (UPAR)":  "UPAR",
    "Alt Risk Premia (QSPIX)":   "QSPIX",   # AQR Style Premia — canonical ARP
    "Trend / Mgd Futures (DBMF)":"DBMF",
    "Vol Carry (SVOL)":          "SVOL",
    "Rate Convexity/Tail (PFIX)":"PFIX",
    "Global Momentum (GMOM)":    "GMOM",
    "Real Return (RLY)":         "RLY",
    "Low-Risk / Anti-Beta (BTAL)":"BTAL",
    # Equity style premia
    "Momentum (MTUM)":           "MTUM",
    "Value (VLUE)":              "VLUE",
    "Quality (QUAL)":            "QUAL",
    "Min Volatility (USMV)":     "USMV",
    "Size (SIZE)":               "SIZE",
}

# AQR's most common strategies available in liquid (mutual-fund) format.
AQR_FUNDS = {
    "Style Premia Alt (QSPIX)":      "QSPIX",
    "Equity Mkt-Neutral (QMNIX)":    "QMNIX",
    "Long-Short Equity (QLEIX)":     "QLEIX",
    "Managed Futures (AQMIX)":       "AQMIX",
    "Multi-Strategy Alt (QMHIX)":    "QMHIX",
    "Diversified Arbitrage (ADAIX)": "ADAIX",
    "Intl Defensive Equity (QICNX)": "QICNX",
    "Risk Parity (QRPRX)":           "QRPRX",
}

# Crypto
CRYPTO = {
    "Bitcoin (BTC)":    "BTC-USD",
    "Ethereum (ETH)":   "ETH-USD",
    "Solana (SOL)":     "SOL-USD",
    "XRP (XRP)":        "XRP-USD",
    "BNB (BNB)":        "BNB-USD",
    "Cardano (ADA)":    "ADA-USD",
    "Dogecoin (DOGE)":  "DOGE-USD",
    "Avalanche (AVAX)": "AVAX-USD",
    "Chainlink (LINK)": "LINK-USD",
    "Polkadot (DOT)":   "DOT-USD",
    "Litecoin (LTC)":   "LTC-USD",
}


def _start_dates():
    today = datetime.date.today()
    return {
        "MTD": datetime.date(today.year, today.month, 1),
        "YTD": datetime.date(today.year, 1, 1),
        "1Y":  today - relativedelta(years=1),
        "3Y":  today - relativedelta(years=3),
        "5Y":  today - relativedelta(years=5),
        "10Y": today - relativedelta(years=10),
    }

def _pct(start_price, end_price):
    if start_price and end_price and start_price != 0:
        return round((end_price - start_price) / start_price * 100, 2)
    return None

def _annualized(start_price, end_price, years):
    """CAGR: (end/start)^(1/years) - 1, expressed as %."""
    if start_price and end_price and start_price != 0 and years > 0:
        return round(((end_price / start_price) ** (1 / years) - 1) * 100, 2)
    return None

# Periods that get annualized (>1Y)
_ANNUALIZE = {"3Y": 3, "5Y": 5, "10Y": 10}

def fetch_returns(ticker_dict, custom_start=None, custom_end=None, absolute=False):
    """
    Fetch returns for each ticker.
    absolute=True: report absolute level differences (e.g. yield bps) instead
                   of percentage changes. Used for the Rates tab.
    custom_start / custom_end: optional datetime.date — computes a 'Custom'
    return between them (end defaults to latest).
    """
    starts = _start_dates()
    results = {}
    # If a custom start older than the default 10y window is requested, fetch
    # from that date so the custom return reaches back — but never shorten the
    # window below 10y (so 5Y/10Y columns stay correct).
    _cs_str = None
    if custom_start:
        _ten_y = datetime.date.today() - relativedelta(years=10)
        _cs_str = min(custom_start, _ten_y).isoformat()
    for name, ticker in ticker_dict.items():
        try:
            # Returns tables only need 10y; pin the window so the (now max-default)
            # price_history doesn't pull full history for every quadrant instrument.
            _tbl_start = _cs_str or (datetime.date.today() - relativedelta(years=10)).isoformat()
            close = price_history(ticker, start=_tbl_start)
            if close.empty:
                results[name] = {"price": None, "change_1d": None, "returns": {}}
                continue
            current = float(close.iloc[-1])
            prev    = float(close.iloc[-2]) if len(close) > 1 else current

            if absolute:
                change_1d = round(current - prev, 4)
            else:
                change_1d = _pct(prev, current)

            returns = {}
            for period, start in starts.items():
                start_dt = datetime.datetime.combine(start, datetime.time())
                subset   = close[close.index >= start_dt]
                if subset.empty:
                    returns[period] = None
                elif absolute:
                    returns[period] = round(current - float(subset.iloc[0]), 4)
                elif period in _ANNUALIZE:
                    returns[period] = _annualized(float(subset.iloc[0]), current,
                                                   _ANNUALIZE[period])
                else:
                    returns[period] = _pct(float(subset.iloc[0]), current)

            # Custom date range (start → end; end defaults to latest)
            if custom_start is not None:
                cdt = datetime.datetime.combine(custom_start, datetime.time())
                csub = close[close.index >= cdt]
                if custom_end is not None:
                    edt = datetime.datetime.combine(custom_end, datetime.time())
                    esub = close[close.index <= edt]
                    ep = float(esub.iloc[-1]) if not esub.empty else current
                    end_date = custom_end
                else:
                    ep = current; end_date = datetime.date.today()
                if not csub.empty:
                    sp = float(csub.iloc[0])
                    if absolute:
                        returns["Custom"] = round(ep - sp, 4)
                    else:
                        years = (end_date - custom_start).days / 365.25
                        returns["Custom"] = (_annualized(sp, ep, years) if years > 1
                                             else _pct(sp, ep))
                else:
                    returns["Custom"] = None

            results[name] = {"price": current, "change_1d": change_1d, "returns": returns}
        except Exception:
            results[name] = {"price": None, "change_1d": None, "returns": {}}
    return results


def fetch_funding():
    """
    Funding-market rates from FRED. Rates are levels in %; change columns are
    ABSOLUTE differences (current − past level), matching the Rates tab style.
    """
    from fi_spreads import _fred_fetch_all, _value_at
    starts  = _start_dates()
    results = {}
    for name, sid in FUNDING.items():
        try:
            dates, values = _fred_fetch_all(sid)
            if not dates:
                results[name] = {"price": None, "change_1d": None, "returns": {}}
                continue
            current = values[-1]
            prev    = values[-2] if len(values) > 1 else current
            returns = {}
            for period, start in starts.items():
                v = _value_at(dates, values, start)
                returns[period] = round(current - v, 3) if v is not None else None
            results[name] = {
                "price":     current,
                "change_1d": round(current - prev, 3),
                "returns":   returns,
            }
        except Exception:
            results[name] = {"price": None, "change_1d": None, "returns": {}}
    return results


def fetch_all():
    print("  Fetching equity indices...")
    indices    = fetch_returns(INDICES)
    print("  Fetching rates...")
    rates      = fetch_returns(RATES, absolute=True)
    print("  Fetching volatility...")
    volatility = fetch_returns(VOLATILITY)
    print("  Fetching FX...")
    fx         = fetch_returns(FX)
    print("  Fetching fixed income...")
    fixed_income = fetch_returns(FIXED_INCOME)
    print("  Fetching munis...")
    munis      = fetch_returns(MUNIS)
    print("  Fetching factors...")
    factors    = fetch_returns(FACTORS)
    print("  Fetching funding markets...")
    funding    = fetch_funding()
    print("  Fetching commodities...")
    commodities = fetch_returns(COMMODITIES)
    print("  Fetching sectors...")
    sectors    = fetch_returns(SECTORS)
    return (indices, rates, volatility, fx, fixed_income, munis, factors,
            funding, commodities, sectors)
