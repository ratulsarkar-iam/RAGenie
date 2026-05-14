"""Live test: West Bengal news via Google News RSS in English, Hindi, Bengali.

Google News natively supports all Indian language region codes — no
rate limiting, no API key, no workarounds needed.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.news.fetcher import NewsFetcher, _build_url

QUERIES = [
    {
        "label":   "English  (region: in-en)",
        "keyword": "West Bengal",
        "region":  "in-en",
    },
    {
        "label":   "Hindi    (region: in-hi)",
        "keyword": "पश्चिम बंगाल",
        "region":  "in-hi",
    },
    {
        "label":   "Bengali  (region: in-bn)",
        "keyword": "পশ্চিমবঙ্গ",
        "region":  "in-bn",
    },
]

SEP = "─" * 72


def run():
    for q in QUERIES:
        print(f"\n{SEP}")
        print(f"  {q['label']}")
        print(f"  Keyword : {q['keyword']}")
        print(f"  RSS URL : {_build_url(q['keyword'], q['region'], None)}")
        print(SEP)

        fetcher = NewsFetcher(region=q["region"])
        articles = fetcher.fetch(keyword=q["keyword"], page_size=5)

        if not articles:
            print("  ⚠  No articles returned")
            continue

        for i, a in enumerate(articles, 1):
            title   = a.title[:80] if a.title else "(no title)"
            content = (a.content[:120] + "…") if len(a.content) > 120 else a.content
            pub     = a.published_at.strftime("%Y-%m-%d %H:%M") if a.published_at else "—"
            print(f"\n  [{i}] {title}")
            print(f"      Source : {a.source or '—'}   Date: {pub}")
            print(f"      Snippet: {content or '(empty)'}")

    print(f"\n{SEP}\nDone.\n")


if __name__ == "__main__":
    run()
