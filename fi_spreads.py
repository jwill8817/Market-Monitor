"""
Fixed Income Spreads — actual OAS data from FRED (ICE BofA indices).

Primary source: FRED CSV endpoint (no API key required).
  - Values are in percent (e.g. 2.65 = 265 bps).
  - Converted to bps for display.

Fallback for history charting: yfinance ETF price-return proxy.
"""
import urllib.request
import urllib.parse
import datetime
import json
import os
import yfinance as yf
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv

load_dotenv()
_FRED_UA      = "JAWS/1.0 jwill8817@gmail.com"
_FRED_TIMEOUT = 10  # seconds
_FRED_KEY     = os.environ.get("FRED_API_KEY", "")   # free key from fred.stlouisfed.org

# ── FRED series definitions ─────────────────────────────────
# (display_name, fred_series_id, category, description)
#
# NOTE: ICE BofA OAS series (BAML*) are licensed on FRED with a rolling
#       ~3-year window — full history (5Y/10Y) is NOT available for them.
#       Moody's Baa/Aaa spread series go back to the 1980s and DO support
#       the full lookback table + decades-long z-scores.
FRED_SPREADS = [
    # ── Credit — Long History (Moody's, 1980s+) ───────────
    ("Baa Corp Spread",    "BAA10Y",          "Credit (Long Hist)",
     "Moody's Baa Corporate yield minus 10Y Treasury (1986+)"),
    ("Aaa Corp Spread",    "AAA10Y",          "Credit (Long Hist)",
     "Moody's Aaa Corporate yield minus 10Y Treasury (1983+)"),
    # ── US Corporate OAS (ICE BofA, ~3yr window) ──────────
    ("US HY OAS",          "BAMLH0A0HYM2",    "US Corp OAS (3yr)",
     "ICE BofA US High Yield OAS (all maturities)"),
    ("US HY BB OAS",       "BAMLH0A1HYBBEY",  "US Corp OAS (3yr)",
     "ICE BofA BB-rated HY OAS"),
    ("US HY B OAS",        "BAMLH0A2HYBEY",   "US Corp OAS (3yr)",
     "ICE BofA B-rated HY OAS"),
    ("US IG Corp OAS",     "BAMLC0A0CM",      "US Corp OAS (3yr)",
     "ICE BofA US Corporate (IG) OAS"),
    ("US BBB OAS",         "BAMLC0A4CBBB",    "US Corp OAS (3yr)",
     "ICE BofA BBB Corporate OAS"),
    ("EM Corp OAS",        "BAMLEMCBPIOAS",   "US Corp OAS (3yr)",
     "ICE BofA EM Corporate Plus OAS"),
    # ── Yield Curve / Gov Spreads (long history) ──────────
    ("10Y-2Y Spread",      "T10Y2Y",          "Rates",
     "10-Year minus 2-Year Treasury yield spread (1976+)"),
    ("10Y-3M Spread",      "T10Y3M",          "Rates",
     "10-Year minus 3-Month Treasury yield spread (1982+)"),
]

# Computed spreads (series_a − series_b), for classic quality spreads
# (display_name, series_a, series_b, category, description)
COMPUTED_SPREADS = [
    ("Baa-Aaa Quality",    "DBAA", "DAAA",     "Credit (Long Hist)",
     "Moody's Baa minus Aaa quality spread (1986+)"),
    ("Mortgage Spread",    "MORTGAGE30US", "DGS10", "Credit (Long Hist)",
     "30Y fixed mortgage rate minus 10Y Treasury (1971+)"),
    ("CP-TBill (3M)",      "DCPF3M", "DTB3",   "Credit (Long Hist)",
     "3M AA financial commercial paper minus 3M T-Bill (funding stress, 1997+)"),
]

# ETF-based fallback / chart history pairs
# (label, credit_etf, benchmark_etf)
CHART_PAIRS = [
    ("HY vs Treasury",  "HYG",  "IEF"),
    ("IG vs Treasury",  "LQD",  "IEF"),
    ("EM vs Treasury",  "EMB",  "IEF"),
    ("Loan vs T-Bill",  "BKLN", "SHY"),
    ("MBS vs Treasury", "MBB",  "IEF"),
    ("Muni vs Treasury","MUB",  "IEF"),
]


