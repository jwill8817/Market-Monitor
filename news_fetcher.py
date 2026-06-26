import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime

NEWS_FEEDS = {
    "Reuters Business": "https://feeds.reuters.com/reuters/businessNews",
    "Yahoo Finance": "https://finance.yahoo.com/news/rssindex",
    "FT Markets": "https://www.ft.com/rss/home/uk",
    "Zero Hedge": "https://feeds.feedburner.com/zerohedge/feed",
    "WSJ Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "Seeking Alpha": "https://seekingalpha.com/feed.xml",
    "SEC 8-K Filings": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=15&search_text=&output=atom",
    "SEC 13F Filings": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=13F&dateb=&owner=include&count=15&search_text=&output=atom",
}

KEYWORDS = [
    "merger", "acquisition", "earnings", "fed", "federal reserve",
    "interest rate", "inflation", "gdp", "hedge fund", "private equity",
    "ipo", "bankruptcy", "restructuring", "dividend", "buyback", "guidance",
    "recession", "rally", "selloff", "downgrade", "upgrade", "macro",
    "credit", "bond", "yield", "spread", "volatility", "short", "long",
    "position", "portfolio", "capital", "leverage", "liquidity"
]

def fetch_feed(name, url):
    try:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:10]:
            articles.append({
                "source": name,
                "title": entry.get("title", "No title"),
                "summary": entry.get("summary", "")[:400],
                "link": entry.get("link", ""),
                "published": entry.get("published", "Unknown date"),
            })
        return articles
    except Exception as e:
        print(f"  [!] Error fetching {name}: {e}")
        return []

def is_relevant(article):
    text = (article["title"] + " " + article["summary"]).lower()
    return any(kw in text for kw in KEYWORDS)

def fetch_all_news():
    all_articles = []
    for name, url in NEWS_FEEDS.items():
        print(f"  Fetching {name}...")
        articles = fetch_feed(name, url)
        all_articles.extend(articles)
    relevant = [a for a in all_articles if is_relevant(a)]
    return relevant
