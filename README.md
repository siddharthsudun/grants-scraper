# grants-scraper

Finds every startup grant, scheme, and funding opportunity a company could apply to, in one run. Built to hunt funding for Ultimate Chicken, it scrapes **37 official sources** (central + state government, incubators, accelerators, corporate and investor programs) plus **Reddit, Google, and Twitter/X** for anything the official sites miss, then uses an LLM to normalize each into a clean, deduped CSV.

## What it does

```
official sources (Firecrawl) ─┐
Reddit / Google / X (Apify) ──┼─▶ LLM enrichment ─▶ deduped, structured CSV
                              ┘   (eligibility, amount, deadline, link, fit)
```

- **37 official sources** across 9 categories: `central_gov` (14), `state_gov` (5), `incubator` (4), `accelerator` (3), `investor` (3), `corporate` (3), `university` (2), `prerequisite` (2, e.g. DPIIT + Udyam registration), `state_incubator` (1). Full list in [`sources.py`](sources.py).
- **Social discovery** — Reddit, Google Search, and Twitter/X via Apify actors, to catch grants that aren't indexed on the official portals. Degrades gracefully if `APIFY_API_KEY` isn't set.
- **LLM enrichment** — each raw hit is parsed into structured fields (name, eligibility, amount, deadline, source URL, relevance) and deduplicated.

## Run

```bash
pip install -r requirements.txt
./run.sh                        # full run: official + social + enrich
python main.py --official-only  # skip social scraping
python main.py --resume raw_XYZ.json   # re-enrich saved raw data, no re-scrape
```

Output CSVs land in `output/` (sample runs are committed so you can see the shape).

## Config

- `FIRECRAWL_API_KEY` — official-site scraping
- `APIFY_API_KEY` — social discovery (optional; skipped if unset)
- `ANTHROPIC_API_KEY` — enrichment

Copy `.env.example` to `.env` and fill in. Secrets are gitignored.

## Layout

```
sources.py          the 37 official sources + social queries
scrape_official.py  Firecrawl scraping of official portals
scrape_social.py    Reddit / Google / Twitter via Apify
enrich.py           LLM parsing + dedupe into structured rows
main.py             orchestrator (full / official-only / resume)
```
