#!/usr/bin/env python
"""Daily index heatmap dataset: per-constituent sector, market cap, and returns for all
standard periods (1D/WTD/MTD/QTD/YTD/1Y). Free data only — Wikipedia (constituents + GICS
sector) and yfinance (prices + market cap). Writes data/heatmap_<index>.json, read by the
app's treemap. Intended to run once a day after the US close (GitHub Actions)."""
import datetime
import json
import pathlib
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
import pandas as pd            # noqa: E402
import yfinance as yf         # noqa: E402

OUTDIR = _ROOT / "data"

# Wikipedia pages with a constituents table carrying ticker + sector.
INDEXES = {
    "sp500": {
        "label": "S&P 500",
        "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "sym_col": "Symbol", "name_col": "Security", "sector_col": "GICS Sector", "table": 0,
    },
    # Wikipedia's Nasdaq-100/Dow component tables broke (JS-rendered); slickcharts is a reliable
    # free source with a clean Symbol column (no GICS sector, so the treemap groups them as '—').
    "nasdaq100": {"label": "Nasdaq 100", "source": "slick",
                  "url": "https://www.slickcharts.com/nasdaq100"},
    "dow": {"label": "Dow 30", "source": "slick",
            "url": "https://www.slickcharts.com/dowjones"},
}


