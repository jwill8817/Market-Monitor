"""
Futures curves, roll yield, and rate-expectations data.

Free / redistribution-safe sources only (fits the public shared app):
  • VIX term structure — CBOE constant-maturity index CSVs (cdn.cboe.com), no key.
  • Energy futures curve (WTI / Henry Hub, contracts 1-4) — EIA API, free key.
  • Fed expectations — FRED Treasury/EFFR (auto expected-rate PATH), plus a
    credential-gated futures path (Fed Funds / SOFR) that computes true FedWatch
    style probabilities when a futures-data key or an uploaded ZQ strip is present.

Design: everything degrades gracefully. Missing key / blocked host → the feature
returns None with a reason, never raises.
"""
import os
import io
import csv
import json
import datetime
import urllib.request
import urllib.parse

_UA = {"User-Agent": "Mozilla/5.0 (JAWS Market Monitor)"}
_TIMEOUT = 12


def _cfg(key, default=""):
    """Prefer Streamlit secrets when in the web app, else environment."""
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)


# ══════════════════════════════════════════════════════════════════
# 1) VIX TERM STRUCTURE  (CBOE constant-maturity indices — free, no key)
# ══════════════════════════════════════════════════════════════════
# (label, cboe symbol, constant maturity in calendar days)
_VIX_TERM = [
    ("VIX9D  (9-day)",   "VIX9D", 9),
    ("VIX    (30-day)",  "VIX",   30),
    ("VIX3M  (3-month)", "VIX3M", 93),
    ("VIX6M  (6-month)", "VIX6M", 184),
    ("VIX1Y  (1-year)",  "VIX1Y", 365),
]

def _cboe_last_close(sym):
    """Return (date, close) for the latest row of a CBOE index history CSV."""
    url = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{sym}_History.csv"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        text = r.read().decode("utf-8", "ignore")
    rows = list(csv.reader(io.StringIO(text)))
    if len(rows) < 2:
        return None, None
    header = [h.strip().upper() for h in rows[0]]
    ci = header.index("CLOSE") if "CLOSE" in header else len(rows[0]) - 1
    for row in reversed(rows[1:]):
        if len(row) <= ci:
            continue
        try:
            val = float(row[ci])
        except Exception:
            continue
        d = row[0].strip()
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                d = datetime.datetime.strptime(d, fmt).date(); break
            except Exception:
                pass
        return d, val
    return None, None

def fetch_vix_term_structure():
    """Latest VIX constant-maturity term structure.
    Returns {'points':[(label, days, level)], 'as_of':date, 'error':str?}."""
    pts = []; as_of = None
    for label, sym, days in _VIX_TERM:
        try:
            d, v = _cboe_last_close(sym)
            if v is not None:
                pts.append((label, days, v))
                if d and (as_of is None or d > as_of):
                    as_of = d
        except Exception:
            continue
    if not pts:
        return {"points": [], "as_of": None, "error": "CBOE feed unavailable"}
    return {"points": pts, "as_of": as_of, "error": None}

def fetch_vix_history(sym):
    """Full daily close history for one CBOE vol index (for the slope time series)."""
    url = f"https://cdn.cboe.com/api/global/us_indices/daily_prices/{sym}_History.csv"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        text = r.read().decode("utf-8", "ignore")
    rows = list(csv.reader(io.StringIO(text)))
    header = [h.strip().upper() for h in rows[0]]
    ci = header.index("CLOSE") if "CLOSE" in header else len(rows[0]) - 1
    out = []
    for row in rows[1:]:
        if len(row) <= ci:
            continue
        try:
            v = float(row[ci])
        except Exception:
            continue
        d = row[0].strip()
        for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
            try:
                d = datetime.datetime.strptime(d, fmt).date(); break
            except Exception:
                pass
        if isinstance(d, datetime.date):
            out.append((d, v))
    return out


# ══════════════════════════════════════════════════════════════════
# 2) ENERGY FUTURES CURVE + ROLL YIELD  (EIA API — free key)
# ══════════════════════════════════════════════════════════════════
# EIA legacy series ids: WTI crude contracts 1-4 and Henry Hub nat gas 1-4.
_EIA_PRODUCTS = {
    "WTI Crude ($/bbl)":   ["RCLC1", "RCLC2", "RCLC3", "RCLC4"],
    "Henry Hub Gas ($/MMBtu)": ["RNGC1", "RNGC2", "RNGC3", "RNGC4"],
}

