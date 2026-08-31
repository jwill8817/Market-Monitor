"""
LSEG (Refinitiv) cloud data — PRIVATE / gated use only.

Credentials come from Streamlit secrets or the local .env (LSEG_APP_KEY / LSEG_USER /
LSEG_PASSWORD). This module is used ONLY behind the password-gated LSEG tab, never in the
shared free-data app — LSEG data is licensed and not redistributable.
"""
import os
import re
import threading
import datetime

_session = None
_lock = threading.Lock()


def _load_env(path=".env"):
    d = {}
    try:
        for line in open(path, encoding="utf-8"):
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, v = s.split("=", 1)
                d[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return d


def _creds():
    c = {}
    try:
        import streamlit as st
        for k in ("LSEG_APP_KEY", "LSEG_USER", "LSEG_PASSWORD"):
            try:
                if k in st.secrets:
                    c[k] = str(st.secrets[k])
            except Exception:
                pass
    except Exception:
        pass
    env = None
    for k in ("LSEG_APP_KEY", "LSEG_USER", "LSEG_PASSWORD"):
        if not c.get(k):
            c[k] = os.environ.get(k)
        if not c.get(k):
            if env is None:
                env = _load_env()
            c[k] = env.get(k)
    return c


def available():
    """True if credentials are present (doesn't open a session)."""
    c = _creds()
    return all(c.get(k) for k in ("LSEG_APP_KEY", "LSEG_USER", "LSEG_PASSWORD"))


def tab_password():
    """The personal password that gates the private LSEG tab (secrets or .env), or None."""
    try:
        import streamlit as st
        try:
            if "LSEG_TAB_PASSWORD" in st.secrets:
                return str(st.secrets["LSEG_TAB_PASSWORD"])
        except Exception:
            pass
    except Exception:
        pass
    return os.environ.get("LSEG_TAB_PASSWORD") or _load_env().get("LSEG_TAB_PASSWORD")


def open_session():
    """Open (once) and reuse a platform (cloud) session.

    Opens the session object DIRECTLY (s.open()) and verifies it reached the Opened
    state — the ld.open_session() default-session handoff is flaky on headless servers
    (Streamlit Cloud), where it can silently leave the session closed. A session that
    fails to open is never cached, so the next call retries cleanly.
    """
    global _session
    with _lock:
        if _session is not None:
            return _session
        import lseg.data as ld
        from lseg.data.session import platform
        c = _creds()
        missing = [k for k in ("LSEG_APP_KEY", "LSEG_USER", "LSEG_PASSWORD") if not c.get(k)]
        if missing:
            raise RuntimeError("LSEG credentials missing: " + ", ".join(missing))
        # signon_control=True sends takeExclusiveSignOnControl=true to the RDP token
        # endpoint. Without it the login is rejected (HTTP 400) whenever another session
        # (e.g. a local Refinitiv Workspace) already holds the sign-on — which is why the
        # cloud login failed while a desktop-shared session masked it locally.
        s = platform.Definition(
            app_key=c["LSEG_APP_KEY"],
            grant=ld.session.platform.GrantPassword(username=c["LSEG_USER"], password=c["LSEG_PASSWORD"]),
            signon_control=True,
        ).get_session()
        try:
            s.open()
        except Exception as ex:
            raise RuntimeError(
                f"LSEG session failed to open ({type(ex).__name__}: {ex}). "
                "Check LSEG_PASSWORD / LSEG_USER / LSEG_APP_KEY in Streamlit secrets.")
        state = str(getattr(getattr(s, "open_state", None), "name", getattr(s, "open_state", "")))
        if "Open" not in state:
            raise RuntimeError(
                f"LSEG session did not reach Opened state (state={state}). "
                "The LSEG credentials were rejected — re-check LSEG_PASSWORD / LSEG_USER / "
                "LSEG_APP_KEY (exact value, no quotes issues, no trailing spaces).")
        ld.session.set_default(s)
        _session = s
        return s


# ── Credit-rating → Investment-Grade / High-Yield bucket ──
_MOODY_IG = {"AAA", "AA1", "AA2", "AA3", "A1", "A2", "A3", "BAA1", "BAA2", "BAA3"}
_SP_IG = {"AAA", "AA", "A", "BBB"}
_HY_CORE = {"BB", "B", "CCC", "CC", "C", "D", "DDD"}


def rating_bucket(r):
    """Map a rating string (S&P/Fitch/Moody's/DBRS) to 'IG', 'HY', or 'NR'."""
    if not isinstance(r, str) or not r.strip():
        return "NR"
    s = r.strip()
    token = s.replace("(high)", "+").replace("(low)", "-").replace(" ", "")
    up = token.upper()
    # Moody's (mixed-case like Aa1, Baa2, Ba1) — detect a lowercase letter in the original
    has_lower = any(ch.islower() for ch in s)
    if up in _MOODY_IG:
        return "IG"
    if has_lower and re.fullmatch(r"(BA|B|CAA|CA|C)\d?", up):
        return "HY"
    # S&P / Fitch / DBRS long-term letter grades
    m = re.match(r"[A-D]{1,3}", up)
    if not m:
        return "NR"            # e.g. Fitch short-term 'F1', 'NR', etc.
    core = m.group()
    if core in _SP_IG:
        return "IG"
    if core in _HY_CORE:
        return "HY"
    return "NR"


_MONTH_CAP = 10000            # RDP search hard row cap per query


def _month_bounds(y, m):
    start = datetime.date(y, m, 1)
    end = datetime.date(y + (m == 12), (m % 12) + 1, 1) - datetime.timedelta(days=1)
    return start.isoformat(), end.isoformat()


def fetch_issuance_month(y, m, min_usd=100_000_000, currency=None):
    """One month of new bond issuance (deals >= min_usd, default $100m — keeps us under the
    API's 10k row cap and drops commercial-paper/MTN noise). Returns dict in $bn:
       {'month','Corp IG','Corp HY','Corp NR','Government','Agency','Other','count','capped'}."""
    open_session()
    import pandas as pd
    from lseg.data import discovery
    lo, hi = _month_bounds(y, m)
    filt = (f"IssueDate ge {lo} and IssueDate le {hi} and FaceIssuedUSD ge {int(min_usd)} "
            f"and IsActive eq true")
    if currency:
        filt += f" and Currency eq '{currency}'"
    df = discovery.search(view=discovery.Views.GOV_CORP_INSTRUMENTS, filter=filt,
                          select="IssueDate,FaceIssuedUSD,BondRatingLatest,DbType,Currency",
                          top=_MONTH_CAP)
    out = {"month": f"{y:04d}-{m:02d}", "Corp IG": 0.0, "Corp HY": 0.0, "Corp NR": 0.0,
           "Government": 0.0, "Agency": 0.0, "Other": 0.0, "count": 0, "capped": False}
    if df is None or df.empty:
        return out
    out["count"] = len(df)
    out["capped"] = len(df) >= _MONTH_CAP
    df = df.copy()
    df["usd"] = pd.to_numeric(df["FaceIssuedUSD"], errors="coerce").fillna(0.0) / 1e9
    for _, row in df.iterrows():
        db = str(row.get("DbType") or "").upper()
        v = float(row["usd"])
        if db == "CORP":
            out[f"Corp {rating_bucket(row.get('BondRatingLatest'))}"] += v
        elif db == "GOVT":
            out["Government"] += v
        elif db == "AGNC":
            out["Agency"] += v
        else:
            out["Other"] += v
    for k in ("Corp IG", "Corp HY", "Corp NR", "Government", "Agency", "Other"):
        out[k] = round(out[k], 2)
    return out


def fetch_issuance_history(months_back=12, min_usd=100_000_000, currency=None):
    """Monthly issuance for the last `months_back` months → list of month dicts (oldest first)."""
    today = datetime.date.today()
    y, m = today.year, today.month
    seq = []
    for _ in range(months_back):
        seq.append((y, m))
        m -= 1
        if m == 0:
            m = 12; y -= 1
    seq.reverse()
    return [fetch_issuance_month(y, m, min_usd=min_usd, currency=currency) for (y, m) in seq]
