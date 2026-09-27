# Overview

This is a Depop shop scraping project. The idea is to collect items based on a search prompt, filter out only those that have likes and offers above the minimal threshold, and select the top items ranked by real demand.
The goal is to provide an automated tool for dropshipping market research, identifying trending/high-demand articles and their prices based on a search query, which the user can then source on platforms like AliExpress.

## Specs
- **Environment & Package Manager:** Python 3.12+, `uv` (`.venv`)
- **HTTP Client & Anti-bot:** `curl_cffi` (Chrome 124 TLS fingerprint impersonation, session warm-up, rate-limiting jitter)
- **Data Validation & Modeling:** `pydantic` v2
- **Logging:** `loguru` with colored console output and file rotation
- **Database & Storage:** SQLite (`output/depop.db`), JSON, and CSV (with AliExpress search links)
- **HTML / Demand Extractor:** Next.js RSC stream parser (`OffersSentNudge`, `InBagsNudge`)

## Demand Scoring Formula
`Demand Score = (Offers × 5.0) + (In Bags × 3.0) + (Likes × 1.0)`
Offers represent explicit buyer purchase intents and have the highest weight.

## Architecture
- `src/depop/config.py`: Settings, headers, URLs, delay ranges, formula weights.
- `src/depop/schemas.py`: Pydantic models for product items and search metadata.
- `src/depop/client.py`: Session management, search API calls with cursor pagination, product HTML retrieval.
- `src/depop/extractor.py`: Next.js App Router RSC stream reconstructor and nudge counter parser.
- `src/depop/storage.py`: SQLite UPSERT table, formatted JSON and CSV exporters.
- `src/depop/scraper.py`: Pipeline orchestrator (search -> likes filter -> HTML offer enrichment -> scoring -> export).
- `src/depop/cli.py`: Command-line interface with `--test`, `--min-likes`, `--top`, `--pages`, `--verbose`.

## Progress / Tasks
- [x] Analyze raw data response (`raw/search_products_*.json`)
- [x] Reverse-engineer Next.js RSC stream to extract offers count and bag count
- [x] Create Pydantic data schemas
- [x] Create configuration and demand scoring formula
- [x] Set up Loguru logging with rotation
- [x] Build cursor pagination logic on top of search API
- [x] Implement lightweight HTML RSC nudge parser
- [x] Implement multi-format storage (SQLite, JSON, CSV with AliExpress search links)
- [x] Create CLI interface with argparse and `--test` mode (first 16 items)
- [x] Create project documentation in Notion (`Depop Trending & Demand Scraper`, `SRS.md`, `PLAN.md`)