def eia_enabled():
    return bool(_cfg("EIA_API_KEY"))

def _eia_series(series_id, key):
    """Latest value + date for one EIA legacy series id via the v2 seriesid route."""
    url = (f"https://api.eia.gov/v2/seriesid/{series_id}"
           f"?api_key={key}&sort[0][column]=period&sort[0][direction]=desc&length=1")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        j = json.loads(r.read())
    data = (j.get("response") or {}).get("data") or []
    if not data:
        return None, None
    row = data[0]
    val = row.get("value")
    return (row.get("period"), float(val)) if val is not None else (row.get("period"), None)

def fetch_energy_curve():
    """{product: {'contracts':[(n, price)], 'roll_yield_pct':x, 'as_of':date}} or error."""
    key = _cfg("EIA_API_KEY")
    if not key:
        return {"error": "no_key"}
    out = {"error": None}
    for prod, sids in _EIA_PRODUCTS.items():
        contracts = []; as_of = None
        for n, sid in enumerate(sids, start=1):
            try:
                period, val = _eia_series(sid, key)
                if val is not None:
                    contracts.append((n, val))
                    if period and (as_of is None or str(period) > str(as_of)):
                        as_of = period
            except Exception:
                continue
        roll = None
        if len(contracts) >= 2:
            c1 = contracts[0][1]; c2 = contracts[1][1]
            # Front-to-next annualized roll yield (≈ monthly gap × 12).
            if c2:
                roll = (c1 - c2) / c2 * 100 * 12
        out[prod] = {"contracts": contracts, "roll_yield_pct": roll, "as_of": as_of}
    return out


# ══════════════════════════════════════════════════════════════════
# 3) FED RATE EXPECTATIONS
#    (a) auto, free: expected-rate PATH from FRED Treasury/EFFR
#    (b) credential-gated / upload: true FedWatch-style probabilities
# ══════════════════════════════════════════════════════════════════
def _fred_latest(series_id):
    import fi_spreads as fs
    d, v = fs._fred_fetch_all(series_id)
    if not d:
        return None, None
    return d[-1], v[-1]

# Short Treasury points used as a market-implied average-rate path proxy.
_PATH_POINTS = [("Now (EFFR)", "DFF", 0.0), ("3M", "DGS3MO", 0.25), ("6M", "DGS6MO", 0.5),
                ("1Y", "DGS1", 1.0), ("2Y", "DGS2", 2.0)]

def fetch_rate_expectation_path():
    """Market-implied expected average-rate path from the front Treasury curve + EFFR.
    Honest approximation (embeds term/liquidity premium) — NOT meeting probabilities."""
    pts = []; effr = None; as_of = None
    for label, sid, yrs in _PATH_POINTS:
        try:
            d, v = _fred_latest(sid)
            if v is None:
                continue
            if sid == "DFF":
                effr = v
            pts.append((label, yrs, v))
            if d and (as_of is None or str(d) > str(as_of)):
                as_of = d
        except Exception:
            continue
    if not pts:
        return {"points": [], "effr": None, "as_of": None, "error": "FRED unavailable"}
    return {"points": pts, "effr": effr, "as_of": as_of, "error": None}


# ── FedWatch-style probability engine (works on any ZQ strip) ──
def _current_target_mid():
    """Current fed funds target midpoint from FRED (upper+lower)/2, fallback to EFFR."""
    try:
        _, up = _fred_latest("DFEDTARU"); _, lo = _fred_latest("DFEDTARL")
        if up is not None and lo is not None:
            return (up + lo) / 2.0
    except Exception:
        pass
    _, effr = _fred_latest("DFF")
    return effr

