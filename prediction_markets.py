"""
Prediction-market implied probabilities (free, no key).

Sources:
  • Polymarket — Gamma API (real-money crypto market; broad macro/politics/geo/crypto).
  • Kalshi     — public markets API (CFTC-regulated USD; strong on US econ prints).

Both expose public market data (question + implied probability + volume). We classify
each contract into a macro-relevant TOPIC by keyword and drop sports/entertainment,
since the raw feeds are dominated by them and carry no usable category field.
"""
import json
import urllib.request

_UA = {"User-Agent": "Mozilla/5.0 (JAWS Market Monitor)"}
_TIMEOUT = 20

TOPICS = {
    "Macro/rates": ["fed", "fomc", "rate cut", "rate hike", "interest rate", "cpi",
                    "inflation", "recession", "gdp", "payroll", "jobs report", "jobless",
                    "unemployment", "powell", "pce", "treasury", "yield", "economy",
                    "tariff", "debt ceiling", "government shutdown", "basis point",
                    "rate decision", "soft landing"],
    "Elections/policy": ["election", "president", "senate", "house of rep", "congress",
                         "governor", "primary", "nominee", "electoral", "parliament",
                         "prime minister", "supreme court", "impeach", "cabinet", "speaker",
                         "referendum", "mayor", "chancellor", "poll", "approval rating",
                         "confirm", "nomination", "shutdown"],
    "Geopolitics": ["war", "ukraine", "russia", "israel", "gaza", "hamas", "iran",
                    "china", "taiwan", "ceasefire", "sanction", "nato", "nuclear",
                    "invade", "invasion", "north korea", "venezuela", "hostage",
                    "military strike", "annex", "coup", "greenland"],
    "Crypto/markets": ["bitcoin", "btc", "ethereum", " eth ", "crypto", "solana",
                       "s&p 500", "nasdaq", "dow ", "stock market", "ipo", "all-time high",
                       "all time high", "market cap", "gold price", "oil price", "$100k",
                       "$1 million", "microstrategy", "strategic reserve"],
}
_SPORTS = ["world cup", "fifa", "nba", "nfl", " mlb", "nhl", "premier league",
           "super bowl", "champions league", " vs.", " vs ", "f1", "grand prix",
           "ufc", "tennis", "olympic", "goals scored", "runs scored", "touchdown",
           "playoff", "wins the match", "to score", "boxing", "cricket", "golf",
           "espn", "heisman", "mvp award", "oscar", "grammy", "emmy", "box office",
           "rotten tomatoes", "album", "movie"]


def _classify(text):
    t = (text or "").lower()
    if any(s in t for s in _SPORTS):
        # allow through only if it ALSO strongly matches a macro/econ term
        if not any(kw in t for kw in TOPICS["Macro/rates"] + TOPICS["Geopolitics"]):
            return None
    for topic, kws in TOPICS.items():
        if any(kw in t for kw in kws):
            return topic
    return None


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=_TIMEOUT) as r:
        return json.loads(r.read())


def fetch_polymarket(limit=500):
    """Top open Polymarket markets by 24h volume → classified macro-relevant list."""
    out = []
    try:
        url = (f"https://gamma-api.polymarket.com/markets?closed=false&active=true"
               f"&limit={limit}&order=volume24hr&ascending=false")
        data = _get(url)
        rows = data if isinstance(data, list) else data.get("data", [])
    except Exception:
        return out
    for m in rows:
        q = (m.get("question") or "").strip()
        topic = _classify(q)
        if not topic:
            continue
        try:
            outs = json.loads(m.get("outcomes") or "[]")
            prices = [float(x) for x in json.loads(m.get("outcomePrices") or "[]")]
        except Exception:
            continue
        if not prices:
            continue
        # binary Yes/No → Yes probability; else the top-priced outcome
        if outs and outs[0].lower() == "yes":
            label, prob = "Yes", prices[0]
        else:
            i = max(range(len(prices)), key=lambda j: prices[j])
            label, prob = (outs[i] if i < len(outs) else "top"), prices[i]
        vol = m.get("volume24hr") or 0.0
        out.append({
            "source": "Polymarket", "topic": topic, "question": q,
            "outcome": label, "prob": prob * 100.0,
            "vol24": float(vol or 0), "total_vol": float(m.get("volume") or 0),
            "chg1w": (float(m.get("oneWeekPriceChange") or 0) * 100.0),
            "end": (m.get("endDate") or "")[:10],
            "url": f"https://polymarket.com/event/{m.get('slug','')}",
        })
    return out


def fetch_kalshi(limit=1000):
    """Open Kalshi markets → classified macro-relevant list (prices are probabilities)."""
    out = []
    try:
        url = (f"https://api.elections.kalshi.com/trade-api/v2/markets"
               f"?limit={limit}&status=open")
        data = _get(url)
        rows = data.get("markets", [])
    except Exception:
        return out
    for m in rows:
        title = (m.get("title") or "").strip()
        sub = (m.get("yes_sub_title") or "").strip()
        full = f"{title} {sub}".strip()
        topic = _classify(full)
        if not topic:
            continue
        last = m.get("last_price_dollars")
        if last in (None, ""):
            yb = m.get("yes_bid_dollars"); ya = m.get("yes_ask_dollars")
            try: last = (float(yb) + float(ya)) / 2 if yb and ya else None
            except Exception: last = None
        if last in (None, ""):
            continue
        try: prob = float(last) * 100.0
        except Exception: continue
        vol = m.get("volume_24h_fp") or m.get("volume_fp") or 0
        et = m.get("event_ticker") or m.get("ticker") or ""
        out.append({
            "source": "Kalshi", "topic": topic,
            "question": full if sub else title, "outcome": "Yes", "prob": prob,
            "vol24": float(vol or 0), "total_vol": float(m.get("volume_fp") or 0),
            "chg1w": 0.0, "end": (m.get("close_time") or "")[:10],
            "url": f"https://kalshi.com/markets/{et.lower()}",
        })
    return out


