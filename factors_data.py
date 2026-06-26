"""
Academic long/short factor data.

Primary source: Kenneth French Data Library (Dartmouth) — free, no key.
  - Daily US factors:   Mkt-RF, SMB, HML, RMW, CMA, Mom, ST_Rev, LT_Rev
  - Monthly US factors: same set, longer history
  - Monthly regional:   Developed / Emerging 5-factor

Returns are L/S (dollar-neutral) portfolio returns in percent on FRED-style
download; we store them as DECIMAL periodic returns and compound for windows.

Other credible sources (AQR, Open Source Asset Pricing, JKP) are monthly and
either require registration (JKP) or very large downloads (OSAP); hooks are
left for future addition.
"""
import urllib.request
import io
import zipfile
import datetime
import statistics

_KF_BASE = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
_UA = "JAWS/1.0 jwill8817@gmail.com"
_TIMEOUT = 25

# (display_name, kf_zip_file, column_in_file)
KF_DAILY = [
    ("Market (Mkt-RF)", "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip", "Mkt-RF"),
    ("Size (SMB)",       "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip", "SMB"),
    ("Value (HML)",      "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip", "HML"),
    ("Profitability (RMW)","F-F_Research_Data_5_Factors_2x3_daily_CSV.zip","RMW"),
    ("Investment (CMA)", "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip", "CMA"),
    ("Momentum (Mom)",   "F-F_Momentum_Factor_daily_CSV.zip",            "Mom"),
    ("Short-Term Rev",   "F-F_ST_Reversal_Factor_daily_CSV.zip",         "ST_Rev"),
    ("Long-Term Rev",    "F-F_LT_Reversal_Factor_daily_CSV.zip",         "LT_Rev"),
]

KF_MONTHLY = [
    ("Market (Mkt-RF)", "F-F_Research_Data_5_Factors_2x3_CSV.zip", "Mkt-RF"),
    ("Size (SMB)",       "F-F_Research_Data_5_Factors_2x3_CSV.zip", "SMB"),
    ("Value (HML)",      "F-F_Research_Data_5_Factors_2x3_CSV.zip", "HML"),
    ("Profitability (RMW)","F-F_Research_Data_5_Factors_2x3_CSV.zip","RMW"),
    ("Investment (CMA)", "F-F_Research_Data_5_Factors_2x3_CSV.zip", "CMA"),
    ("Momentum (Mom)",   "F-F_Momentum_Factor_CSV.zip",            "Mom"),
    ("Short-Term Rev",   "F-F_ST_Reversal_Factor_CSV.zip",         "ST_Rev"),
    ("Long-Term Rev",    "F-F_LT_Reversal_Factor_CSV.zip",         "LT_Rev"),
    ("Dev Market",       "Developed_5_Factors_CSV.zip",            "Mkt-RF"),
    ("Dev Value (HML)",  "Developed_5_Factors_CSV.zip",            "HML"),
    ("Dev Momentum",     "Developed_Mom_Factor_CSV.zip",           "WML"),
    ("EM Market",        "Emerging_5_Factors_CSV.zip",             "Mkt-RF"),
    ("EM Value (HML)",   "Emerging_5_Factors_CSV.zip",             "HML"),
]

# In-process cache: filename -> {column: [(date, decimal_return), ...]}
_CACHE = {}

# ── AQR monthly factors (Excel downloads) ───────────────────
# (display_name, url, country_column, sign)
# sign=-1 flips AQR's "low minus high" BAB into "high minus low beta".
_AQR_BASE = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"
AQR_MONTHLY = [
    ("Quality H-L (QMJ)", _AQR_BASE + "Quality-Minus-Junk-Factors-Monthly.xlsx",
     "USA",  1, "AQR Quality-Minus-Junk (high quality − junk), US"),
    ("Betting-Against-Beta", _AQR_BASE + "Betting-Against-Beta-Equity-Factors-Monthly.xlsx",
     "USA", 1, "AQR Betting-Against-Beta (low-beta − high-beta), US"),
]
_AQR_CACHE = {}   # (url, column) -> [(date, decimal)]


