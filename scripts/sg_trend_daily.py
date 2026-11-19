#!/usr/bin/env python
"""Daily SG Trend Indicator dataset (Société Générale, free public feed).

Pulls the SG Trend Indicator daily report CSV feeds and writes data/sg_trend.json, read by
the app's SG Trend monitor. The SG Trend Indicator is a transparent, rules-based medium-term
trend-following model; SG also publishes the SG CTA Index and SG Trend Index (peer-group
performance benchmarks). Source (public, no login):
  https://wholesale.banking.societegenerale.com/fileadmin/indices_feeds/ti_screen/

Feeds used:
  0.max_trade_date.txt                     latest trade date
  4.nav.csv                                index levels since 2000 (Indicator/CTA/Trend/S&P TR)
  1summary/1.<date>.summary.csv            headline Daily/MTD/YTD per index
  31sector/3.1.<date>.sector.csv           MTD/YTD contribution by asset class
  71market_table/7.1.<date>.market_table.csv  per-market Long/Short + days-in-position + P&L
  15.trades.csv                            recent position changes
"""
import datetime as dt
import json
import pathlib
import ssl
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sg_trend.json"
BASE = "https://wholesale.banking.societegenerale.com/fileadmin/indices_feeds/ti_screen/data/"
NAV_YEARS = 20                                    # trim NAV history to the last N years

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _CTX = ssl.create_default_context()

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/124.0 Safari/537.36")


def _get(path, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + path, headers={
                "User-Agent": _UA, "Accept": "text/csv,text/plain,*/*",
                "Referer": "https://wholesale.banking.societegenerale.com/fileadmin/indices_feeds/ti_screen/index.html"})
            return urllib.request.urlopen(req, timeout=40, context=_CTX).read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last if last else RuntimeError("no data")


def _num(s):
    """Parse ' 0.75628%' / '-2.01%' / '0.235979' / '' → float or None."""
    s = (s or "").strip().replace("%", "")
    if s in ("", "-", "null", "NaN"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _rows(csv, skip_header=False):
    lines = [l for l in csv.splitlines() if l.strip()]
    if skip_header and lines:
        lines = lines[1:]
    return [l.split(",") for l in lines]


def main():
    date = _get("0.max_trade_date.txt").strip()[:10]

    # ── NAV history (index levels) ──
    nav_csv = _get("4.nav.csv")
    nav_lines = [l for l in nav_csv.splitlines() if l.strip()]
    hdr = [h.strip() for h in nav_lines[0].split(",")]
    series_names = hdr[1:]                         # SG Trend Indicator, SG CTA Index, SG Trend Index, S&P 500 TR
    cutoff = (dt.date.today() - dt.timedelta(days=int(NAV_YEARS * 366))).isoformat()
    dates = []
    cols = {n: [] for n in series_names}
    for parts in (l.split(",") for l in nav_lines[1:]):
        d = parts[0].strip()[:10]
        if d < cutoff:
            continue
        dates.append(d)
        for i, n in enumerate(series_names):
            v = _num(parts[i + 1]) if i + 1 < len(parts) else None
            cols[n].append(round(v, 2) if v is not None else None)
    nav = {"dates": dates, "series": cols, "names": series_names}

    # ── Headline summary (Benchmark | Daily | MTD | YTD) ──
    summary = []
    for p in _rows(_get(f"1summary/1.{date}.summary.csv")):
        if p and p[0].strip():
            summary.append({"name": p[0].strip(),
                            "daily": _num(p[1]) if len(p) > 1 else None,
                            "mtd": _num(p[2]) if len(p) > 2 else None,
                            "ytd": _num(p[3]) if len(p) > 3 else None})

    # ── Sector contribution (fractions → %) ──
    sectors = []
    for p in _rows(_get(f"31sector/3.1.{date}.sector.csv"), skip_header=True):
        if len(p) >= 3 and p[0].strip():
            mtd = _num(p[1]); ytd = _num(p[2])
            sectors.append({"sector": p[0].strip(),
                            "mtd": round(mtd * 100, 2) if mtd is not None else None,
                            "ytd": round(ytd * 100, 2) if ytd is not None else None})

    # ── Per-market positioning (Long/Short, days, Daily/MTD/YTD %) ──
    markets = []
    for p in _rows(_get(f"71market_table/7.1.{date}.market_table.csv")):
        if len(p) >= 10 and p[2].strip():
            markets.append({"market": p[2].strip(), "position": p[3].strip(),
                            "days": int(_num(p[4]) or 0), "daily": _num(p[5]),
                            "mtd": _num(p[6]), "ytd": _num(p[7]),
                            "sector": p[8].strip(), "code": p[9].strip()})

    # ── Recent position changes (code, sector, market, date, new position) ──
    trades = []
    for p in _rows(_get("15.trades.csv")):
        if len(p) >= 5 and p[2].strip():
            trades.append({"sector": p[1].strip(), "market": p[2].strip(),
                           "date": p[3].strip()[:10], "position": p[4].strip()})
    trades.sort(key=lambda t: t["date"], reverse=True)

    out = {"asof": date, "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "source": "Société Générale — SG Trend Indicator (public daily feed)",
           "nav": nav, "summary": summary, "sectors": sectors,
           "markets": markets, "trades": trades[:40]}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out), encoding="utf-8")
    print(f"SG Trend {date}: {len(markets)} markets, {len(sectors)} sectors, {len(nav['dates'])} nav rows, "
          f"{len(trades)} trades -> {OUT} [{OUT.stat().st_size//1024} KB]")


if __name__ == "__main__":
    main()
