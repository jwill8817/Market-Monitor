"""
Yield curve fetchers for:
  - US Treasury nominal par yield curve   (13 maturities incl. 4Mo)
  - US Treasury TIPS real yield curve     (5 maturities)
  - Municipal proxy curve                 (6 duration buckets via ETF SEC yields)
"""
import requests
import re
from datetime import datetime, timedelta
import time

# ── URLs ──────────────────────────────────────────────────────
_TREASURY_BASE = ("https://home.treasury.gov/resource-center/data-chart-center/"
                  "interest-rates/TextView?type={curve_type}&field_tdr_date_value={ym}")

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── Nominal Treasury curve ────────────────────────────────────
MATURITIES = ["1 Mo","2 Mo","3 Mo","4 Mo","6 Mo",
              "1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"]

_NOM_COL_MAP = {
    "1 Mo":  ["tc1month",  "1month"],
    "2 Mo":  ["tc2month",  "2month"],
    "3 Mo":  ["tc3month",  "3month"],
    "4 Mo":  ["tc4month",  "4month"],
    "6 Mo":  ["tc6month",  "6month"],
    "1 Yr":  ["tc1year",   "1year"],
    "2 Yr":  ["tc2year",   "2year"],
    "3 Yr":  ["tc3year",   "3year"],
    "5 Yr":  ["tc5year",   "5year"],
    "7 Yr":  ["tc7year",   "7year"],
    "10 Yr": ["tc10year",  "10year"],
    "20 Yr": ["tc20year",  "20year"],
    "30 Yr": ["tc30year",  "30year"],
}

# ── TIPS real yield curve ──────────────────────────────────────
TIPS_MATURITIES = ["5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"]

_TIPS_COL_MAP = {
    "5 Yr":  ["tc5year",  "5year"],
    "7 Yr":  ["tc7year",  "7year"],
    "10 Yr": ["tc10year", "10year"],
    "20 Yr": ["tc20year", "20year"],
    "30 Yr": ["tc30year", "30year"],
}

# ── Muni proxy curve — iShares/Vanguard ETF SEC 30-day yields ─
# These are fetched separately via _fetch_muni_curve()
MUNI_MATURITIES = ["0-2 Yr","2-5 Yr","5-10 Yr","10-15 Yr","15-20 Yr","20+ Yr"]

# ETFs mapped to approximate duration buckets for the muni curve
_MUNI_ETFS = {
    "0-2 Yr":   ("SHM",  "SPDR Short-Term Muni"),
    "2-5 Yr":   ("SUB",  "iShares Short IG Muni"),
    "5-10 Yr":  ("ITM",  "iShares Natl Muni 5-10"),
    "10-15 Yr": ("MUB",  "iShares Natl Muni Blend"),
    "15-20 Yr": ("TFI",  "SPDR Nuveen Muni"),
    "20+ Yr":   ("MLN",  "WisdomTree Muni Yield"),
}

# yfinance fallback for nominal curve (4 maturities only)
_YF_FALLBACK = {
    "3 Mo": "^IRX", "5 Yr": "^FVX",
    "10 Yr": "^TNX", "30 Yr": "^TYX",
}


def _scrape_table(curve_type, target_date, col_map, maturities_list,
                  max_lookback_months=3):
    """Generic Treasury HTML table scraper. Returns list of row dicts."""
    from bs4 import BeautifulSoup

    for offset in range(max_lookback_months + 1):
        month = target_date.month - offset
        year  = target_date.year
        while month <= 0:
            month += 12; year -= 1
        ym  = f"{year}{month:02d}"
        url = _TREASURY_BASE.format(curve_type=curve_type, ym=ym)
        try:
            r = requests.get(url, headers=_HEADERS, timeout=18)
            if r.status_code != 200:
                time.sleep(0.1); continue
            soup  = BeautifulSoup(r.text, "lxml")
            table = soup.find("table")
            if not table:
                continue

            # Map column index from header
            headers = table.find_all("th")
            col_idx = {}
            for i, th in enumerate(headers):
                cls_str  = " ".join(th.get("class", [])).lower()
                txt_str  = th.get_text(strip=True).lower().replace(" ", "")
                for mat, aliases in col_map.items():
                    for alias in aliases:
                        if alias in cls_str or alias in txt_str:
                            col_idx[mat] = i
                            break

            rows = []
            for tr in table.find_all("tr")[1:]:
                cells = tr.find_all("td")
                if not cells: continue
                try:
                    dt = datetime.strptime(cells[0].get_text(strip=True), "%m/%d/%Y")
                    date_str = dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
                yields = {}
                for mat, idx in col_idx.items():
                    if idx < len(cells):
                        txt = cells[idx].get_text(strip=True)
                        try: yields[mat] = float(txt) if txt else None
                        except ValueError: yields[mat] = None
                    else:
                        yields[mat] = None
                rows.append({"date": date_str, "yields": yields})

            rows.sort(key=lambda x: x["date"])
            dstr  = target_date.strftime("%Y-%m-%d")
            match = [row for row in rows if row["date"] <= dstr]
            if match:
                return match[-1]
        except Exception:
            pass
        time.sleep(0.1)
    return None