def _fetch_aqr_series(url, column, sign=1):
    """Download an AQR monthly factor Excel and return [(date, decimal_return)]."""
    key = (url, column)
    if key in _AQR_CACHE:
        base = _AQR_CACHE[key]
    else:
        import openpyxl, io
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            raw = r.read()
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
        ws = wb[wb.sheetnames[0]]          # first sheet = "<FACTOR> Factors"
        rows = list(ws.iter_rows(values_only=True))
        hdr_i = next((i for i, rr in enumerate(rows)
                      if rr and rr[0] == "DATE"), None)
        base = []
        if hdr_i is not None:
            hdr = rows[hdr_i]
            if column in hdr:
                ci = hdr.index(column)
                for rr in rows[hdr_i + 1:]:
                    if ci >= len(rr):
                        continue
                    d, v = rr[0], rr[ci]
                    if d is None or not isinstance(v, (int, float)):
                        continue
                    if isinstance(v, bool):
                        continue
                    if isinstance(d, datetime.datetime):
                        dd = d.date()
                    elif isinstance(d, datetime.date):
                        dd = d
                    else:
                        try:
                            dd = datetime.datetime.strptime(str(d), "%m/%d/%Y").date()
                        except Exception:
                            continue
                    base.append((dd, float(v)))
        _AQR_CACHE[key] = base
    return [(d, v * sign) for d, v in base]


def _download_zip_csv(filename):
    """Download a Ken French zip and return the contained CSV text."""
    url = _KF_BASE + filename
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        raw = r.read()
    zf = zipfile.ZipFile(io.BytesIO(raw))
    name = zf.namelist()[0]
    return zf.read(name).decode("latin-1")


def _parse_kf_csv(text):
    """Parse a Ken French CSV → {column: [(date, decimal_return)]}.
    Stops at the first non-data block (e.g. the annual section)."""
    lines = text.splitlines()
    header = None
    start = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith(",") and any(c.isalpha() for c in s):
            header = [h.strip() for h in ln.split(",")]
            start = i + 1
            break
    if header is None:
        return {}
    cols = [c for c in header[1:] if c]   # drop leading empty cell

    dates, rows = [], []
    for ln in lines[start:]:
        parts = [p.strip() for p in ln.split(",")]
        tok = parts[0]
        if not tok or not tok.isdigit() or len(tok) not in (6, 8):
            break   # blank line or start of annual block → stop
        try:
            if len(tok) == 8:
                d = datetime.date(int(tok[:4]), int(tok[4:6]), int(tok[6:8]))
            else:
                d = datetime.date(int(tok[:4]), int(tok[4:6]), 1)
            vals = [float(x) for x in parts[1:1 + len(cols)]]
        except Exception:
            break
        dates.append(d)
        rows.append(vals)

    out = {}
    for ci, c in enumerate(cols):
        series = []
        for ri in range(len(dates)):
            v = rows[ri][ci]
            if v <= -99:        # KF missing-data sentinel
                continue
            series.append((dates[ri], v / 100.0))   # percent → decimal
        out[c] = series
    return out


def _get_file(filename):
    if filename not in _CACHE:
        _CACHE[filename] = _parse_kf_csv(_download_zip_csv(filename))
    return _CACHE[filename]


# ── Window return math ──────────────────────────────────────

def _cum_return(series, start_date=None, end_date=None):
    """Compound decimal returns in (start_date, end_date] → percent total."""
    prod = 1.0
    n = 0
    for d, r in series:
        if start_date is not None and d < start_date:
            continue
        if end_date is not None and d > end_date:
            continue
        prod *= (1.0 + r)
        n += 1
    return (prod - 1.0) * 100.0 if n else None


