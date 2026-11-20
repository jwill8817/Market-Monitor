#!/usr/bin/env python
"""Point-in-time crowded-shorts index (FINRA).

At every bi-monthly FINRA Consolidated Short Interest report back to 2018, take that date's
most-shorted liquid US names, hold them equal-weight until the next report, then rebalance —
and chain-link daily into one index. This is a genuine point-in-time basket (the names that
were actually crowded-short at each date), not today's names projected backward. Writes
data/crowding_shorts_index.json, read by the app's Crowded Positioning panel.

Caveats: FINRA short interest is bi-monthly with a ~2-week settlement lag; the index holds from
the settlement date (a real strategy would lag slightly more). Delisted names are captured as
far as the price feed has data (a name that gap-delists mid-interval may miss its final leg) —
equal-weight, no costs. Treat as a positioning signal, not a tradeable product.
"""
import datetime as dt
import json
import pathlib
import ssl
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
import pandas as pd                       # noqa: E402

OUT = ROOT / "data" / "crowding_shorts_index.json"
START = "2018-01-01"            # earliest FINRA settlement date to include
TOP_N = 20                      # names per basket
MIN_ADV = 1_000_000            # liquidity floor (avg daily volume)
_OK_EXCH = {"NYSE", "NNM", "NMS", "NGS", "NCM", "AMEX"}

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _CTX = ssl.create_default_context()
_H = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Content-Type": "application/json"}


def _finra_dates():
    u = "https://api.finra.org/partitions/group/otcMarket/name/consolidatedShortInterest"
    parts = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=_H), timeout=30).read())
    dates = sorted({p["partitions"][0] for p in parts.get("availablePartitions", [])})
    return [d for d in dates if d >= START]


def _finra_basket(date):
    body = {"limit": TOP_N * 4,
            "compareFilters": [
                {"fieldName": "settlementDate", "compareType": "EQUAL", "fieldValue": date},
                {"fieldName": "averageDailyVolumeQuantity", "compareType": "GTE", "fieldValue": MIN_ADV}],
            "sortFields": ["-currentShortPositionQuantity"]}
    req = urllib.request.Request(
        "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest",
        data=json.dumps(body).encode(), headers=_H, method="POST")
    for attempt in range(3):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=30, context=_CTX).read())
            d = d if isinstance(d, list) else d.get("data", [])
            syms = [x.get("symbolCode", "").strip() for x in d
                    if x.get("marketClassCode") in _OK_EXCH and x.get("symbolCode")]
            # de-dupe, keep order, cap at TOP_N
            seen = set(); out = []
            for s in syms:
                if s not in seen:
                    out.append(s); seen.add(s)
                if len(out) >= TOP_N:
                    break
            return out
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return []


def main():
    import market_data as md
    dates = _finra_dates()
    print(f"FINRA settlement dates since {START}: {len(dates)}")
    baskets = {}
    for i, d in enumerate(dates):
        baskets[d] = _finra_basket(d)
        if i % 25 == 0:
            print(f"  {d}: {len(baskets[d])} names ({i+1}/{len(dates)})")
    union = sorted({s for b in baskets.values() for s in b})
    print(f"Unique names ever in basket: {len(union)}")

    # Batch price history for the whole union (daily closes, dividend-adjusted).
    px = md.price_histories(union, start=(pd.Timestamp(dates[0]) - pd.Timedelta(days=10)).date().isoformat())
    P = pd.DataFrame({s: px[s] for s in union if s in px and not px[s].empty}).sort_index()
    P = P[~P.index.duplicated(keep="last")]
    R = P.pct_change(fill_method=None)      # don't carry stale prices across gaps/delistings

    settle_ts = [pd.Timestamp(d) for d in dates]
    days = R.index[R.index >= settle_ts[0]]
    idx_dates, idx_vals = [], []
    cover = []
    I = 100.0
    bi = 0
    for j, day in enumerate(days):
        # active basket = names as of the most recent settlement on/before `day`
        while bi + 1 < len(settle_ts) and settle_ts[bi + 1] <= day:
            bi += 1
        active = [s for s in baskets[dates[bi]] if s in R.columns]
        if j == 0:
            idx_dates.append(day); idx_vals.append(round(I, 3)); cover.append(len(active)); continue
        rets = [R.at[day, s] for s in active if pd.notna(R.at[day, s])]
        if rets:
            I *= (1.0 + sum(rets) / len(rets))
        idx_dates.append(day); idx_vals.append(round(I, 3)); cover.append(len(rets))

    out = {
        "asof": dates[-1],
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "top_n": TOP_N, "min_adv": MIN_ADV, "n_reports": len(dates),
        "latest_basket": baskets[dates[-1]],
        "dates": [d.date().isoformat() for d in idx_dates],
        "level": idx_vals,
        "coverage": cover,          # names with price data contributing each day
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out), encoding="utf-8")
    last = idx_vals[-1] if idx_vals else None
    print(f"Crowded-shorts index: {len(idx_dates)} days, latest level {last} "
          f"(=100 at {idx_dates[0].date()}), {len(union)} names -> {OUT} [{OUT.stat().st_size//1024} KB]")


if __name__ == "__main__":
    main()