# ── FRED fetch helpers ──────────────────────────────────────

def _fred_fetch_all(series_id: str) -> tuple[list, list] | tuple[None, None]:
    """
    Fetch complete available history for a FRED series.
    Uses the proper JSON API when FRED_API_KEY is set (full history).
    Falls back to the public CSV endpoint (~3 years without a key).
    """
    dates, values = [], []

    if _FRED_KEY:
        # Full history via FRED API
        url = (f"https://api.stlouisfed.org/fred/series/observations"
               f"?series_id={series_id}&observation_start=1990-01-01"
               f"&file_type=json&api_key={_FRED_KEY}")
        req = urllib.request.Request(url, headers={"User-Agent": _FRED_UA})
        try:
            with urllib.request.urlopen(req, timeout=_FRED_TIMEOUT) as r:
                data = json.loads(r.read())
            for obs in data.get("observations", []):
                if obs.get("value") in (".", ""):
                    continue
                try:
                    dates.append(datetime.date.fromisoformat(obs["date"]))
                    values.append(float(obs["value"]))
                except Exception:
                    continue
        except Exception:
            pass  # fall through to CSV

    if not dates:
        # Public CSV endpoint (~3 years without login)
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        req = urllib.request.Request(url, headers={"User-Agent": _FRED_UA})
        try:
            with urllib.request.urlopen(req, timeout=_FRED_TIMEOUT) as r:
                lines = r.read().decode().strip().split("\n")
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) != 2 or parts[1].strip() in (".", ""):
                    continue
                try:
                    dates.append(datetime.date.fromisoformat(parts[0].strip()))
                    values.append(float(parts[1].strip()))
                except Exception:
                    continue
        except Exception:
            return None, None

    if not dates:
        return None, None

    # Guarantee ascending date order
    paired = sorted(zip(dates, values))
    dates, values = zip(*paired)
    return list(dates), list(values)


def _value_at(dates: list, values: list, target: datetime.date,
              tolerance_days: int = 7) -> float | None:
    """
    Return the last value on or before target date.
    If nothing exists before target, accepts the first value within tolerance_days
    after target (handles weekends, holidays, and minor data gaps).
    """
    result = None
    for d, v in zip(dates, values):
        if d <= target:
            result = v
        elif result is None and (d - target).days <= tolerance_days:
            return v   # nearest available when target predates the series start
        elif result is not None:
            break
    return result


# ── Public API ─────────────────────────────────────────────

_LOOKBACKS = [
    ("1M",  30),
    ("3M",  91),
    ("1Y",  365),
    ("3Y",  365*3),
    ("5Y",  365*5),
    ("10Y", 365*10),
]

def _build_analytics(name, sid, cat, desc, dates, values, to_bps=True):
    """Compute current / lookbacks / min / max / z-score from a series.
    to_bps=True  → spreads: % values ×100, displayed in bps (integer)
    to_bps=False → rate levels: kept in %, displayed with 2 decimals."""
    import statistics
    today  = datetime.date.today()
    scale  = 100 if to_bps else 1
    scaled = [v * scale for v in values]

    current = scaled[-1]
    hist = {}
    for label, days in _LOOKBACKS:
        target = today - datetime.timedelta(days=days)
        raw = _value_at(dates, values, target)
        hist[label] = round(raw * scale, 2) if raw is not None else None

    mn  = round(min(scaled), 2)
    mx  = round(max(scaled), 2)
    avg = statistics.mean(scaled)
    std = statistics.stdev(scaled) if len(scaled) > 1 else 0
    z   = round((current - avg) / std, 2) if std > 0 else None

    return {
        "name":        name,
        "series_id":   sid,
        "category":    cat,
        "description": desc,
        "is_oas":      to_bps,             # bps display when True
        "unit":        "bps" if to_bps else "%",
        "decimals":    0 if to_bps else 2,
        "current":     round(current, 2),
        "as_of":       str(dates[-1]),
        "hist":        hist,
        "all_min":     mn,
        "all_max":     mx,
        "z_score":     z,
        "raw_dates":   dates,
        "raw_values":  scaled,
    }


