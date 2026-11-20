#!/usr/bin/env python
"""Point-in-time JAWS Crowded Short Index (FINRA).

At every bi-monthly FINRA Consolidated Short Interest report back to 2018, build a basket of the
most-crowded shorts and hold it equal-weight until the next report, rebalancing each time and
chain-linking daily into one index. Genuine point-in-time construction (the names actually
crowded-short at each date), not today's names projected backward. Writes
data/crowding_shorts_index.json, read by the app (symbol JCSI).

Construction (de-noised via a liquidity floor so the index isn't dominated by one illiquid name
or sector — a volume floor naturally spreads the basket across sectors):
  - rank by DAYS-TO-COVER (shares short / avg daily volume) — size/liquidity-neutral crowding,
    winsorized at DTC_CAP so one ultra-thin name can't top the list
  - liquidity floor: avg daily volume >= MIN_ADV shares AND dollar-volume >= DOLLARVOL_MIN/day
  - TOP_N names, equal-weight, US-listed only

Caveats: FINRA short interest is bi-monthly with a ~2-week settlement lag (index holds from the
settlement date). Equal-weight, no costs; delisted names captured as far as the price feed has
data. A positioning signal / index, not a tradeable product.
"""
import datetime as dt
import json
import pathlib
import ssl
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd                       # noqa: E402

OUT = ROOT / "data" / "crowding_shorts_index.json"
START = "2018-01-01"
TOP_N = 25
MIN_ADV = 2_000_000           # shares/day
DOLLARVOL_MIN = 10_000_000    # $/day (price x ADV at the report date)
DTC_CAP = 40.0               # winsorize days-to-cover for ranking (illiquidity-artifact guard)
CAND_LIMIT = 150             # candidates pulled per report (by DTC) before the liquidity filter
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
    ds = sorted({p["partitions"][0] for p in parts.get("availablePartitions", [])})
    return [d for d in ds if d >= START]


def _finra_candidates(date):
    """Return [(symbol, dtc, adv), ...] — high-days-to-cover US names above the share-volume floor."""
    body = {"limit": CAND_LIMIT,
            "compareFilters": [
                {"fieldName": "settlementDate", "compareType": "EQUAL", "fieldValue": date},
                {"fieldName": "averageDailyVolumeQuantity", "compareType": "GTE", "fieldValue": MIN_ADV}],
            "sortFields": ["-daysToCoverQuantity"]}
    req = urllib.request.Request(
        "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest",
        data=json.dumps(body).encode(), headers=_H, method="POST")
    for attempt in range(3):
        try:
            d = json.loads(urllib.request.urlopen(req, timeout=30, context=_CTX).read())
            d = d if isinstance(d, list) else d.get("data", [])
            out, seen = [], set()
            for x in d:
                s = x.get("symbolCode", "").strip()
                if x.get("marketClassCode") in _OK_EXCH and s and s not in seen:
                    try:
                        out.append((s, float(x["daysToCoverQuantity"]), float(x["averageDailyVolumeQuantity"])))
                        seen.add(s)
                    except Exception:
                        pass
            return out
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    return []


def main():
    import market_data as md
    dates = _finra_dates()
    print(f"FINRA reports since {START}: {len(dates)}")
    cand = {}
    for i, d in enumerate(dates):
        cand[d] = _finra_candidates(d)
        if i % 25 == 0:
            print(f"  {d}: {len(cand[d])} candidates ({i+1}/{len(dates)})")
    union = sorted({s for c in cand.values() for s, _, _ in c})
    print(f"Unique candidate names: {len(union)}")

    px = md.price_histories(union, start=(pd.Timestamp(dates[0]) - pd.Timedelta(days=10)).date().isoformat())
    P = pd.DataFrame({s: px[s] for s in union if s in px and not px[s].empty}).sort_index()
    P = P[~P.index.duplicated(keep="last")]
    R = P.pct_change(fill_method=None)

    # Finalize each report's basket: liquidity floor ($-vol), ranked by winsorized DTC.
    baskets = {}
    for d in dates:
        ts = pd.Timestamp(d)
        ranked = sorted(cand[d], key=lambda t: -min(t[1], DTC_CAP))
        picked = []
        for s, dtc, adv in ranked:
            if s not in P.columns:
                continue
            p = P[s].asof(ts)
            if pd.isna(p) or p * adv < DOLLARVOL_MIN:
                continue
            picked.append(s)
            if len(picked) >= TOP_N:
                break
        baskets[d] = picked

    settle = [pd.Timestamp(d) for d in dates]
    days = R.index[R.index >= settle[0]]
    idx_dates, idx_vals, cover = [], [], []
    I, bi = 100.0, 0
    for j, day in enumerate(days):
        while bi + 1 < len(settle) and settle[bi + 1] <= day:
            bi += 1
        active = [s for s in baskets[dates[bi]] if s in R.columns]
        if j > 0:
            rets = [R.at[day, s] for s in active if pd.notna(R.at[day, s])]
            if rets:
                I *= (1.0 + sum(rets) / len(rets))
        idx_dates.append(day); idx_vals.append(round(I, 3)); cover.append(len(active))

    out = {
        "asof": dates[-1],
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "rank_by": "days_to_cover", "top_n": TOP_N, "min_adv": MIN_ADV,
        "dollarvol_min": DOLLARVOL_MIN, "dtc_cap": DTC_CAP,
        "n_reports": len(dates), "latest_basket": baskets[dates[-1]],
        "dates": [d.date().isoformat() for d in idx_dates], "level": idx_vals, "coverage": cover,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out), encoding="utf-8")
    avg_sz = round(sum(len(b) for b in baskets.values()) / len(baskets), 1)
    print(f"JAWS Crowded Short Index: {len(idx_dates)} days, latest {idx_vals[-1]} (=100 at "
          f"{idx_dates[0].date()}), avg basket {avg_sz} names, {len(union)} candidates -> {OUT}")


if __name__ == "__main__":
    main()