def _quarter_start(today):
    q_first_month = 3 * ((today.month - 1) // 3) + 1
    return datetime.date(today.year, q_first_month, 1)


def _window_returns(series, is_daily):
    """Compute the standard monitor windows for one factor series (percent)."""
    if not series:
        return {}
    today = series[-1][0]
    last_n = lambda n: _cum_return(series[-n:]) if len(series) >= 1 else None

    out = {}
    if is_daily:
        out["1D"] = series[-1][1] * 100.0
        out["1W"] = _cum_return(series[-5:])
        out["1M"] = _cum_return(series[-21:])
        out["3M"] = _cum_return(series[-63:])
        yr = 252
    else:
        out["1D"] = None
        out["1W"] = None
        out["1M"] = series[-1][1] * 100.0
        out["3M"] = _cum_return(series[-3:])
        yr = 12

    out["MTD"] = _cum_return(series, datetime.date(today.year, today.month, 1))
    out["QTD"] = _cum_return(series, _quarter_start(today))
    out["YTD"] = _cum_return(series, datetime.date(today.year, 1, 1))
    out["1Y"]  = _cum_return(series[-yr:])     if len(series) >= 2 else None
    out["3Y"]  = _cum_return(series[-yr*3:])
    out["5Y"]  = _cum_return(series[-yr*5:])
    out["7Y"]  = _cum_return(series[-yr*7:])
    out["10Y"] = _cum_return(series[-yr*10:])
    return out


def build_factor_row(name, series, is_daily, custom_start=None, custom_end=None):
    win = _window_returns(series, is_daily)
    if custom_start is not None:
        win["Custom"] = _cum_return(series, custom_start, custom_end)
    else:
        win["Custom"] = None

    # All-time min/max single-period return + annualized full-period stats
    rets = [r for _, r in series]
    out = {
        "name":       name,
        "is_daily":   is_daily,
        "windows":    win,
        "start":      str(series[0][0]) if series else "",
        "end":        str(series[-1][0]) if series else "",
        "n_obs":      len(series),
        "raw_dates":  [d for d, _ in series],
        "raw_rets":   rets,
    }
    return out


def fetch_factors(custom_start=None, custom_end=None, which="both"):
    """
    Returns dict with 'daily' and 'monthly' lists of factor rows.
    custom_start / custom_end: datetime.date for the Custom column.
    """
    result = {"daily": [], "monthly": []}

    if which in ("both", "daily"):
        for name, fn, col in KF_DAILY:
            try:
                data = _get_file(fn)
                series = data.get(col, [])
                if series:
                    result["daily"].append(
                        build_factor_row(name, series, True, custom_start, custom_end))
            except Exception as e:
                result["daily"].append({"name": name, "error": str(e), "is_daily": True})

    if which in ("both", "monthly"):
        for name, fn, col in KF_MONTHLY:
            try:
                data = _get_file(fn)
                series = data.get(col, [])
                if series:
                    result["monthly"].append(
                        build_factor_row(name, series, False, custom_start, custom_end))
            except Exception as e:
                result["monthly"].append({"name": name, "error": str(e), "is_daily": False})

        # AQR monthly factors (Quality-Minus-Junk, High−Low Beta)
        for name, url, col, sign, _desc in AQR_MONTHLY:
            try:
                series = _fetch_aqr_series(url, col, sign)
                if series:
                    result["monthly"].append(
                        build_factor_row(name, series, False, custom_start, custom_end))
            except Exception as e:
                result["monthly"].append({"name": name, "error": str(e), "is_daily": False})

    return result


def cumulative_series(raw_dates, raw_rets, start_date=None):
    """Return (dates, cumulative_pct) growth-of-1 series for charting."""
    ds, vs = [], []
    prod = 1.0
    started = start_date is None
    for d, r in zip(raw_dates, raw_rets):
        if start_date is not None and d < start_date:
            continue
        prod *= (1.0 + r)
        ds.append(d)
        vs.append((prod - 1.0) * 100.0)
    return ds, vs