def fetch_spread_analytics() -> list[dict]:
    """
    Fetch each FRED series (and computed differences) and return analytics:
      current, 1M/3M/1Y/3Y/5Y/10Y ago, all-time min/max, z-score.
    All spreads displayed in bps.
    """
    results = []

    # Single-series spreads
    for name, sid, cat, desc in FRED_SPREADS:
        dates, values = _fred_fetch_all(sid)
        if dates is None:
            results.append({"name": name, "series_id": sid, "category": cat,
                            "description": desc, "error": True})
            continue
        results.append(_build_analytics(name, sid, cat, desc, dates, values))

    # Computed spreads (series_a − series_b on aligned dates)
    for name, sid_a, sid_b, cat, desc in COMPUTED_SPREADS:
        da, va = _fred_fetch_all(sid_a)
        db, vb = _fred_fetch_all(sid_b)
        if da is None or db is None:
            results.append({"name": name, "series_id": f"{sid_a}-{sid_b}",
                            "category": cat, "description": desc, "error": True})
            continue
        map_b = dict(zip(db, vb))
        dates, values = [], []
        for d, v in zip(da, va):
            if d in map_b:
                dates.append(d)
                values.append(v - map_b[d])
        if not dates:
            results.append({"name": name, "series_id": f"{sid_a}-{sid_b}",
                            "category": cat, "description": desc, "error": True})
            continue
        results.append(_build_analytics(name, f"{sid_a}-{sid_b}", cat, desc,
                                        dates, values))

    # Order by category for clean grouping
    cat_order = {c: i for i, c in enumerate(
        ["Credit (Long Hist)", "US Corp OAS (3yr)", "EM", "Rates"])}
    results.sort(key=lambda r: cat_order.get(r.get("category", ""), 99))
    return results


# ── Rates & Funding (level series, displayed in %) ──────────
# (display_name, fred_series_id, category, description)
RATES_SERIES = [
    ("1M T-Bill",    "DGS1MO", "T-Bills",  "1-Month Treasury Constant Maturity"),
    ("3M T-Bill",    "DGS3MO", "T-Bills",  "3-Month Treasury Constant Maturity"),
    ("6M T-Bill",    "DGS6MO", "T-Bills",  "6-Month Treasury Constant Maturity"),
    ("1Y Treasury",  "DGS1",   "Notes",    "1-Year Treasury Constant Maturity"),
    ("2Y Treasury",  "DGS2",   "Notes",    "2-Year Treasury Constant Maturity"),
    ("3Y Treasury",  "DGS3",   "Notes",    "3-Year Treasury Constant Maturity"),
    ("5Y Treasury",  "DGS5",   "Notes",    "5-Year Treasury Constant Maturity"),
    ("7Y Treasury",  "DGS7",   "Notes",    "7-Year Treasury Constant Maturity"),
    ("10Y Treasury", "DGS10",  "Bonds",    "10-Year Treasury Constant Maturity"),
    ("20Y Treasury", "DGS20",  "Bonds",    "20-Year Treasury Constant Maturity"),
    ("30Y Treasury", "DGS30",  "Bonds",    "30-Year Treasury Constant Maturity"),
    ("10Y TIPS (Real)","DFII10","Real",    "10-Year TIPS Real Yield"),
    ("10Y Breakeven","T10YIE",  "Real",    "10-Year Breakeven Inflation Rate"),
]

