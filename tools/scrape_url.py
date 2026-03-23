"""
Deep-scrape a single URL for full article content using trafilatura.

Usage:
    python tools/scrape_url.py "https://example.com/article"
    python tools/scrape_url.py "https://example.com/article" --output .tmp/article.json
"""

import argparse
import io
import json
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import trafilatura


def scrape(url: str, timeout: int = 15) -> dict:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return {"url": url, "error": "Failed to fetch URL"}

    metadata = trafilatura.extract(
        downloaded,
        output_format="json",
        include_comments=False,
        include_links=True,
        with_metadata=True,
    )

    if not metadata:
        return {"url": url, "error": "Failed to extract content"}

    data = json.loads(metadata)
    return {
        "title": data.get("title", ""),
        "author": data.get("author", ""),
        "date": data.get("date", ""),
        "text": data.get("text", ""),
        "url": url,
    }


def main():
    parser = argparse.ArgumentParser(description="Deep-scrape a URL for article content")
    parser.add_argument("url", help="The URL to scrape")
    parser.add_argument("--output", help="Optional output file path (default: stdout)")
    args = parser.parse_args()

    result = scrape(args.url)

    output = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Saved to: {args.output}")
    else:
        print(output)

    if "error" in result:
        sys.exit(1)


if __name__ == "__main__":
    main()
