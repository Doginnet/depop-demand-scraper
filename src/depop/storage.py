import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from loguru import logger

from depop.schemas import ProductItem


def init_db(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with required tables and indexes."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                slug TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                currency TEXT NOT NULL,
                url TEXT NOT NULL,
                image_url TEXT,
                brand_name TEXT,
                like_count INTEGER NOT NULL DEFAULT 0,
                offers_count INTEGER NOT NULL DEFAULT 0,
                in_bags_count INTEGER NOT NULL DEFAULT 0,
                demand_score REAL NOT NULL DEFAULT 0.0,
                search_query TEXT,
                scraped_at TEXT NOT NULL
            );
        """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_score ON products (demand_score DESC);"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_products_offers ON products (offers_count DESC);"
        )
    return conn


def save_to_sqlite(
    products: list[ProductItem], db_path: Path, search_query: str = ""
) -> int:
    """Upsert products into the SQLite database."""
    if not products:
        return 0

    conn = init_db(db_path)
    now_str = datetime.now().isoformat()
    inserted = 0

    with conn:
        for p in products:
            conn.execute(
                """
                INSERT INTO products (
                    id, slug, title, description, price, currency, url, image_url,
                    brand_name, like_count, offers_count, in_bags_count, demand_score,
                    search_query, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    price = excluded.price,
                    like_count = excluded.like_count,
                    offers_count = excluded.offers_count,
                    in_bags_count = excluded.in_bags_count,
                    demand_score = excluded.demand_score,
                    scraped_at = excluded.scraped_at;
            """,
                (
                    p.id,
                    p.slug,
                    p.title,
                    p.description,
                    p.price,
                    p.currency,
                    p.url,
                    p.image_url,
                    p.brand_name,
                    p.like_count,
                    p.offers_count,
                    p.in_bags_count,
                    p.demand_score,
                    search_query,
                    now_str,
                ),
            )
            inserted += 1

    conn.close()
    logger.info(f"Saved/Updated {inserted} products in SQLite database at {db_path}")
    return inserted


def save_to_json(
    products: list[ProductItem], filepath: Path, indent: int = 2
) -> Path:
    """Export products to a formatted JSON file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    data = [p.model_dump(mode="json") for p in products]
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    logger.info(f"Saved {len(products)} products to JSON at {filepath}")
    return filepath


def save_to_csv(products: list[ProductItem], filepath: Path) -> Path:
    """Export products to CSV with AliExpress search link column for dropshipping analysis."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "title",
        "price",
        "currency",
        "offers_count",
        "in_bags_count",
        "like_count",
        "demand_score",
        "brand_name",
        "url",
        "image_url",
        "scraped_at",
    ]

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in products:
            writer.writerow(
                {
                    "id": p.id,
                    "title": p.title,
                    "price": p.price,
                    "currency": p.currency,
                    "offers_count": p.offers_count,
                    "in_bags_count": p.in_bags_count,
                    "like_count": p.like_count,
                    "demand_score": round(p.demand_score, 2),
                    "brand_name": p.brand_name or "",
                    "url": p.url,
                    "image_url": p.image_url or "",
                    "scraped_at": p.scraped_at.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

    logger.info(f"Saved {len(products)} products to CSV at {filepath}")
    return filepath


def get_saved_queries(db_path: Path) -> list[dict]:
    """Return distinct search queries and their product counts from SQLite."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with conn:
        rows = conn.execute(
            """
            SELECT search_query, COUNT(*) as count, MAX(scraped_at) as last_scraped
            FROM products
            WHERE search_query IS NOT NULL AND search_query != ''
            GROUP BY search_query
            ORDER BY last_scraped DESC
            """
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_saved_products(
    db_path: Path, search_query: str | None = None, limit: int = 100
) -> list[dict]:
    """Retrieve saved products sorted by demand score."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    with conn:
        if search_query:
            rows = conn.execute(
                """
                SELECT * FROM products
                WHERE search_query = ?
                ORDER BY demand_score DESC, offers_count DESC, like_count DESC
                LIMIT ?
                """,
                (search_query, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM products
                ORDER BY demand_score DESC, offers_count DESC, like_count DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
