#!/usr/bin/env python
"""Daily global sovereign-rates dataset.

Pulls government-bond yields for the major markets from free official sources and writes
data/global_rates.json (per country: tenor curve + aligned daily/monthly history), read by
the app's Global Rates tab. Each market is tagged with its data frequency and source so the
tab can be explicit about what is daily vs monthly.

Sources (all free, no key except FRED which also has a keyless fallback):
  US  Treasury  — FRED constant-maturity (DGS…)          daily, full curve
  DE  Bund      — Deutsche Bundesbank (Svensson curve)    daily, full curve
  GB  Gilt      — Bank of England (IADB par yields)       daily, 5y/10y/20y
  JP  JGB       — Japan MOF (interest_rate CSV)           daily, full curve
  FR  OAT  }    — FRED / OECD long-term rate              monthly, 10y only
  IT  BTP  }                                              (daily curves = future work)
  ES  Bonos}
"""
import datetime as dt
import json
import os
import pathlib
import re
import ssl
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "global_rates.json"
HIST_YEARS = 10                                   # trim each series to the last N years

# SSL context (certifi where available — ECB/MOF/Bundesbank need a good CA bundle).
try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _CTX = ssl.create_default_context()


def _load_dotenv():
    """Make FRED_API_KEY available locally without exporting it (no dependency)."""
    if os.environ.get("FRED_API_KEY"):
        return
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"\s*FRED_API_KEY\s*=\s*(.+)\s*$", line)
            if m:
                os.environ["FRED_API_KEY"] = m.group(1).strip().strip('"').strip("'")
                break


def _http(url, timeout=45, tries=4):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
            return urllib.request.urlopen(req, timeout=timeout, context=_CTX).read().decode("utf-8", "replace")
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise last if last else RuntimeError("no data")


def _cutoff_iso():
    return (dt.date.today() - dt.timedelta(days=int(HIST_YEARS * 366))).isoformat()


# ── FRED (keyless fredgraph first; API key as fallback) ───────────────────────
def _fred(series_id):
    """Return {date_str: value} for a FRED series. Tries the keyless CSV endpoint first
    (works on CI), then the keyed API."""
    cutoff = _cutoff_iso()
    # 1) keyless CSV (fast-fail so a blocked network drops through to the keyed API quickly;
    #    on CI this succeeds on the first try)
    try:
        csv = _http(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}", timeout=12, tries=1)
        out = {}
        for line in csv.splitlines()[1:]:
            parts = line.split(",")
            if len(parts) >= 2 and parts[1] not in ("", "."):
                d = parts[0][:10]
                if d >= cutoff:
                    try:
                        out[d] = float(parts[1])
                    except ValueError:
                        pass
        if out:
            return out
    except Exception:
        pass
    # 2) keyed API
    key = os.environ.get("FRED_API_KEY", "")
    if key:
        try:
            import urllib.parse
            u = "https://api.stlouisfed.org/fred/series/observations?" + urllib.parse.urlencode(
                {"series_id": series_id, "api_key": key, "file_type": "json",
                 "observation_start": cutoff})
            js = json.loads(_http(u))
            out = {}
            for o in js.get("observations", []):
                if o.get("value") not in ("", "."):
                    try:
                        out[o["date"]] = float(o["value"])
                    except ValueError:
                        pass
            return out
        except Exception:
            pass
    return {}


# ── Deutsche Bundesbank (German Bund term structure, Svensson), daily ─────────
_BBK_TENORS = {"1Y": "R01XX", "2Y": "R02XX", "3Y": "R03XX", "5Y": "R05XX",
               "7Y": "R07XX", "10Y": "R10XX", "15Y": "R15XX", "20Y": "R20XX", "30Y": "R30XX"}


def _bundesbank(tenor_code):
    sid = f"D.I.ZST.ZI.EUR.S1311.B.A604.{tenor_code}.R.A.A._Z._Z.A"
    csv = _http(f"https://api.statistiken.bundesbank.de/rest/data/BBSIS/{sid}?format=csv&lang=en")
    cutoff = _cutoff_iso()
    out = {}
    for line in csv.splitlines():
        m = re.match(r"^(\d{4}-\d{2}-\d{2}),\s*([-\d.]+)", line)
        if m and m.group(1) >= cutoff:
            try:
                out[m.group(1)] = float(m.group(2))
            except ValueError:
                pass
    return out


# ── Bank of England (gilt par yields), daily ─────────────────────────────────
_BOE_TENORS = {"5Y": "IUDSNPY", "10Y": "IUDMNPY", "20Y": "IUDLNPY"}


def _boe(code):
    frm = (dt.date.today() - dt.timedelta(days=int(HIST_YEARS * 366))).strftime("%d/%b/%Y")
    url = ("https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp?csv.x=yes"
           f"&Datefrom={frm}&Dateto=now&SeriesCodes={code}&CSVF=TN&UsingCodes=Y")
    csv = _http(url)
    out = {}
    for line in csv.splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            try:
                d = dt.datetime.strptime(parts[0].strip(), "%d %b %Y").date().isoformat()
                out[d] = float(parts[1])
            except (ValueError, IndexError):
                pass
    return out


# ── Japan MOF (JGB interest rates), daily full curve ─────────────────────────
_JP_KEEP = ["1Y", "2Y", "5Y", "10Y", "20Y", "30Y", "40Y"]


