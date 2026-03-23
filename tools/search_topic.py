"""
Search a topic using Tavily API and return structured research results.

Usage:
    python tools/search_topic.py "AI in healthcare" --queries 5
    python tools/search_topic.py "AI in healthcare" --dry-run  # Use cached results
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
TMP_DIR = BASE_DIR / ".tmp"
CACHE_DIR = TMP_DIR / "search_cache"
OUTPUT_FILE = TMP_DIR / "search_results.json"
CACHE_MAX_AGE = 86400  # 24 hours


def get_cache_path(query: str) -> Path:
    key = hashlib.md5(query.encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < CACHE_MAX_AGE


def search_single(client: TavilyClient, query: str, dry_run: bool = False) -> list[dict]:
    cache_path = get_cache_path(query)

    if dry_run and is_cache_fresh(cache_path):
        print(f"  [cache hit] {query}")
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    if dry_run and not is_cache_fresh(cache_path):
        print(f"  [cache miss, skipping in dry-run] {query}")
        return []

    print(f"  [searching] {query}")
    response = client.search(query=query, search_depth="advanced", max_results=5)
    results = []
    for r in response.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0),
        })

    # Cache the results
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return results


def generate_sub_queries(topic: str, count: int) -> list[str]:
    queries = [topic]
    if count >= 2:
        queries.append(f"{topic} statistics 2026")
    if count >= 3:
        queries.append(f"{topic} latest developments 2026")
    if count >= 4:
        queries.append(f"{topic} trends and analysis")
    if count >= 5:
        queries.append(f"{topic} expert opinions insights")
    return queries[:count]


def main():
    parser = argparse.ArgumentParser(description="Search a topic using Tavily API")
    parser.add_argument("topic", help="The topic to research")
    parser.add_argument("--queries", type=int, default=5, help="Number of search queries (default: 5)")
    parser.add_argument("--dry-run", action="store_true", help="Use cached results only (no API calls)")
    parser.add_argument("--extra-queries", nargs="*", default=[], help="Additional custom search queries")
    args = parser.parse_args()

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("Error: TAVILY_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    client = TavilyClient(api_key=api_key)

    queries = generate_sub_queries(args.topic, args.queries)
    queries.extend(args.extra_queries)

    print(f"Researching: {args.topic}")
    print(f"Running {len(queries)} search queries...")

    all_results = []
    seen_urls = set()

    for query in queries:
        results = search_single(client, query, dry_run=args.dry_run)
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)

    # Sort by relevance score descending
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    TMP_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    print(f"\nFound {len(all_results)} unique results")
    print(f"Saved to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
