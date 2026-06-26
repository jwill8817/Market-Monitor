import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime

INSIGHT_FEEDS = {
    "Hussman Funds Weekly": "https://www.hussmanfunds.com/rss.xml",
    "AQR Research": "https://www.aqr.com/Insights/Research/rss",
    "Federal Reserve Papers": "https://www.federalreserve.gov/feeds/working_papers.xml",
    "Federal Reserve Speeches": "https://www.federalreserve.gov/feeds/speeches.xml",
    "IMF Blog": "https://www.imf.org/en/Blogs/rss",
    "IMF Working Papers": "https://www.imf.org/en/Publications/WP/rss",
    "BIS Working Papers": "https://www.bis.org/doclist/wppubls.rss",
    "BIS Quarterly Review": "https://www.bis.org/doclist/quartpubls.rss",
    "NBER Working Papers": "https://back.nber.org/rss/new.xml",
}

SCRAPED_SOURCES = {
    "Howard Marks (Oaktree)": "https://www.oaktreecapital.com/insights/howard-marks-memos",
    "Jeremy Grantham (GMO)": "https://www.gmo.com/americas/research-library/",
    "AQR Insights": "https://www.aqr.com/Insights/Research",
}

def fetch_feed(name, url):
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:5]:
            summary = entry.get("summary", entry.get("description", ""))
            items.append({
                "source": name,
                "title": entry.get("title", "No title"),
                "summary": BeautifulSoup(summary, "html.parser").get_text()[:500],
                "link": entry.get("link", ""),
                "published": entry.get("published", entry.get("updated", "Unknown date")),
            })
        return items
    except Exception as e:
        print(f"  [!] Error fetching {name}: {e}")
        return []

def scrape_oaktree():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://www.oaktreecapital.com/insights/howard-marks-memos", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "lxml")
        items = []
        for a in soup.select("a[href*='memo']")[:5]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if title and href:
                if not href.startswith("http"):
                    href = "https://www.oaktreecapital.com" + href
                items.append({
                    "source": "Howard Marks (Oaktree)",
                    "title": title,
                    "summary": "Howard Marks memo — click link to read full text.",
                    "link": href,
                    "published": "Recent",
                })
        return items
    except Exception as e:
        print(f"  [!] Error scraping Oaktree: {e}")
        return []

def scrape_gmo():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get("https://www.gmo.com/americas/research-library/", headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "lxml")
        items = []
        for a in soup.select("a")[:20]:
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if title and href and len(title) > 15:
                if not href.startswith("http"):
                    href = "https://www.gmo.com" + href
                items.append({
                    "source": "Jeremy Grantham (GMO)",
                    "title": title,
                    "summary": "GMO research — click link to read full text.",
                    "link": href,
                    "published": "Recent",
                })
                if len(items) >= 5:
                    break
        return items
    except Exception as e:
        print(f"  [!] Error scraping GMO: {e}")
        return []

def fetch_all_insights():
    all_items = []

    for name, url in INSIGHT_FEEDS.items():
        print(f"  Fetching {name}...")
        items = fetch_feed(name, url)
        all_items.extend(items)

    print("  Scraping Howard Marks (Oaktree)...")
    all_items.extend(scrape_oaktree())

    print("  Scraping Jeremy Grantham (GMO)...")
    all_items.extend(scrape_gmo())

    return all_items
