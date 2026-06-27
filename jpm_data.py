"""
J.P. Morgan Markets / DataQuery integration — credential-gated SCAFFOLD.

This activates ONLY when JPM API credentials are present (env or Streamlit
secrets). With no creds it stays dormant, so the free/shared deployment is
unaffected and never tries to call JPM.

To enable, add to your .env (local) or Streamlit secrets (private app):
    JPM_CLIENT_ID     = "..."
    JPM_CLIENT_SECRET = "..."
    JPM_OAUTH_URL     = "https://authe.jpmorgan.com/as/token.oauth2"   # confirm in portal
    JPM_API_BASE      = "https://api-gw.jpmorgan.com/research/dataquery-api/v2"  # confirm

How to get credentials: ask your J.P. Morgan coverage / the Markets portal for
"DataQuery API access (OAuth client credentials)". They provision a client_id /
client_secret and give you the exact OAuth + API base URLs — paste those into
JPM_OAUTH_URL / JPM_API_BASE above (the defaults here are placeholders).

Primary use here: index-level FORWARD earnings/revenue estimates and custom
basket / factor time series that are not available from free sources.
"""
import os
import time
import json
import urllib.request
import urllib.parse

def _cfg(key, default=""):
    # Prefer Streamlit secrets when running in the web app, else env.
    try:
        import streamlit as st
        if key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return os.environ.get(key, default)

def is_enabled() -> bool:
    return bool(_cfg("JPM_CLIENT_ID") and _cfg("JPM_CLIENT_SECRET"))

_TOKEN = {"value": None, "exp": 0}

def _get_token() -> str | None:
    """OAuth2 client-credentials token, cached until ~60s before expiry."""
    if not is_enabled():
        return None
    if _TOKEN["value"] and time.time() < _TOKEN["exp"] - 60:
        return _TOKEN["value"]
    oauth_url = _cfg("JPM_OAUTH_URL", "https://authe.jpmorgan.com/as/token.oauth2")
    data = urllib.parse.urlencode({
        "grant_type":    "client_credentials",
        "client_id":     _cfg("JPM_CLIENT_ID"),
        "client_secret": _cfg("JPM_CLIENT_SECRET"),
        "scope":         _cfg("JPM_SCOPE", "read"),
    }).encode()
    req = urllib.request.Request(oauth_url, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=20) as r:
        tok = json.loads(r.read())
    _TOKEN["value"] = tok.get("access_token")
    _TOKEN["exp"]   = time.time() + int(tok.get("expires_in", 1800))
    return _TOKEN["value"]

def fetch_series(expressions, start=None, end=None) -> dict | None:
    """
    Fetch one or more DataQuery time-series 'expressions'.
    Returns {expression: [(date, value), ...]} or None if not enabled/failed.

    NOTE: the exact request shape (path, params, JSON body) depends on your
    DataQuery API version — confirm from the portal docs and adjust the URL/
    params below. This is wired for the common /expressions/time-series form.
    """
    token = _get_token()
    if not token:
        return None
    base = _cfg("JPM_API_BASE",
                "https://api-gw.jpmorgan.com/research/dataquery-api/v2")
    if isinstance(expressions, str):
        expressions = [expressions]
    params = {"expressions": ",".join(expressions), "format": "JSON"}
    if start: params["start-date"] = str(start)
    if end:   params["end-date"]   = str(end)
    url = f"{base}/expressions/time-series?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except Exception:
        return None
    # Parse the standard DataQuery response shape (adjust to your version)
    out = {}
    for inst in data.get("instruments", []):
        expr = inst.get("expr") or inst.get("expression") or ""
        pts = []
        for s in inst.get("series", []) or [inst]:
            for d, v in s.get("data", []) or []:
                if v is not None:
                    pts.append((d, v))
        out[expr] = pts
    return out or None
