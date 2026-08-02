"""
Primary-market issuance & deal-activity data (committed CSVs, refreshed by a scheduled agent).

The deployed app only READS these CSVs — the fragile part (finding/parsing SIFMA's versioned
Excel files and IMAA's M&A tables) runs in a scheduled cloud agent that writes the CSVs and
commits them, so the dashboard never breaks on a source URL change.

Files (repo-root data/):
  issuance_monthly.csv : month, asset_class, category, value_bn      (SIFMA, monthly $bn)
  ma_activity.csv      : period, freq, region, sector, value_bn, deal_count  (IMAA, annual/quarterly)

Sources: SIFMA statistics (sifma.org) for issuance; IMAA (imaa-institute.org) for M&A.
"""
import os
import pandas as pd

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _read(name):
    p = os.path.join(_DIR, name)
    if not os.path.exists(p):
        return pd.DataFrame()
    try:
        return pd.read_csv(p)
    except Exception:
        return pd.DataFrame()


def load_issuance():
    """Tidy monthly issuance: columns month(datetime), asset_class, category, value_bn."""
    df = _read("issuance_monthly.csv")
    if df.empty or "month" not in df.columns:
        return pd.DataFrame(columns=["month", "asset_class", "category", "value_bn"])
    df["month"] = pd.to_datetime(df["month"], errors="coerce")
    df["value_bn"] = pd.to_numeric(df["value_bn"], errors="coerce")
    df = df.dropna(subset=["month", "value_bn"])
    return df.sort_values("month")


def load_ma():
    """M&A activity: period, freq (A/Q), region, sector, value_bn, deal_count."""
    df = _read("ma_activity.csv")
    if df.empty or "period" not in df.columns:
        return pd.DataFrame(columns=["period", "freq", "region", "sector", "value_bn", "deal_count"])
    for c in ("value_bn", "deal_count"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
