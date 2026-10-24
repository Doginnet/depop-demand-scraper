import asyncio
from pathlib import Path
import threading
import time
import webbrowser
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel
import uvicorn

from depop.config import default_config
from depop.schemas import ProductItem
from depop.scraper import DepopScraper
from depop.storage import get_saved_products, get_saved_queries

app = FastAPI(title="Depop Demand Scraper UI")
TEMPLATES_DIR = Path(__file__).parent / "templates"


class ScrapeRequest(BaseModel):
    query: str
    top_n: int = 20
    min_likes: int = 5
    test_mode: bool = False
    proxy: str | None = None


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serve the single-page dashboard HTML."""
    html_file = TEMPLATES_DIR / "index.html"
    if not html_file.exists():
        raise HTTPException(status_code=404, detail="Template index.html not found")
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/api/collections")
async def api_get_collections():
    """Return all past scraped search queries from SQLite database."""
    queries = get_saved_queries(default_config.db_path)
    return queries


@app.get("/api/products")
async def api_get_products(query: str | None = None, limit: int = 200):
    """Return saved products from SQLite for a given collection or all collections."""
    products = get_saved_products(
        default_config.db_path, search_query=query, limit=limit
    )
    return products


@app.post("/api/scrape")
async def api_scrape(req: ScrapeRequest):
    """Trigger scraper and return the resulting top products."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Search query cannot be empty")

    logger.info(
        f"Web UI triggered scrape: query='{req.query}', top_n={req.top_n}, min_likes={req.min_likes}, test_mode={req.test_mode}"
    )

    try:
        config = Config(proxies=[req.proxy]) if req.proxy else default_config
        scraper = DepopScraper(config=config)
        # Run blocking scraping operation in executor thread to keep server responsive
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            None,
            lambda: scraper.run(
                query=req.query.strip(),
                min_likes=req.min_likes,
                top_n=req.top_n,
                test_mode=req.test_mode,
            ),
        )
        return results
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def open_browser_delayed(url: str, delay: float = 1.0):
    """Open default web browser after server starts."""
    time.sleep(delay)
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.warning(f"Could not open browser automatically: {e}")


def start(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True):
    """Entrypoint to launch the web dashboard."""
    url = f"http://{host}:{port}"
    print("\n" + "=" * 65)
    print("Depop Demand Scraper - Web Dashboard")
    print(f"Running at: {url}")
    print("=" * 65 + "\n")

    if open_browser:
        threading.Thread(
            target=open_browser_delayed, args=(url,), daemon=True
        ).start()

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start()