def fedwatch_probabilities(strip, step=0.25):
    """Compute step-by-step implied hike/cut probabilities from a Fed Funds futures strip.

    strip: list of (contract_month 'YYYY-MM', implied_avg_rate_pct) in ascending month order.
           implied_avg_rate = 100 - ZQ settlement price.
    Simplified month-over-month method: the change in implied average rate between
    consecutive contract months approximates the expected policy move priced for a
    meeting in that window; P(move) = |Δ| / step (capped at 1), direction by sign.
    Returns list of {'month','implied_rate','delta_bps','p_move','direction'}.
    NOTE: this is the transparent monthly approximation. A meeting-date-weighted
    version (splitting a month by the FOMC date) is the exact FedWatch refinement.
    """
    out = []
    prev = None
    for month, rate in strip:
        row = {"month": month, "implied_rate": round(rate, 3)}
        if prev is not None:
            delta = rate - prev
            row["delta_bps"] = round(delta * 100, 1)
            row["p_move"] = round(min(abs(delta) / step, 1.0) * 100, 1)
            row["direction"] = "hike" if delta > 0.01 else ("cut" if delta < -0.01 else "hold")
        else:
            row["delta_bps"] = 0.0; row["p_move"] = 0.0; row["direction"] = "base"
        out.append(row)
        prev = rate
    return out

def futures_key_enabled():
    return bool(_cfg("BARCHART_API_KEY") or _cfg("FUTURES_API_KEY"))

# ── FOMC meeting calendar (announcement / 2nd-day dates) ──
# 2025–2026 are the Fed's published dates; 2027 are the tentative schedule.
FOMC_DATES = [
    (2025,1,29),(2025,3,19),(2025,5,7),(2025,6,18),(2025,7,30),(2025,9,17),(2025,10,29),(2025,12,10),
    (2026,1,28),(2026,3,18),(2026,4,29),(2026,6,17),(2026,7,29),(2026,9,16),(2026,10,28),(2026,12,9),
    (2027,1,27),(2027,3,17),(2027,4,28),(2027,6,16),(2027,7,28),(2027,9,22),(2027,10,27),(2027,12,8),
]

def _next_month(ym):
    y, m = int(ym[:4]), int(ym[5:7])
    m += 1
    if m > 12: m = 1; y += 1
    return f"{y:04d}-{m:02d}"

def _distribute(change_pct, step=0.25):
    """Split an expected rate change across the two bracketing 25bp grid points."""
    import math
    if abs(change_pct) < 0.005:
        return {0.0: 1.0}
    lo = math.floor(round(change_pct / step, 6)) * step
    hi = lo + step
    p_hi = (change_pct - lo) / step
    p_hi = min(max(p_hi, 0.0), 1.0)
    return {round(lo, 4): round(1 - p_hi, 4), round(hi, 4): round(p_hi, 4)}

def fedwatch_meeting_probs(strip, step=0.25, start_rate=None):
    """Meeting-date-weighted FedWatch probabilities (the exact CME approach).

    For each FOMC meeting, the contract month's implied average rate is split by the
    meeting day: avg = (d/N)·r_in + ((N-d)/N)·r_out, solved for r_out. The per-meeting
    expected change is then distributed over the nearest 25bp outcomes. r_out chains
    forward as the next meeting's r_in.
    strip: [(YYYY-MM, implied_avg_rate)] ascending. Returns list of per-meeting dicts."""
    import calendar
    if not strip:
        return []
    imp = {m: r for m, r in strip}
    first_month = min(imp)
    if start_rate is None:
        _, effr = _fred_latest("DFF")
        start_rate = effr if effr is not None else strip[0][1]
    r_prev = float(start_rate); out = []
    for (yy, mm, dd) in FOMC_DATES:
        ym = f"{yy:04d}-{mm:02d}"
        if ym < first_month:
            continue
        if ym not in imp:
            break
        N = calendar.monthrange(yy, mm)[1]
        w_after = (N - dd) / N
        avg_M = imp[ym]; nxt = _next_month(ym)
        if w_after < 0.25 and nxt in imp:       # meeting late in month → use next month
            r_end = imp[nxt]
        elif w_after <= 0:
            r_end = imp.get(nxt, avg_M)
        else:
            r_end = (avg_M - (dd / N) * r_prev) / w_after
        change = r_end - r_prev
        probs = _distribute(change, step)
        best = max(probs, key=probs.get)
        out.append({
            "date": f"{yy:04d}-{mm:02d}-{dd:02d}",
            "r_in": round(r_prev, 3), "r_out": round(r_end, 3),
            "change_bps": round(change * 100, 1),
            "outcomes": {f"{int(round(k*100)):+d}": round(v * 100, 1)
                         for k, v in sorted(probs.items())},
            "most_likely_bps": int(round(best * 100)),
            "p_most": round(probs[best] * 100, 1),
        })
        r_prev = r_end
    return out