# ── Central-bank rate-decision capture (self-populating from prediction markets) ──
# Each CB: (display name, short tag, match keywords, FRED policy-rate series or None).
# FRED series only where the feed is timely; None = show current rate as unavailable
# rather than risk a stale hardcoded number. Odds fill in automatically when a market appears.
# (display name, tag, match keywords, FRED daily rate series or None, rate label)
CB_DEFS = [
    ("Federal Reserve", "Fed", ["fed ", "fed's", "federal reserve", "fomc", "powell",
                                 "fed interest", "fed rate"], "DFEDTARU", "Fed funds upper target"),
    ("European Central Bank", "ECB", ["ecb", "european central bank", "lagarde"],
     "ECBDFR", "ECB deposit facility rate"),
    ("Bank of England", "BoE", ["bank of england", "boe ", " boe", "bailey"],
     "IUDSOIA", "SONIA (≈ Bank Rate)"),
    ("Bank of Japan", "BoJ", ["bank of japan", "boj ", " boj", "ueda"], None, None),
    ("Bank of Canada", "BoC", ["bank of canada", "boc ", " boc", "macklem"], None, None),
    ("Reserve Bank of Australia", "RBA", ["reserve bank of australia", "rba ", " rba"], None, None),
    ("Swiss National Bank", "SNB", ["swiss national bank", "snb ", " snb"], None, None),
]
_HIKE = ["increase", "hike", "raise", "raising", "higher", "up by", "above"]
_CUT = ["decrease", "cut", "cutting", "lower", "reduce", "reducing", "down by", "below"]
_HOLD = ["no change", "unchanged", "hold ", "keep rates", "keep interest", "leave rates",
         "maintain", "no cut", "no hike", "steady", "same"]
_RATEY = ["interest rate", "rate hike", "rate cut", "rate decision", "basis point", "bps",
          " rates ", "monetary policy", "rate by", "policy rate", "cut rates", "hike rates",
          "raise rates", "lower rates"]


def _rate_move_class(q):
    ql = " " + (q or "").lower() + " "
    # order matters: 'no hike/no cut' → hold, checked first
    if any(w in ql for w in _HOLD):
        return "hold"
    if any(w in ql for w in _HIKE):
        return "hike"
    if any(w in ql for w in _CUT):
        return "cut"
    return None


def fetch_cb_rate_markets():
    """Scan Polymarket + Kalshi for central-bank rate-decision contracts, grouped by bank.
    Self-populating: a bank shows aggregated hike/hold/cut odds only when contracts exist
    (today typically just the Fed); others fill in automatically as markets are listed.
    Aggregation sums the Yes-probability of each mutually-exclusive outcome by direction, so
    with a full outcome set hike+hold+cut ≈ 100%; with a lone contract it may be partial.
    Returns [{name, tag, fred, contracts:[...], hike, hold, cut, updated}]."""
    rows = fetch_polymarket() + fetch_kalshi()
    ratey = lambda q: any(w in (" " + (q or "").lower() + " ") for w in _RATEY)
    out = []
    for name, tag, kws, fred, ratelbl in CB_DEFS:
        matched = [r for r in rows
                   if any(k in (" " + r["question"].lower() + " ") for k in kws) and ratey(r["question"])]
        agg = {"hike": 0.0, "hold": 0.0, "cut": 0.0}
        seen = {"hike": False, "hold": False, "cut": False}
        clist = []
        for r in matched:
            cls = _rate_move_class(r["question"])
            clist.append({"source": r["source"], "question": r["question"], "outcome": r["outcome"],
                          "prob": r["prob"], "move": cls, "vol24": r["vol24"],
                          "end": r["end"], "url": r["url"]})
            if cls in agg:
                agg[cls] += r["prob"]; seen[cls] = True
        clist.sort(key=lambda x: -x["vol24"])
        out.append({"name": name, "tag": tag, "fred": fred, "rate_label": ratelbl, "contracts": clist,
                    "hike": round(agg["hike"], 1) if seen["hike"] else None,
                    "hold": round(agg["hold"], 1) if seen["hold"] else None,
                    "cut": round(agg["cut"], 1) if seen["cut"] else None})
    return out


def fetch_prediction_markets(sources, topics):
    """Combined, topic-filtered, de-duplicated, sorted by 24h volume desc."""
    rows = []
    if "Polymarket" in sources:
        rows += fetch_polymarket()
    if "Kalshi" in sources:
        rows += fetch_kalshi()
    tset = set(topics)
    rows = [r for r in rows if r["topic"] in tset]
    # de-dupe near-identical questions (keep the higher-volume one)
    seen = {}
    for r in sorted(rows, key=lambda x: -x["vol24"]):
        key = r["question"].lower()[:60]
        if key not in seen:
            seen[key] = r
    return sorted(seen.values(), key=lambda x: -x["vol24"])
