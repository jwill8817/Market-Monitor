import feedparser
import requests
from bs4 import BeautifulSoup

SEC_BASE = "https://www.sec.gov"

FILING_FEEDS = {
    "hedge_fund": [
        ("13F Holdings", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=13F-HR&dateb=&owner=include&count=20&search_text=&output=atom"),
        ("13D Activist", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=SC+13D&dateb=&owner=include&count=20&search_text=&output=atom"),
        ("13G Passive", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=SC+13G&dateb=&owner=include&count=20&search_text=&output=atom"),
    ],
    "ipo": [
        ("S-1 IPO Registration", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=S-1&dateb=&owner=include&count=20&search_text=&output=atom"),
        ("S-11 REIT IPO", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=S-11&dateb=&owner=include&count=10&search_text=&output=atom"),
        ("424B Prospectus", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=424B4&dateb=&owner=include&count=20&search_text=&output=atom"),
    ],
    "ma": [
        ("8-K Material Events", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=8-K&dateb=&owner=include&count=30&search_text=&output=atom"),
        ("SC TO Tender Offers", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=SC+TO-T&dateb=&owner=include&count=20&search_text=&output=atom"),
        ("Merger Proxy DEFM14A", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=DEFM14A&dateb=&owner=include&count=20&search_text=&output=atom"),
    ],
    "issuance": [
        ("S-3 Shelf Registration", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=S-3&dateb=&owner=include&count=20&search_text=&output=atom"),
        ("424B3 Prospectus Supplement", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=424B3&dateb=&owner=include&count=20&search_text=&output=atom"),
        ("Free Writing Prospectus", f"{SEC_BASE}/cgi-bin/browse-edgar?action=getcurrent&type=FWP&dateb=&owner=include&count=20&search_text=&output=atom"),
    ],
}

def fetch_sec_feed(name, url):
    try:
        headers = {"User-Agent": "HedgeFundAgent/1.0 jwill8817@gmail.com"}
        feed = feedparser.parse(url, request_headers=headers)
        items = []
        for entry in feed.entries[:15]:
            title = entry.get("title", "No title")
            summary = entry.get("summary", "")
            link = entry.get("link", "")
            published = entry.get("published", entry.get("updated", ""))
            items.append({
                "source": f"SEC — {name}",
                "title": title,
                "summary": BeautifulSoup(summary, "html.parser").get_text()[:400].strip(),
                "link": link,
                "published": published,
            })
        return items
    except Exception as e:
        print(f"  [!] Error fetching SEC {name}: {e}")
        return []

def fetch_sec_filings(category):
    results = []
    for name, url in FILING_FEEDS.get(category, []):
        print(f"  SEC: {name}...")
        results.extend(fetch_sec_feed(name, url))
    return results