def _mof():
    """Return {tenor: {date: yield}} for JGBs. Uses the full-history file; falls back to
    the current-year file."""
    csv = None
    for u in ("https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/historical/jgbcme_all.csv",
              "https://www.mof.go.jp/english/policy/jgbs/reference/interest_rate/jgbcme.csv"):
        try:
            csv = _http(u)
            if csv and "Date" in csv:
                break
        except Exception:
            csv = None
    if not csv:
        return {}
    lines = [l for l in csv.splitlines() if l.strip()]
    # find the header row that starts with "Date"
    hi = next((i for i, l in enumerate(lines) if l.split(",")[0].strip().lower() == "date"), None)
    if hi is None:
        return {}
    cols = [c.strip() for c in lines[hi].split(",")]
    cutoff = _cutoff_iso()
    out = {t: {} for t in _JP_KEEP}
    for line in lines[hi + 1:]:
        parts = line.split(",")
        if not parts or not re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", parts[0].strip()):
            continue
        y, m, d = parts[0].strip().split("/")
        iso = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
        if iso < cutoff:
            continue
        for t in _JP_KEEP:
            if t in cols:
                v = parts[cols.index(t)].strip()
                if v not in ("", "-"):
                    try:
                        out[t][iso] = float(v)
                    except ValueError:
                        pass
    return {t: s for t, s in out.items() if s}


# ── Assemble one country record (aligned arrays) ─────────────────────────────
def _pack(code, label, bond, freq, source, note, tenor_series):
    """tenor_series: {tenor: {date: value}} → aligned {dates, yields{tenor:[...]}} record."""
    tenor_series = {t: s for t, s in tenor_series.items() if s}
    if not tenor_series:
        return None
    dates = sorted(set().union(*[set(s) for s in tenor_series.values()]))
    yields = {}
    for t, s in tenor_series.items():
        yields[t] = [round(s[d], 3) if d in s else None for d in dates]
    # latest non-null per tenor (for the snapshot curve)
    latest = {}
    for t, arr in yields.items():
        for i in range(len(arr) - 1, -1, -1):
            if arr[i] is not None:
                latest[t] = {"v": arr[i], "d": dates[i]}
                break
    return {"code": code, "label": label, "bond": bond, "freq": freq, "source": source,
            "note": note, "tenors": list(tenor_series.keys()), "dates": dates,
            "yields": yields, "latest": latest}


def main():
    _load_dotenv()
    countries = []

    # US — FRED daily constant maturity
    us_map = {"1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO", "1Y": "DGS1", "2Y": "DGS2",
              "3Y": "DGS3", "5Y": "DGS5", "7Y": "DGS7", "10Y": "DGS10", "20Y": "DGS20", "30Y": "DGS30"}
    us = {t: _fred(sid) for t, sid in us_map.items()}
    r = _pack("US", "United States", "Treasury", "daily", "FRED (DGS constant maturity)",
              "Daily constant-maturity Treasury yields.", us)
    if r: countries.append(r); print(f"US  tenors={len(r['tenors'])} obs={len(r['dates'])}")

    # DE — Bundesbank daily Svensson curve
    de = {}
    for t, code in _BBK_TENORS.items():
        try:
            de[t] = _bundesbank(code)
        except Exception as e:
            print(f"  DE {t}: {e}")
    r = _pack("DE", "Germany", "Bund", "daily", "Deutsche Bundesbank (Svensson curve)",
              "Daily fitted Bund yields (listed Federal securities).", de)
    if r: countries.append(r); print(f"DE  tenors={len(r['tenors'])} obs={len(r['dates'])}")

    # GB — Bank of England daily gilt par yields
    gb = {}
    for t, code in _BOE_TENORS.items():
        try:
            gb[t] = _boe(code)
        except Exception as e:
            print(f"  GB {t}: {e}")
    r = _pack("GB", "United Kingdom", "Gilt", "daily", "Bank of England (IADB par yields)",
              "Daily gilt par yields (5y/10y/20y benchmark points only).", gb)
    if r: countries.append(r); print(f"GB  tenors={len(r['tenors'])} obs={len(r['dates'])}")

    # JP — Japan MOF daily full curve
    try:
        jp = _mof()
    except Exception as e:
        jp = {}; print(f"  JP: {e}")
    r = _pack("JP", "Japan", "JGB", "daily", "Japan Ministry of Finance",
              "Daily JGB yields across the curve.", jp)
    if r: countries.append(r); print(f"JP  tenors={len(r['tenors'])} obs={len(r['dates'])}")

    # FR / IT / ES — FRED OECD long-term (monthly, 10y only)
    oecd = {"FR": ("France", "OAT", "IRLTLT01FRM156N"),
            "IT": ("Italy", "BTP", "IRLTLT01ITM156N"),
            "ES": ("Spain", "Bonos", "IRLTLT01ESM156N")}
    for code, (label, bond, sid) in oecd.items():
        s = _fred(sid)
        r = _pack(code, label, bond, "monthly", "FRED / OECD long-term rate",
                  "Monthly 10y benchmark only — daily multi-tenor curve not freely available.",
                  {"10Y": s})
        if r: countries.append(r); print(f"{code}  tenors={len(r['tenors'])} obs={len(r['dates'])}")

    asof = max((c["dates"][-1] for c in countries if c["dates"]), default=None)
    out = {"asof": asof, "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "countries": countries}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out), encoding="utf-8")
    print(f"Wrote {len(countries)} countries (asof {asof}) -> {OUT}  [{OUT.stat().st_size//1024} KB]")


if __name__ == "__main__":
    main()
