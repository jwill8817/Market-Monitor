#!/usr/bin/env python
"""Daily CFTC Commitments of Traders (COT) positioning dataset.

Pulls net speculative positioning for key futures from the CFTC open-data API (free):
  - Financials (TFF report, Leveraged Funds): equity indexes, VIX, Treasuries, FX, USD index
  - Commodities (Disaggregated report, Managed Money): crude, nat gas, metals
Net = long − short. Writes data/cot.json (3y weekly history per market), read by the app.
COT is published weekly (Friday, for Tuesday positions), so a daily run always has the latest.
"""
import datetime
import json
import pathlib
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cot.json"


def _get(ds, params):
    import time
    u = f"https://publicreporting.cftc.gov/resource/{ds}.json?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(u, headers={"User-Agent": "JAWS/1.0", "Accept": "application/json"})
    last = None
    for attempt in range(4):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=45).read())
            if isinstance(d, list):
                return d
            last = RuntimeError(str(d)[:120])          # error object, not a result list
        except Exception as e:
            last = e
        time.sleep(1.5 * (attempt + 1))
    raise last if last else RuntimeError("no data")


# (socrata id, long field, short field, category, [(display, like_kw, include_token, exclude_token), ...])
# like_kw avoids "U.S." (periods break the SoQL like); include/exclude disambiguate contracts.
GROUPS = [
    ("gpe5-46if", "lev_money_positions_long", "lev_money_positions_short", "Leveraged funds (financials)", [
        ("S&P 500", "E-MINI S&P 500", "E-MINI S&P 500", "MICRO"),
        ("Nasdaq 100", "NASDAQ-100", "NASDAQ-100", "MICRO"),
        ("Russell 2000", "RUSSELL 2000", "RUSSELL 2000", "DIVIDEND"),
        ("VIX", "VIX FUTURES", "VIX", ""),
        ("Euro FX", "EURO FX", "EURO FX", "/"),
        ("Yen", "JAPANESE YEN", "JAPANESE YEN", "/"),
        ("Pound", "BRITISH POUND", "BRITISH POUND", "/"),
    ]),
    ("72hh-3qpy", "m_money_positions_long_all", "m_money_positions_short_all", "Managed money (commodities)", [
        ("Crude (WTI)", "CRUDE OIL, LIGHT SWEET", "CRUDE OIL, LIGHT SWEET", "MICRO"),
        ("Gold", "GOLD", "GOLD - COMMODITY", "MICRO"),
        ("Silver", "SILVER", "SILVER - COMMODITY", "MICRO"),
        ("Copper", "COPPER", "COPPER", "MICRO"),
    ]),
]


def _market_series(ds, like_kw, include, exclude, lf, sf):
    """Fetch rows for markets matching `like_kw`, keep names containing `include` and not
    `exclude`, pick the one with the longest history (the primary continuous contract), and
    return (name, [[date, net], ...]) over ~3y of weekly history."""
    rows = _get(ds, {"$select": f"market_and_exchange_names,report_date_as_yyyy_mm_dd,{lf},{sf}",
                     "$where": f"upper(market_and_exchange_names) like '%{like_kw.upper()}%'",
                     "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": "6000"})
    if not rows:
        return None, None
    inc, exc = include.upper(), (exclude or "").upper()
    cutoff = (datetime.date.today() - datetime.timedelta(days=3 * 366 + 10)).isoformat()
    counts = {}                                           # in-window rows per matching contract
    for r in rows:
        nm = r["market_and_exchange_names"]; up = nm.upper()
        if inc in up and (not exc or exc not in up) and r["report_date_as_yyyy_mm_dd"][:10] >= cutoff:
            counts[nm] = counts.get(nm, 0) + 1
    if not counts:
        return None, None
    nm = max(counts, key=counts.get)                      # the active (most in-window data) contract
    pts = [[r["report_date_as_yyyy_mm_dd"][:10], float(r.get(lf, 0) or 0) - float(r.get(sf, 0) or 0)]
           for r in rows if r["market_and_exchange_names"] == nm and r["report_date_as_yyyy_mm_dd"][:10] >= cutoff]
    pts.sort()
    return nm, pts


def main():
    out = {"asof": None, "markets": []}
    for ds, lf, sf, cat, mkts in GROUPS:
        for disp, like_kw, include, exclude in mkts:
            try:
                nm, pts = _market_series(ds, like_kw, include, exclude, lf, sf)
                if not nm or not pts:
                    print(f"  {disp}: no match"); continue
                out["markets"].append({"name": disp, "category": cat, "contract": nm, "points": pts})
                if out["asof"] is None or pts[-1][0] > out["asof"]:
                    out["asof"] = pts[-1][0]
                print(f"  {disp:12s} {nm[:34]:34s} n={len(pts)} net={pts[-1][1]:+.0f}")
            except Exception as e:
                print(f"  {disp}: ERROR {e}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out), encoding="utf-8")
    print(f"Wrote {len(out['markets'])} markets (asof {out['asof']}) -> {OUT}")


if __name__ == "__main__":
    main()