def _yf_fallback(target_date):
    """4-point nominal curve from yfinance when Treasury scrape fails."""
    import yfinance as yf
    yields   = {m: None for m in MATURITIES}
    date_str = target_date.strftime("%Y-%m-%d")
    start    = (target_date - timedelta(days=14)).strftime("%Y-%m-%d")
    end      = (target_date + timedelta(days=2)).strftime("%Y-%m-%d")
    for mat, sym in _YF_FALLBACK.items():
        try:
            hist = yf.Ticker(sym).history(start=start, end=end)
            if hist.empty: continue
            hist.index = hist.index.tz_localize(None) if hist.index.tzinfo else hist.index
            sub = hist[hist.index.strftime("%Y-%m-%d") <= date_str]
            if not sub.empty:
                yields[mat] = round(float(sub["Close"].iloc[-1]), 2)
        except Exception:
            pass
    return {"date": date_str, "yields": yields, "source": "yfinance (partial)"}


# ── Public API ────────────────────────────────────────────────

def fetch_curve_for_date(target_date: datetime):
    """Nominal par yield curve (13 maturities). Falls back to yfinance."""
    row = _scrape_table("daily_treasury_yield_curve", target_date,
                        _NOM_COL_MAP, MATURITIES)
    if row and any(v is not None for v in row["yields"].values()):
        row["source"] = "US Treasury"
        return row
    return _yf_fallback(target_date)


def fetch_tips_curve_for_date(target_date: datetime):
    """TIPS real yield curve (5 maturities: 5, 7, 10, 20, 30 Yr)."""
    row = _scrape_table("daily_treasury_real_yield_curve", target_date,
                        _TIPS_COL_MAP, TIPS_MATURITIES)
    if row and any(v is not None for v in row["yields"].values()):
        row["source"] = "US Treasury (TIPS)"
        row["curve_type"] = "tips"
        return row
    return None


def fetch_muni_curve(target_date: datetime = None):
    """
    Proxy muni curve built from yfinance ETF 30-day SEC yield proxies.
    Uses ETF price-based yield estimate (not official SEC yield).
    Returns same dict format as fetch_curve_for_date.
    """
    import yfinance as yf
    if target_date is None:
        target_date = datetime.today()
    date_str = target_date.strftime("%Y-%m-%d")
    start    = (target_date - timedelta(days=14)).strftime("%Y-%m-%d")
    end      = (target_date + timedelta(days=2)).strftime("%Y-%m-%d")

    # We use the 12-month trailing yield implied by dividend / price
    yields = {m: None for m in MUNI_MATURITIES}
    for bucket, (ticker, _name) in _MUNI_ETFS.items():
        try:
            t    = yf.Ticker(ticker)
            info = t.info
            # SEC yield fields yfinance may expose
            for key in ("yield", "trailingAnnualDividendYield",
                        "dividendYield", "fiveYearAvgDividendYield"):
                val = info.get(key)
                if val and 0 < val < 1:     # expressed as decimal
                    yields[bucket] = round(val * 100, 2)
                    break
                elif val and 1 < val < 20:  # already in %
                    yields[bucket] = round(float(val), 2)
                    break
        except Exception:
            pass

    if not any(v is not None for v in yields.values()):
        return None

    return {
        "date":       date_str,
        "yields":     yields,
        "source":     "ETF yield proxy (MUB/SHM/ITM/TFI…)",
        "curve_type": "muni",
    }


def fetch_curves(periods: dict) -> dict:
    return {label: fetch_curve_for_date(dt) for label, dt in periods.items()}
