"""
Central-bank policy rates from the BIS (Bank for International Settlements).

Single authoritative, free, redistributable source for every major central bank's
policy rate — daily history via the BIS Stats SDMX API (dataset WS_CBPOL). Covers
Fed, ECB, BoE, BoJ, BoC, RBA, SNB (and more) with one consistent methodology, so we
don't hardcode stale numbers or scrape seven different sites.

BIS terms: BIS statistics are freely available for use with attribution.
"""
import urllib.request
import ssl
import csv
import io
import math
import datetime

try:
    import certifi
    _CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _CTX = ssl.create_default_context()

_UA = {"User-Agent": "Mozilla/5.0 (JAWS Market Monitor)"}
_TIMEOUT = 30

# JAWS tag -> BIS REF_AREA code
AREAS = {"Fed": "US", "ECB": "XM", "BoE": "GB", "BoJ": "JP",
         "BoC": "CA", "RBA": "AU", "SNB": "CH"}


def fetch_policy_rate_history(area_code, years=6):
    """[(date, rate_pct), ...] ascending for a BIS REF_AREA, last ~`years` years. [] on failure."""
    start = (datetime.date.today() - datetime.timedelta(days=int(years * 366))).isoformat()
    url = (f"https://stats.bis.org/api/v2/data/dataflow/BIS/WS_CBPOL/1.0/D.{area_code}"
           f"?startPeriod={start}&format=csv")
    try:
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=_TIMEOUT, context=_CTX) as r:
            txt = r.read().decode("utf-8", "replace")
    except Exception:
        return []
    out = []
    for row in csv.DictReader(io.StringIO(txt)):
        d = row.get("TIME_PERIOD"); v = row.get("OBS_VALUE")
        if not d or v in (None, "", "."):
            continue
        try:
            fv = float(v)
            if not math.isfinite(fv):        # BIS emits "NaN" strings for gap days
                continue
            out.append((datetime.date.fromisoformat(d), fv))
        except Exception:
            continue
    out.sort()
    return out