def _slick(cfg):
    import urllib.request, io
    req = urllib.request.Request(cfg["url"], headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    for df in pd.read_html(io.StringIO(html)):
        cols = {str(c): c for c in df.columns}
        if "Symbol" in cols:
            out = []
            for _, r in df.iterrows():
                sym = str(r[cols["Symbol"]]).strip().replace(".", "-")
                nm = str(r.get(cols.get("Company", ""), sym)).strip()
                if sym and sym.lower() != "nan" and len(sym) <= 6:
                    out.append({"t": sym, "name": nm, "sector": "—"})
            if out:
                return out
    raise RuntimeError("slickcharts: no Symbol table")


def _wiki(cfg):
    import urllib.request, io
    if cfg.get("source") == "slick":
        return _slick(cfg)
    req = urllib.request.Request(cfg["url"], headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    tables = pd.read_html(io.StringIO(html))
    # pick the table that has the needed columns
    if cfg["table"] is not None:
        cand = [tables[cfg["table"]]]
    else:
        cand = tables
    for df in cand:
        cols = {str(c): c for c in df.columns}
        if cfg["sym_col"] in cols and cfg["sector_col"] in cols:
            out = []
            for _, r in df.iterrows():
                sym = str(r[cfg["sym_col"]]).strip().replace(".", "-")   # BRK.B -> BRK-B
                sec = str(r[cfg["sector_col"]]).strip()
                nm = str(r.get(cfg["name_col"], sym)).strip()
                if sym and sym.lower() != "nan":
                    out.append({"t": sym, "name": nm, "sector": sec})
            return out
    raise RuntimeError(f"No constituents table with {cfg['sym_col']}/{cfg['sector_col']}")


def _pct(a, b):
    return round((b / a - 1) * 100, 2) if (a and b and a != 0) else None


def _period_returns(s):
    s = s.dropna().sort_index()
    if len(s) < 2:
        return {}
    cur = float(s.iloc[-1]); d = s.index[-1]
    before = lambda dt: (float(s[s.index < dt].iloc[-1]) if len(s[s.index < dt]) else None)
    onafter = lambda dt: (float(s[s.index >= dt].iloc[0]) if len(s[s.index >= dt]) else None)
    wtd = d - pd.Timedelta(days=int(d.weekday()))
    mtd = d.replace(day=1)
    qtd = d.replace(month=((d.month - 1) // 3) * 3 + 1, day=1)
    ytd = d.replace(month=1, day=1)
    return {
        "1D": _pct(float(s.iloc[-2]), cur),
        "WTD": _pct(before(wtd), cur), "MTD": _pct(before(mtd), cur),
        "QTD": _pct(before(qtd), cur), "YTD": _pct(before(ytd), cur),
        "1Y": _pct(onafter(d - pd.DateOffset(years=1)), cur),
    }


def build(key, cfg):
    cons = _wiki(cfg)
    syms = [c["t"] for c in cons]
    start = (datetime.date.today() - datetime.timedelta(days=900)).isoformat()  # ~2.5y so the
    # realized-correlation series has history (heatmap period returns only need the tail).
    # Batched price history for all constituents.
    hist = yf.download(syms, start=start, interval="1d", auto_adjust=True,
                       group_by="ticker", threads=True, progress=False)
    rows = []
    _closes = {}
    for c in cons:
        t = c["t"]
        try:
            if len(syms) == 1:
                s = hist["Close"]
            else:
                s = hist[t]["Close"] if t in hist.columns.get_level_values(0) else None
            if s is None:
                continue
            s = pd.to_numeric(s, errors="coerce").dropna()
            if s.empty:
                continue
            _closes[t] = s                                # keep for breadth stats
            rets = _period_returns(s)
            if not rets:
                continue
            # market cap (size) via fast_info; retry a couple times
            mc = None
            for _ in range(2):
                try:
                    mc = yf.Ticker(t).fast_info["marketCap"]
                    if mc:
                        break
                except Exception:
                    mc = None
                time.sleep(0.3)
            rows.append({"t": t, "name": c["name"], "sector": c["sector"],
                         "mktcap": (round(mc) if mc else None), "r": rets})
        except Exception:
            continue
    rows = [r for r in rows if r.get("mktcap")]       # need a size for the treemap
    asof = datetime.date.today().isoformat()
    out = {"index": cfg["label"], "asof": asof, "count": len(rows), "names": rows}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / f"heatmap_{key}.json").write_text(json.dumps(out), encoding="utf-8")
    print(f"{cfg['label']}: {len(rows)} names -> data/heatmap_{key}.json")
    if key == "sp500":
        _append_breadth(_closes, asof)
    _append_correlation(key, _closes, {r["t"]: r["mktcap"] for r in rows if r.get("mktcap")}, asof)


def _append_correlation(key, closes, weights, asof):
    """Realized average correlation of an index's constituents over time, via the variance-
    decomposition identity  rho = (var_p - sum wi^2 var_i) / ((sum wi*sigma_i)^2 - sum wi^2 var_i).
    Computes TWO weightings at 21d & 63d:
      cw_* = cap-weighted  — the apples-to-apples match for CBOE implied correlation (COR1M/3M)
      ew_* = equal-weight  — ~average pairwise, needs NO weights (robust for deep history)
    MERGES onto any existing data/realized_corr_<key>.csv so a long one-time seed is preserved
    while the nightly run only refreshes the recent tail."""
    import numpy as np
    syms = [s for s in closes if s in weights and weights[s]]
    if len(syms) < 20:                 # enough for a meaningful average (Dow has 30)
        return
    px = pd.DataFrame({s: closes[s] for s in syms}).sort_index()
    R = px.pct_change()
    mp_names = max(1, int(len(syms) * 0.8))
    cw = np.array([weights[s] for s in syms], float); cw = cw / cw.sum()
    ew = np.full(len(syms), 1.0 / len(syms))
    out = {}
    for wname, w in [("cw", cw), ("ew", ew)]:
        rp = R[syms].mul(w, axis=1).sum(axis=1, min_count=mp_names)
        for W, tag in [(21, "21d"), (63, "63d")]:
            mp = int(W * 0.8)
            var_p = rp.rolling(W, min_periods=mp).var()
            var_i = R[syms].rolling(W, min_periods=mp).var()
            std_i = R[syms].rolling(W, min_periods=mp).std()
            sw2v = var_i.mul(w ** 2, axis=1).sum(axis=1)
            swsig = std_i.mul(w, axis=1).sum(axis=1)
            denom = swsig ** 2 - sw2v
            out[f"{wname}_{tag}"] = ((var_p - sw2v) / denom.where(denom.abs() > 1e-12)).clip(-1, 1)
    new = pd.DataFrame(out).dropna(how="all").round(4)
    if new.empty:
        return
    new.index = pd.to_datetime(new.index)
    # Merge with any existing (seeded) history — new rows win on overlapping dates.
    path = OUTDIR / f"realized_corr_{key}.csv"
    if path.exists():
        try:
            old = pd.read_csv(path); old.index = pd.to_datetime(old["date"]); old = old.drop(columns=["date"])
            new = pd.concat([old, new])
            new = new[~new.index.duplicated(keep="last")].sort_index()
        except Exception:
            pass
    new = new.tail(6000)
    # Cap-weighted uses TODAY's weights, so only trust it where current weights are a fair proxy;
    # beyond ~5y the mega-cap weight drift distorts it. Equal-weight (weight-free) keeps full history.
    cw_cut = pd.Timestamp.today().normalize() - pd.Timedelta(days=int(5 * 365.25))
    for col in ("cw_21d", "cw_63d"):
        if col in new.columns:
            new.loc[new.index < cw_cut, col] = np.nan
    df = new.reset_index(); df = df.rename(columns={df.columns[0]: "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    path.write_text(df.to_csv(index=False), encoding="utf-8")
    last = df.iloc[-1]
    print(f"realized corr [{key}]: {len(df)} days ({df['date'].iloc[0]}..{df['date'].iloc[-1]}), "
          f"latest cw63={last.get('cw_63d')} ew63={last.get('ew_63d')}")


def _append_breadth(closes, asof):
    """Compute a full market-breadth *history* (not just today) from the constituent price
    window — % above 50/200-DMA, 52-week new highs/lows, advancers/decliners — vectorized,
    and write the last ~250 trading days to data/breadth_sp500.csv. Recomputed each run so
    the chart has real history immediately and rolls forward over time."""
    if len(closes) < 50:
        return
    px = pd.DataFrame(closes).sort_index()            # columns = tickers, index = dates
    valid = px.notna()
    ma50 = px.rolling(50, min_periods=40).mean()
    ma200 = px.rolling(200, min_periods=150).mean()
    hi252 = px.rolling(252, min_periods=120).max()
    lo252 = px.rolling(252, min_periods=120).min()
    prev = px.shift(1)
    a50 = (px > ma50).sum(axis=1)
    a200 = (px > ma200).sum(axis=1)
    n50 = (valid & ma50.notna()).sum(axis=1)
    n200 = (valid & ma200.notna()).sum(axis=1)
    newhi = (px >= hi252 * 0.999).sum(axis=1)
    newlo = (px <= lo252 * 1.001).sum(axis=1)
    adv = (px > prev).sum(axis=1)
    dec = (px < prev).sum(axis=1)
    df = pd.DataFrame({
        "date": px.index,
        "n": valid.sum(axis=1).values,
        "pct_above_50dma": (a50 / n50.replace(0, 1) * 100).round(1).values,
        "pct_above_200dma": (a200 / n200.replace(0, 1) * 100).round(1).values,
        "new_highs_52w": newhi.values, "new_lows_52w": newlo.values,
        "net_new_highs": (newhi - newlo).values, "advancers": adv.values, "decliners": dec.values,
    })
    df = df[n200.values >= 50].tail(260)              # only once 200-DMA breadth is meaningful
    if df.empty:
        return
    df["date"] = pd.to_datetime(df["date"]).dt.date.astype(str)
    (OUTDIR / "breadth_sp500.csv").write_text(df.to_csv(index=False), encoding="utf-8")
    last = df.iloc[-1]
    print(f"breadth: {len(df)} days, latest {last['pct_above_50dma']}% >50dma, "
          f"{last['pct_above_200dma']}% >200dma, net new highs {last['net_new_highs']}")


def main():
    only = sys.argv[1:] or list(INDEXES)
    for key in only:
        try:
            build(key, INDEXES[key])
        except Exception as e:
            print(f"{key}: FAILED {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
