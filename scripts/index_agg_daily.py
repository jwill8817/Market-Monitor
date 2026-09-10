#!/usr/bin/env python
"""Daily constituent-built index valuation aggregates (forward P/E + P/B).

Computes cap-weighted aggregate forward P/E and P/B for a set of indices from their
constituents (LSEG), and appends one row per index per day to data/index_aggregates.csv.
Intended to run once a day pre-market (GitHub Actions cron). Credentials come from env
(LSEG_APP_KEY / LSEG_USER / LSEG_PASSWORD) or a local .env — never committed.

The output holds only aggregate index-level numbers (not raw constituent data).
"""
import csv
import datetime
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
import pandas  # noqa: E402,F401  (ensure it's loaded before lseg_data's lazy import)
import lseg_data as L  # noqa: E402

# Indices to aggregate. (MSCI World omitted — constituents not entitled.)
INDEXES = {"TOPIX": ".TOPX", "S&P 500": ".SPX"}
OUT = _ROOT / "data" / "index_aggregates.csv"
FIELDS = ["date", "index", "fwd_pe", "pb", "n", "pe_cov", "pb_cov"]


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if OUT.exists():
        with open(OUT, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    have = {(r["date"], r["index"]) for r in rows}
    today = datetime.date.today().isoformat()

    added = 0
    for name, ric in INDEXES.items():
        if (today, name) in have:
            print(f"{name}: already have {today}, skipping")
            continue
        r = L.fetch_index_forward_valuation(ric)
        if r.get("error"):
            print(f"{name}: ERROR {r['error']}")
            continue
        if r.get("fwd_pe") is None and r.get("pb") is None:
            print(f"{name}: no data returned, skipping")
            continue
        rows.append({"date": today, "index": name, "fwd_pe": r["fwd_pe"], "pb": r["pb"],
                     "n": r["n"], "pe_cov": r["pe_cov"], "pb_cov": r["pb_cov"]})
        added += 1
        print(f"{name}: fwdPE={r['fwd_pe']} PB={r['pb']} n={r['n']} peCov={r['pe_cov']}%")

    rows.sort(key=lambda x: (x["date"], x["index"]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {added} new row(s); {len(rows)} total -> {OUT}")


if __name__ == "__main__":
    main()