FUNDING_SERIES = [
    ("SOFR",               "SOFR",         "Overnight", "Secured Overnight Financing Rate"),
    ("SOFR 30D Avg",       "SOFR30DAYAVG", "Overnight", "30-Day Average SOFR"),
    ("SOFR 90D Avg",       "SOFR90DAYAVG", "Overnight", "90-Day Average SOFR"),
    ("Fed Funds (EFFR)",   "EFFR",         "Overnight", "Effective Federal Funds Rate"),
    ("Overnight Bank Rate","OBFR",         "Overnight", "Overnight Bank Funding Rate"),
    ("Interest on Reserves","IORB",        "Policy",    "Interest on Reserve Balances"),
    ("Fed Funds Tgt Upper","DFEDTARU",     "Policy",    "Fed Funds Target Range Upper Limit"),
    ("Prime Rate",         "DPRIME",       "Policy",    "Bank Prime Loan Rate"),
    ("1M T-Bill",          "DTB4WK",       "Bills/CP",  "4-Week Treasury Bill Secondary Mkt"),
    ("3M T-Bill",          "DTB3",         "Bills/CP",  "3-Month Treasury Bill Secondary Mkt"),
    ("6M T-Bill",          "DTB6",         "Bills/CP",  "6-Month Treasury Bill Secondary Mkt"),
    ("3M AA Fin CP",       "DCPF3M",       "Bills/CP",  "3-Month AA Financial Commercial Paper"),
    ("3M Nonfin CP",       "DCPN3M",       "Bills/CP",  "3-Month AA Nonfinancial Commercial Paper"),
    ("ESTR (Euro O/N)",    "ECBESTRVOLWGTTRMDMNRT", "Intl", "Euro Short-Term Rate"),
    ("SONIA (UK O/N)",     "IUDSOIA",      "Intl",      "Sterling Overnight Index Average"),
    ("30Y Mortgage",       "MORTGAGE30US", "Other",     "30-Year Fixed Mortgage Average"),
]


def _fetch_level_analytics(series_list, cat_order_list):
    """Shared fetcher for rate/funding level series (displayed in %)."""
    results = []
    for name, sid, cat, desc in series_list:
        dates, values = _fred_fetch_all(sid)
        if dates is None:
            results.append({"name": name, "series_id": sid, "category": cat,
                            "description": desc, "error": True})
            continue
        results.append(_build_analytics(name, sid, cat, desc, dates, values,
                                        to_bps=False))
    order = {c: i for i, c in enumerate(cat_order_list)}
    results.sort(key=lambda r: order.get(r.get("category", ""), 99))
    return results


def fetch_rates_analytics() -> list[dict]:
    return _fetch_level_analytics(
        RATES_SERIES, ["T-Bills", "Notes", "Bonds", "Real"])


def fetch_funding_analytics() -> list[dict]:
    return _fetch_level_analytics(
        FUNDING_SERIES, ["Overnight", "Policy", "Bills/CP", "Intl", "Other"])


def fetch_spread_history_fred(series_id: str, years: int = 5) -> dict | None:
    """Return FRED time-series for a spread series in bps (for charting)."""
    dates, values = _fred_fetch_all(series_id)
    if dates is None:
        return None
    cutoff = datetime.date.today() - relativedelta(years=years)
    paired = [(d, v * 100) for d, v in zip(dates, values) if d >= cutoff]  # → bps
    if not paired:
        return None
    ds, vs = zip(*paired)
    return {"dates": [datetime.datetime.combine(d, datetime.time()) for d in ds],
            "values": list(vs)}


def fetch_spread_history(label: str, credit: str, treasury: str,
                         years: int = 3) -> dict | None:
    """ETF excess-return proxy (fallback / secondary chart)."""
    try:
        start = (datetime.datetime.today() - relativedelta(years=years)).strftime("%Y-%m-%d")
        c_hist = yf.Ticker(credit).history(start=start)["Close"]
        t_hist = yf.Ticker(treasury).history(start=start)["Close"]
        if c_hist.empty or t_hist.empty:
            return None
        if c_hist.index.tz is not None:
            c_hist.index = c_hist.index.tz_localize(None)
        if t_hist.index.tz is not None:
            t_hist.index = t_hist.index.tz_localize(None)
        idx   = c_hist.index.intersection(t_hist.index)
        c     = c_hist.reindex(idx)
        t     = t_hist.reindex(idx)
        excess = (c.pct_change().fillna(0).cumsum() -
                  t.pct_change().fillna(0).cumsum()) * 100
        return {
            "label":    label,
            "credit":   credit,
            "treasury": treasury,
            "dates":    list(idx.to_pydatetime()),
            "excess":   list(excess.values),
        }
    except Exception:
        return None
