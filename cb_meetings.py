"""
Scheduled central-bank policy-decision dates (announcement / decision day).

Hand-curated from each central bank's OFFICIAL published calendar, verified Aug 2026.
Two-day meetings use the second (decision) day. Refresh when a bank posts a new year's
schedule — this is the small periodic maintenance the Global CB Monitor needs so the
"Next decision" column stays authoritative even before a prediction market lists a contract.

Only dates confirmed from official / unambiguous sources are included. SNB's exact
Sep/Dec 2026 days were not verifiable at build time and are intentionally omitted (that
bank falls back to the prediction-market contract date, or '—').

Sources: ecb.europa.eu, bankofengland.co.uk, boj.or.jp, bankofcanada.ca, rba.gov.au.
"""
import datetime

# JAWS tag -> list of ISO decision dates (ascending)
MEETINGS = {
    "ECB": ["2026-09-10", "2026-10-29", "2026-12-17"],
    "BoE": ["2026-09-17", "2026-11-05", "2026-12-17"],
    "BoJ": ["2026-09-18", "2026-10-30", "2026-12-18"],
    "BoC": ["2026-09-02", "2026-10-28", "2026-12-09"],
    "RBA": ["2026-08-11", "2026-09-29", "2026-11-03", "2026-12-08"],
}


def next_meeting(tag, today=None):
    """Next scheduled decision date on/after `today` for a CB tag, or None."""
    today = today or datetime.date.today()
    out = []
    for s in MEETINGS.get(tag, []):
        try:
            out.append(datetime.date.fromisoformat(s))
        except Exception:
            continue
    fut = [d for d in out if d >= today]
    return min(fut) if fut else None
