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