def _yahoo_last(sym):
    """Latest price for a Yahoo symbol via the public chart endpoint, or None."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?range=5d&interval=1d")
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        j = json.loads(r.read())
    res = (j.get("chart") or {}).get("result")
    if not res:
        return None
    meta = res[0].get("meta") or {}
    px = meta.get("regularMarketPrice")
    if px is not None:
        return float(px)
    # fallback: last non-null close
    try:
        closes = res[0]["indicators"]["quote"][0]["close"]
        for c in reversed(closes):
            if c is not None:
                return float(c)
    except Exception:
        pass
    return None

def fetch_zq_strip(n=16):
    """30-Day Fed Funds (ZQ) monthly strip, FREE & automated via Yahoo dated contracts
    (symbols like ZQN26.CBT). Returns [(month 'YYYY-MM', implied_avg_rate)] or None.

    implied_avg_rate = 100 - settlement price. Prices are delayed (fine for FedWatch,
    which uses daily settlements). Falls back to a credential-gated vendor if configured
    and Yahoo is unavailable."""
    strip = []
    for sym in _zq_symbols(n):                      # e.g. ZQN26 -> ZQN26.CBT
        try:
            px = _yahoo_last(f"{sym}.CBT")
            if px is not None and 80.0 < px < 101.0:
                strip.append((_zq_month_from_symbol(sym), 100.0 - px))
        except Exception:
            continue
    strip = [s for s in strip if s[0]]
    strip.sort()
    if strip:
        return strip
    return _fetch_zq_strip_vendor()

def _fetch_zq_strip_vendor():
    """Optional credential-gated vendor fallback (dormant unless a key is set)."""
    key = _cfg("BARCHART_API_KEY")
    if not key:
        return None
    try:
        months = _zq_symbols(12)
        url = ("https://marketdata.websol.barchart.com/getQuote.json?"
               + urllib.parse.urlencode({"apikey": key, "symbols": ",".join(months)}))
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            j = json.loads(r.read())
        strip = []
        for res in j.get("results", []):
            last = res.get("lastPrice") or res.get("settlement")
            sym = res.get("symbol", "")
            if last is not None:
                strip.append((_zq_month_from_symbol(sym), 100.0 - float(last)))
        strip = [s for s in strip if s[0]]
        strip.sort()
        return strip or None
    except Exception:
        return None

_MCODE = {1:"F",2:"G",3:"H",4:"J",5:"K",6:"M",7:"N",8:"Q",9:"U",10:"V",11:"X",12:"Z"}
_MCODE_INV = {v: k for k, v in _MCODE.items()}

def _zq_symbols(n):
    today = datetime.date.today()
    out = []
    y, m = today.year, today.month
    for _ in range(n):
        out.append(f"ZQ{_MCODE[m]}{str(y)[-2:]}")
        m += 1
        if m > 12:
            m = 1; y += 1
    return out

def _zq_month_from_symbol(sym):
    # ZQ + monthcode + 2-digit year  ->  'YYYY-MM'
    try:
        code = sym[2]; yy = int(sym[3:5]); mm = _MCODE_INV[code]
        return f"20{yy:02d}-{mm:02d}"
    except Exception:
        return None

def parse_zq_upload(rows):
    """Turn an uploaded/pasted table into a strip.
    Accepts rows of (month_or_symbol, price_or_rate). If value>50 assume it's a ZQ
    price (implied = 100 - price); else treat as an implied rate already."""
    strip = []
    for a, b in rows:
        a = str(a).strip()
        try:
            v = float(b)
        except Exception:
            continue
        month = a if "-" in a else _zq_month_from_symbol(a)
        if not month:
            continue
        rate = (100.0 - v) if v > 50 else v
        strip.append((month, rate))
    strip.sort()
    return strip
