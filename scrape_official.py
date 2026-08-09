"""
Scrapes official government sites, incubator pages, and university TBI pages
using Firecrawl. Returns list of raw dicts with {source_id, url, title, content, category, tags}.
"""
import os
import time
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from firecrawl.v1 import V1FirecrawlApp
from firecrawl.v1.client import V1ScrapeOptions
from tqdm import tqdm

from sources import OFFICIAL_SOURCES

load_dotenv()

_app: Optional[V1FirecrawlApp] = None

def _get_firecrawl() -> V1FirecrawlApp:
    global _app
    if _app is None:
        _app = V1FirecrawlApp(api_key=os.environ["FIRECRAWL_API_KEY"])
    return _app


def _scrape_single(source: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    fc = _get_firecrawl()
    url = source["url"]
    try:
        result = fc.scrape_url(url, formats=["markdown"], only_main_content=True, timeout=25000)
        content = result.markdown or ""
        if not content or len(content) < 100:
            return None
        title = result.title or (result.metadata.get("title") if isinstance(result.metadata, dict) else None) or source["name"]
        return {
            "source_id": source["id"],
            "source_name": source["name"],
            "url": url,
            "title": title,
            "content": content[:15000],
            "category": source["category"],
            "tags": source["tags"],
            "priority": source["priority"],
            "platform": "official",
        }
    except Exception as e:
        print(f"    ✗ Failed {source['id']}: {e}")
        return None


def _crawl_site(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    fc = _get_firecrawl()
    url = source["url"]
    results = []
    try:
        crawl_result = fc.crawl_url(
            url,
            limit=8,
            scrape_options=V1ScrapeOptions(formats=["markdown"]),
        )
        pages = crawl_result.data if hasattr(crawl_result, "data") and crawl_result.data else []
        for page in pages:
            content = page.markdown or ""
            if not content or len(content) < 200:
                continue
            page_url = url
            page_title = source["name"]
            if page.metadata and isinstance(page.metadata, dict):
                page_url = page.metadata.get("url") or url
                page_title = page.metadata.get("title") or source["name"]
            elif page.title:
                page_title = page.title
            results.append({
                "source_id": source["id"],
                "source_name": source["name"],
                "url": page_url,
                "title": page_title,
                "content": content[:15000],
                "category": source["category"],
                "tags": source["tags"],
                "priority": source["priority"],
                "platform": "official",
            })
    except Exception as e:
        print(f"    ✗ Failed crawl {source['id']}: {e}")
        # Fall back to single scrape
        single = _scrape_single(source)
        if single:
            results.append(single)
    return results


def scrape_official_sources(priority_max: int = 3) -> List[Dict[str, Any]]:
    """
    Scrapes all official sources up to priority_max (0=prerequisite, 1=high, 2=medium, 3=low).
    Returns list of raw page dicts.
    """
    sources = [s for s in OFFICIAL_SOURCES if s["priority"] <= priority_max]
    sources.sort(key=lambda x: x["priority"])

    all_results = []
    print(f"    Scraping {len(sources)} official sources...")

    for source in tqdm(sources, desc="    Official", ncols=80):
        if source.get("crawl"):
            pages = _crawl_site(source)
            all_results.extend(pages)
        else:
            page = _scrape_single(source)
            if page:
                all_results.append(page)
        time.sleep(0.5)

    return all_results
