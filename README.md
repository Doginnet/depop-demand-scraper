# Depop Trending & Demand Scraper

A lightweight, high-performance scraper for dropshippers and e-commerce researchers to uncover trending products on Depop by analyzing real buyer demand signals: **Offers**, **In-Bag additions**, and **Likes**.

## Features

- **Anti-Bot Bypass**: Uses `curl_cffi` with Chrome 124 TLS fingerprint impersonation and session warm-up. No heavy headless browsers needed.
- **Next.js RSC Extraction**: Reverse-engineers React Server Components streamed in `self.__next_f.push` to extract hidden metrics:
  - `OffersSentNudge`: Exact number of offers sent by buyers.
  - `InBagsNudge`: Number of buyers who currently have the item in their bag/cart.
- **Two-Stage Architecture**: Fast API search for bulk listings, followed by targeted HTML enrichment for promising candidates.
- **Weighted Demand Scoring**: Prioritizes actual purchase intent:
  $$\text{Score} = (\text{Offers} \times 5.0) + (\text{In Bags} \times 3.0) + (\text{Likes} \times 1.0)$$
- **Multi-Format Export**:
  - **SQLite**: Local database (`output/depop.db`) with UPSERT support.
  - **JSON**: Structured payload for programmatic access.
  - **CSV**: Includes pre-built AliExpress search links for instant dropshipping product sourcing.

## Installation

Using [uv](https://github.com/astral-sh/uv):

```bash
uv sync
```

## Quick Start

### 1. Test Mode (Quick 16-item run)
```bash
uv run depop "baggy jeans" --test
```
or via Python:
```bash
uv run python main.py "baggy jeans" --test
```

### 2. Full Search & Ranking
Scrape up to 3 pages of search results, filter products with at least 5 likes, enrich with offers, and output the Top 20:
```bash
uv run depop "vintage leather jacket" --min-likes 5 --top 20
```

### 3. CLI Options
| Argument | Description | Default |
|---|---|---|
| `query` | Search query | `"baggy jeans"` |
| `--test`, `-t` | Run test mode (first 16 items) | `False` |
| `--min-likes`, `-l` | Minimum likes threshold to qualify for HTML offer parsing | `5` |
| `--top` | Number of top items to export | `20` |
| `--pages`, `-p` | Maximum pages of search API results to fetch | `3` |
| `--verbose`, `-v` | Enable debug logging | `False` |

## Project Structure

```
depop/
├── src/depop/
│   ├── config.py       # Scraper settings, delays, formula weights
│   ├── schemas.py      # Pydantic data models
│   ├── client.py       # HTTP client with Chrome 124 TLS impersonation
│   ├── extractor.py    # RSC stream parser for Offers and InBags nudges
│   ├── storage.py      # SQLite, JSON, and CSV exporters
│   ├── scraper.py      # Two-stage pipeline orchestrator
│   └── cli.py          # Command-line interface
├── output/             # Generated database and export files
├── logs/               # Log files with daily rotation
├── main.py             # Script entrypoint
└── pyproject.toml      # uv project configuration
```
