"""
Scrapes Reddit, Google Search results, and Twitter/X via Apify actors.
Falls back gracefully if APIFY_API_KEY is not set.
Returns list of raw dicts compatible with enrich.py.
"""
import os
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from tqdm import tqdm

from sources import GOOGLE_QUERIES, REDDIT_SOURCES, TWITTER_QUERIES

load_dotenv()


def _get_apify_client():
    key = os.environ.get("APIFY_API_KEY", "").strip()
    if not key:
        return None
    try:
        from apify_client import ApifyClient
        return ApifyClient(token=key)
    except ImportError:
        print("    ! apify-client not installed. Run: pip install apify-client")
        return None


def _scrape_google(client, queries: List[str]) -> List[Dict[str, Any]]:
    results = []
    print(f"    Running Google Search for {len(queries)} queries...")
    try:
        run = client.actor("apify/google-search-scraper").call(
            run_input={
                "queries": "\n".join(queries),
                "resultsPerPage": 8,
                "maxPagesPerQuery": 1,
                "languageCode": "en",
                "countryCode": "in",
            }
        )
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        for item in items:
            organic = item.get("organicResults", [])
            for r in organic:
                url = r.get("url", "")
                if not url:
                    continue
                results.append({
                    "source_id": "google_search",
                    "source_name": "Google Search",
                    "url": url,
                    "title": r.get("title", ""),
                    "content": r.get("description", "") + "\n\n" + r.get("title", ""),
                    "category": "search_result",
                    "tags": ["google", "discovery"],
                    "priority": 2,
                    "platform": "google",
                    "query": item.get("searchQuery", ""),
                })
    except Exception as e:
        print(f"    ✗ Google scrape failed: {e}")
    return results


def _scrape_reddit(client, sources: Dict[str, Any]) -> List[Dict[str, Any]]:
    results = []
    all_queries = sources["search_queries"]
    subreddits = sources["subreddits"]

    print(f"    Running Reddit search across {len(subreddits)} subreddits, {len(all_queries)} queries...")
    try:
        # Use apify/reddit-scraper
        run = client.actor("apify/reddit-scraper").call(
            run_input={
                "startUrls": [
                    {"url": f"https://www.reddit.com/r/{sub}/search/?q={q.replace(' ', '+')}&sort=relevance&t=year"}
                    for sub in subreddits
                    for q in all_queries[:3]  # 3 queries per sub to stay within limits
                ][:30],  # cap total requests
                "maxPostCount": 5,
                "maxComments": 10,
                "maxCommentsDepth": 2,
                "skipComments": False,
            }
        )
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        for item in items:
            body = item.get("body", "") or item.get("text", "") or ""
            title = item.get("title", "") or item.get("heading", "")
            url = item.get("url", "") or item.get("parsedUrl", {}).get("href", "")
            if not (body or title):
                continue
            # Include comments as context
            comments = item.get("comments", [])
            comment_text = "\n\n".join(
                f"Comment: {c.get('body', '')}" for c in comments[:5] if c.get("body")
            )
            content = f"POST TITLE: {title}\n\nPOST BODY: {body}\n\n{comment_text}"
            results.append({
                "source_id": "reddit",
                "source_name": f"Reddit r/{item.get('communityName', 'unknown')}",
                "url": url,
                "title": title,
                "content": content[:8000],
                "category": "social",
                "tags": ["reddit", "community", "insider"],
                "priority": 2,
                "platform": "reddit",
            })
    except Exception as e:
        print(f"    ✗ Reddit scrape failed: {e}")
    return results


def _scrape_twitter(client, queries: List[str]) -> List[Dict[str, Any]]:
    results = []
    print(f"    Running Twitter/X search for {len(queries)} queries...")
    try:
        run = client.actor("quacker/twitter-scraper").call(
            run_input={
                "searchTerms": queries[:8],  # cap
                "maxTweets": 20,
                "addUserInfo": False,
                "startUrls": [],
                "twitterHandles": [],
            }
        )
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        for item in items:
            text = item.get("full_text", "") or item.get("text", "")
            url = item.get("url", "") or f"https://twitter.com/i/web/status/{item.get('id', '')}"
            if not text:
                continue
            results.append({
                "source_id": "twitter",
                "source_name": "Twitter/X",
                "url": url,
                "title": text[:100],
                "content": text,
                "category": "social",
                "tags": ["twitter", "announcement"],
                "priority": 3,
                "platform": "twitter",
            })
    except Exception as e:
        print(f"    ✗ Twitter scrape failed (non-critical): {e}")
    return results


def _scrape_youtube_via_google(client, queries: List[str]) -> List[Dict[str, Any]]:
    """Use Google Search filtered to YouTube to find relevant grant videos."""
    yt_queries = [f"site:youtube.com {q}" for q in [
        "India startup grants explained 2025",
        "Startup India seed fund how to apply",
        "T-Hub Hyderabad how to apply selection",
        "PMFME scheme food startup India apply",
        "BITS Pilani startup incubator how to join",
    ]]
    results = []
    try:
        run = client.actor("apify/google-search-scraper").call(
            run_input={
                "queries": "\n".join(yt_queries),
                "resultsPerPage": 5,
                "maxPagesPerQuery": 1,
            }
        )
        items = client.dataset(run["defaultDatasetId"]).list_items().items
        for item in items:
            for r in item.get("organicResults", []):
                url = r.get("url", "")
                if "youtube.com/watch" not in url:
                    continue
                results.append({
                    "source_id": "youtube",
                    "source_name": "YouTube",
                    "url": url,
                    "title": r.get("title", ""),
                    "content": r.get("description", "") + "\nTitle: " + r.get("title", ""),
                    "category": "social",
                    "tags": ["youtube", "video", "tutorial"],
                    "priority": 3,
                    "platform": "youtube",
                })
    except Exception as e:
        print(f"    ✗ YouTube discovery failed (non-critical): {e}")
    return results


def scrape_social_sources() -> List[Dict[str, Any]]:
    """
    Runs all Apify-based scrapers. Gracefully skips if APIFY_API_KEY is missing.
    """
    client = _get_apify_client()
    if not client:
        print("    ! APIFY_API_KEY not set — skipping social/discovery scraping.")
        print("    → Add your Apify key to .env as APIFY_API_KEY and re-run.")
        return []

    all_results = []

    # Google Search (most valuable for discovery)
    google_results = _scrape_google(client, GOOGLE_QUERIES)
    print(f"      → {len(google_results)} Google results")
    all_results.extend(google_results)

    # Reddit (insider knowledge)
    reddit_results = _scrape_reddit(client, REDDIT_SOURCES)
    print(f"      → {len(reddit_results)} Reddit posts/comments")
    all_results.extend(reddit_results)

    # Twitter/X (announcements)
    twitter_results = _scrape_twitter(client, TWITTER_QUERIES)
    print(f"      → {len(twitter_results)} tweets")
    all_results.extend(twitter_results)

    # YouTube via Google
    yt_results = _scrape_youtube_via_google(client, [])
    print(f"      → {len(yt_results)} YouTube links")
    all_results.extend(yt_results)

    return all_results
