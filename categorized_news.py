import feedparser
import requests
import os
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/everything"

NEWS_FEEDS = {
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "FT Markets": "https://www.ft.com/rss/home/uk",
    "Zero Hedge": "https://feeds.feedburner.com/zerohedge/feed",
    "WSJ Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "Seeking Alpha": "https://seekingalpha.com/feed.xml",
}

NEWSAPI_QUERIES = {
    "hedge_fund": 'hedge fund OR "short seller" OR "activist investor" OR derivatives OR "prime broker" OR leverage',
    "ipo":        'IPO OR "initial public offering" OR "going public" OR SPAC OR "direct listing"',
    "ma":         'merger OR acquisition OR takeover OR buyout OR "tender offer" OR "leveraged buyout"',
    "issuance":   '"bond issuance" OR "debt offering" OR "equity offering" OR "high yield" OR "senior notes" OR "capital raise"',
}

NEWSAPI_SOURCES = "bloomberg,the-wall-street-journal,financial-times,reuters,the-economist,cnbc,business-insider"

CATEGORY_KEYWORDS = {
    "hedge_fund": [
        "hedge fund", "short seller", "short selling", "activist investor",
        "activist campaign", "13f", "13d", "fund manager", "long/short",
        "short interest", "short squeeze", "fund flows", "alpha", "beta",
        "prime brokerage", "prime broker", "gross exposure", "net exposure",
        "position", "leverage", "leveraged", "derivatives", "derivative",
        "options", "puts", "calls", "swaps", "futures", "structured products",
        "pershing square", "ackman", "einhorn", "greenlight", "citadel",
        "bridgewater", "two sigma", "renaissance", "point72", "millennium",
        "third point", "loeb", "icahn", "elliott", "starboard", "corvex",
    ],
    "ipo": [
        "ipo", "initial public offering", "going public", "direct listing",
        "spac", "blank check", "roadshow", "listing", "debut", "float",
        "s-1", "prospectus", "underwriter", "bookrunner", "lock-up",
        "pre-ipo", "unicorn", "valuation", "first day trading",
    ],
    "ma": [
        "merger", "acquisition", "takeover", "buyout", "deal",
        "agreed to acquire", "bid for", "offer for", "tender offer",
        "leveraged buyout", "lbo", "private equity buyout", "strategic deal",
        "antitrust", "regulatory approval", "due diligence", "synergies",
        "all-cash deal", "all-stock deal", "premium", "hostile bid",
        "friendly deal", "agreed deal", "definitive agreement",
    ],
    "issuance": [
        "bond issuance", "debt offering", "equity offering", "share offering",
        "secondary offering", "follow-on offering", "shelf registration",
        "high yield", "investment grade", "credit rating", "coupon",
        "yield spread", "notes due", "senior notes", "subordinated",
        "convertible", "rights issue", "capital raise", "placing",
        "accelerated bookbuild", "at-the-market", "atm offering",
    ],
}

def fetch_newsapi(category):
    if not NEWS_API_KEY:
        return []
    try:
        params = {
            "q": NEWSAPI_QUERIES[category],
            "sources": NEWSAPI_SOURCES,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
            "apiKey": NEWS_API_KEY,
        }
        r = requests.get(NEWS_API_URL, params=params, timeout=10)
        data = r.json()
        if data.get("status") != "ok":
            print(f"  [!] NewsAPI error: {data.get('message', 'unknown error')}")
            return []
        articles = []
        for a in data.get("articles", []):
            articles.append({
                "source": f"NewsAPI — {a.get('source', {}).get('name', 'Unknown')}",
                "title": a.get("title", ""),
                "summary": (a.get("description") or "")[:500],
                "link": a.get("url", ""),
                "published": a.get("publishedAt", ""),
                "score": 3,
            })
        return articles
    except Exception as e:
        print(f"  [!] NewsAPI fetch error: {e}")
        return []

def fetch_all_news_categorized():
    all_articles = []

    for name, url in NEWS_FEEDS.items():
        print(f"  News: {name}...")
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                summary = entry.get("summary", entry.get("description", ""))
                all_articles.append({
                    "source": name,
                    "title": entry.get("title", ""),
                    "summary": BeautifulSoup(summary, "html.parser").get_text()[:500].strip(),
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                })
        except Exception as e:
            print(f"  [!] Error: {e}")

    categorized = {cat: [] for cat in CATEGORY_KEYWORDS}

    for article in all_articles:
        text = (article["title"] + " " + article["summary"]).lower()
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score >= 1:
                article_copy = article.copy()
                article_copy["score"] = score
                categorized[category].append(article_copy)

    for cat in categorized:
        seen = set()
        unique = []
        for a in categorized[cat]:
            if a["title"] not in seen:
                seen.add(a["title"])
                unique.append(a)
        categorized[cat] = sorted(unique, key=lambda x: x["score"], reverse=True)

    # Fetch targeted NewsAPI results per category and merge
    if NEWS_API_KEY:
        print("  Fetching NewsAPI (Bloomberg, WSJ, Reuters, CNBC...)...")
        for cat in categorized:
            newsapi_items = fetch_newsapi(cat)
            existing_titles = {a["title"] for a in categorized[cat]}
            for item in newsapi_items:
                if item["title"] not in existing_titles:
                    categorized[cat].append(item)
                    existing_titles.add(item["title"])
            categorized[cat] = sorted(categorized[cat], key=lambda x: x.get("score", 1), reverse=True)

    return categorized
