from collections import Counter
import re

def score_sentence(sentence, word_freq, keywords):
    words = re.findall(r'\w+', sentence.lower())
    score = sum(word_freq.get(w, 0) for w in words)
    score += sum(3 for kw in keywords if kw in sentence.lower())
    return score

def extractive_summary(items, keywords, max_points=5):
    if not items:
        return ["No items found for this category."]

    all_text = " ".join(
        (a.get("title", "") + " " + a.get("summary", "")) for a in items
    )
    words = re.findall(r'\w+', all_text.lower())
    stopwords = {"the","a","an","is","in","on","at","to","for","of","and",
                 "or","but","with","from","by","as","are","was","were","has",
                 "have","had","be","been","that","this","it","its","will",
                 "said","says","also","more","than","into","their","they",
                 "which","who","what","when","how","he","she","we","you","i"}
    word_freq = Counter(w for w in words if w not in stopwords and len(w) > 3)

    sentences = []
    for a in items:
        title = a.get("title", "").strip()
        summary = a.get("summary", "").strip()
        source = a.get("source", "")
        if title:
            sentences.append((score_sentence(title, word_freq, keywords) + 5, title, source))
        if summary:
            for sent in re.split(r'(?<=[.!?])\s+', summary):
                if len(sent) > 40:
                    sentences.append((score_sentence(sent, word_freq, keywords), sent, source))

    sentences.sort(key=lambda x: x[0], reverse=True)

    seen = set()
    points = []
    for score, sent, source in sentences:
        clean = sent.strip()
        if clean and clean not in seen and len(points) < max_points:
            seen.add(clean)
            points.append(clean)

    return points

CATEGORY_SUMMARIES = {
    "hedge_fund": {
        "title": "Hedge Fund Activity",
        "keywords": ["hedge fund", "activist", "short", "position", "13f", "filing"],
    },
    "ipo": {
        "title": "IPO Pipeline",
        "keywords": ["ipo", "listing", "public offering", "debut", "prospectus", "spac"],
    },
    "ma": {
        "title": "M&A Activity",
        "keywords": ["merger", "acquisition", "deal", "takeover", "buyout", "bid"],
    },
    "issuance": {
        "title": "Equity & Bond Issuance",
        "keywords": ["offering", "issuance", "bond", "notes", "equity", "raise"],
    },
}
