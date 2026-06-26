import os
from datetime import datetime
from categorized_news import fetch_all_news_categorized
from sec_fetcher import fetch_sec_filings
from summarizer import extractive_summary, CATEGORY_SUMMARIES
from pdf_generator import generate_report

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")

CATEGORIES = ["hedge_fund", "ipo", "ma", "issuance"]

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"\n{'='*55}")
    print(f"  HEDGE FUND NEWS AGENT")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*55}\n")

    print("[1/3] Fetching and categorizing news...")
    news_by_category = fetch_all_news_categorized()
    for cat, items in news_by_category.items():
        print(f"      {CATEGORY_SUMMARIES[cat]['title']}: {len(items)} articles")

    print("\n[2/3] Fetching SEC filings...")
    sec_by_category = {}
    for cat in CATEGORIES:
        sec_by_category[cat] = fetch_sec_filings(cat)
        print(f"      {CATEGORY_SUMMARIES[cat]['title']}: {len(sec_by_category[cat])} filings")

    print("\n[3/3] Generating reports...")
    generated = []
    for cat in CATEGORIES:
        news_items = news_by_category.get(cat, [])
        sec_items = sec_by_category.get(cat, [])
        all_items = news_items + sec_items

        cfg = CATEGORY_SUMMARIES[cat]
        summary_points = extractive_summary(all_items, cfg["keywords"], max_points=5)

        if all_items:
            path = generate_report(cat, news_items, sec_items, summary_points, OUTPUT_DIR)
            print(f"      Saved: {os.path.basename(path)}")
            generated.append(path)
        else:
            print(f"      {cfg['title']}: no items found, skipping.")

    print(f"\n{'='*55}")
    print(f"  Done! {len(generated)} reports saved to:")
    print(f"  {OUTPUT_DIR}")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    main()
