#!/usr/bin/env python3
"""
Ultimate Chicken — Grants & Schemes Scraper
Scrapes gov sites, incubators, Reddit, Google for every funding opportunity.

Usage:
  python main.py                        # full run
  python main.py --official-only        # skip social/Apify scraping
  python main.py --resume raw_XYZ.json  # skip scraping, re-enrich from saved raw data
  python main.py --enrich-only FILE     # alias for --resume
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from scrape_official import scrape_official_sources
from scrape_social import scrape_social_sources
from enrich import enrich_grants
from utils import save_to_csv, deduplicate_grants, load_raw

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def print_header():
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║      Ultimate Chicken — Grants & Schemes Scraper         ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()


def print_summary(grants: list[dict], csv_path: Path):
    print(f"\n{'─'*60}")
    print(f"  Total unique grants found: {len(grants)}")
    print(f"  CSV saved to: {csv_path}")
    print(f"{'─'*60}")

    by_type: dict[str, int] = {}
    for g in grants:
        t = g.get("type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1

    print("\n  By type:")
    for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {t:<20} {count}")

    top = sorted(grants, key=lambda x: x.get("relevance_score", 0), reverse=True)[:15]
    print(f"\n  Top 15 opportunities (by relevance for Ultimate Chicken):\n")
    print(f"  {'#':<3} {'Score':<7} {'Type':<14} {'Amount':<18} Name")
    print(f"  {'─'*3} {'─'*7} {'─'*14} {'─'*18} {'─'*30}")
    for i, g in enumerate(top, 1):
        score = g.get("relevance_score", "?")
        gtype = g.get("type", "?")[:13]
        amount = (g.get("amount") or "TBD")[:17]
        name = g.get("name", "?")[:50]
        print(f"  {i:<3} {score:<7} {gtype:<14} {amount:<18} {name}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Ultimate Chicken Grants Scraper")
    parser.add_argument("--official-only", action="store_true", help="Skip Apify social scraping")
    parser.add_argument("--resume", metavar="FILE", help="Load raw JSON and skip scraping")
    parser.add_argument("--enrich-only", metavar="FILE", help="Alias for --resume")
    parser.add_argument("--priority", type=int, default=3, help="Max priority level to scrape (0-3, default 3)")
    args = parser.parse_args()

    print_header()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    raw_path = OUTPUT_DIR / f"raw_{timestamp}.json"
    csv_path = OUTPUT_DIR / f"grants_{timestamp}.csv"

    resume_file = args.resume or args.enrich_only

    # ── Phase 1 & 2: Scraping ────────────────────────────────────────────────
    if resume_file:
        print(f"[RESUME] Loading raw data from {resume_file}...")
        all_raw = load_raw(resume_file)
        print(f"  → {len(all_raw)} raw items loaded")
    else:
        # Official sources
        print("[1/4] Scraping official sources (gov sites, incubators)...")
        official_raw = scrape_official_sources(priority_max=args.priority)
        print(f"  → {len(official_raw)} pages scraped")

        # Social / discovery
        if args.official_only:
            print("[2/4] Skipping social scraping (--official-only)")
            social_raw = []
        else:
            print("\n[2/4] Scraping social sources (Reddit, Google, Twitter)...")
            social_raw = scrape_social_sources()
            print(f"  → {len(social_raw)} social items found")

        all_raw = official_raw + social_raw

        # Save raw for resume
        raw_path.write_text(json.dumps(all_raw, indent=2, default=str))
        print(f"\n  Raw data saved → {raw_path}")
        print(f"  (Use --resume {raw_path} to re-enrich without re-scraping)")

    # ── Phase 3: Enrich with Claude ──────────────────────────────────────────
    print(f"\n[3/4] Enriching {len(all_raw)} items with Claude (Haiku)...")
    grants = enrich_grants(all_raw)
    print(f"  → {len(grants)} raw grant records extracted")

    # ── Phase 4: Deduplicate + Export ────────────────────────────────────────
    print("\n[4/4] Deduplicating and writing CSV...")
    grants = deduplicate_grants(grants)
    save_to_csv(grants, csv_path)

    print_summary(grants, csv_path)


if __name__ == "__main__":
    main()
