"""
Scheduled central-bank policy-decision dates (announcement / decision day).

Hand-curated from each central bank's OFFICIAL published calendar, verified Oct 2026.
Two-day meetings use the second (decision) day. Refresh when a bank posts a new year's
schedule — this is the small periodic maintenance the Global CB Monitor needs so the
"Next decision" column stays authoritative even before a prediction market lists a contract.

Only dates confirmed from official / unambiguous sources are included.

Sources: ecb.europa.eu, bankofengland.co.uk, boj.or.jp, bankofcanada.ca, rba.gov.au, snb.ch.
"""
import datetime

# JAWS tag -> list of ISO decision dates (ascending)
MEETINGS = {
    "ECB": [
        "2026-10-29", "2026-12-17",
        "2027-02-04", "2027-03-18", "2027-04-29", "2027-06-10",
        "2027-07-22", "2027-09-09", "2027-10-28", "2027-12-16",
    ],
    "BoE": [
        "2026-11-05", "2026-12-17",
        "2027-02-04", "2027-03-18", "2027-04-29", "2027-06-17",
        "2027-07-29", "2027-09-16", "2027-11-04", "2027-12-16",
    ],
    "BoJ": [
        "2026-10-30", "2026-12-18",
        "2027-01-22", "2027-03-18", "2027-04-28", "2027-06-11",
        "2027-07-22", "2027-09-22", "2027-10-29", "2027-12-17",
    ],
    "BoC": [
        "2026-10-28", "2026-12-09",
        "2027-01-27", "2027-03-03", "2027-04-28", "2027-06-02",
        "2027-07-21", "2027-09-08", "2027-10-27", "2027-12-08",
    ],
    "RBA": [
        "2026-11-03", "2026-12-08",
        "2027-02-09", "2027-03-23", "2027-05-04", "2027-06-22",
        "2027-08-10", "2027-09-28", "2027-11-02", "2027-12-14",
    ],
    "SNB": [
        "2026-12-10",
        "2027-03-18", "2027-06-24", "2027-09-23", "2027-12-16",
    ],
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
