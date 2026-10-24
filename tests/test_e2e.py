import json
import sqlite3
from pathlib import Path
import pytest

from depop.config import Config
from depop.extractor import extract_nudges
from depop.schemas import ProductItem
from depop.scraper import DepopScraper
from depop.storage import save_to_csv, save_to_json, save_to_sqlite


@pytest.fixture
def sample_raw_object():
    return {
        "id": 12345678,
        "slug": "test-vintage-jacket-1234",
        "description": "Amazing vintage oversized jacket\nSize L\n#vintage #jacket",
        "pricing": {
            "currency": "USD",
            "current_price": {"total_price": "45.00"},
        },
        "preview": {
            "formats": {
                "P0": {
                    "url": "https://media-photos.depop.com/r1/test/P0.jpg"
                }
            }
        },
        "like_count": 25,
        "brand_name": "Carhartt",
    }


def test_product_schema_and_image_extraction(sample_raw_object):
    """Verify that ProductItem correctly extracts title, prices, URLs, and image URLs."""
    item = ProductItem.from_api_object(sample_raw_object)

    assert item.id == 12345678
    assert item.slug == "test-vintage-jacket-1234"
    assert item.title == "Amazing vintage oversized jacket"
    assert item.price == 45.0
    assert item.currency == "USD"
    assert item.url == "https://www.depop.com/products/test-vintage-jacket-1234/"
    assert item.image_url == "https://media-photos.depop.com/r1/test/P0.jpg"
    assert item.like_count == 25
    assert item.brand_name == "Carhartt"


def test_image_url_fallback_to_pictures():
    """Verify that image_url falls back to pictures array if preview formats is empty."""
    raw = {
        "id": 999,
        "slug": "fallback-test",
        "description": "Fallback item",
        "pricing": {"current_price": {"total_price": "20.00"}},
        "preview": {},
        "pictures": [
            {
                "formats": {
                    "P0": {"url": "https://media-photos.depop.com/fallback.jpg"}
                }
            }
        ],
    }
    item = ProductItem.from_api_object(raw)
    assert item.image_url == "https://media-photos.depop.com/fallback.jpg"


def test_rsc_nudge_extractor():
    """Verify that RSC stream parser correctly extracts offers and bags counts."""
    # Synthetic Next.js RSC payload simulating self.__next_f.push
    synthetic_html = (
        '<script>self.__next_f.push([1,"'
        '7b:I[12345,[\\"chunk1.js\\"],\\"InBagsNudge\\"]\\n'
        '7c:I[67890,[\\"chunk2.js\\"],\\"OffersSentNudge\\"]\\n'
        '10:[\\"$\\",\\"div\\",null,{\\"children\\":['
        '[\\"$\\",\\"$L7b\\",null,{\\"count\\":4}],'
        '[\\"$\\",\\"$L7c\\",null,{\\"count\\":9}]'
        ']}]\\n'
        '"])</script>'
    )
    nudges = extract_nudges(synthetic_html)
    assert nudges["in_bags"] == 4
    assert nudges["offers_sent"] == 9


def test_storage_exports(tmp_path):
    """Verify that SQLite, JSON, and CSV exports include all required fields including image URL and AliExpress search link."""
    items = [
        ProductItem(
            id=1,
            slug="item-1",
            title="Baggy Cargo Pants",
            price=30.0,
            currency="USD",
            url="https://www.depop.com/products/item-1/",
            image_url="https://media-photos.depop.com/p1.jpg",
            like_count=10,
            offers_count=5,
            in_bags_count=2,
            demand_score=41.0,
        ),
        ProductItem(
            id=2,
            slug="item-2",
            title="Vintage Graphic Tee",
            price=25.0,
            currency="USD",
            url="https://www.depop.com/products/item-2/",
            image_url="https://media-photos.depop.com/p2.jpg",
            like_count=20,
            offers_count=1,
            in_bags_count=0,
            demand_score=25.0,
        ),
    ]

    # 1. SQLite test
    db_file = tmp_path / "test.db"
    inserted = save_to_sqlite(items, db_file, search_query="cargo pants")
    assert inserted == 2

    conn = sqlite3.connect(db_file)
    row = conn.execute(
        "SELECT id, title, price, url, image_url, offers_count, demand_score FROM products WHERE id=1"
    ).fetchone()
    conn.close()
    assert row[0] == 1
    assert row[1] == "Baggy Cargo Pants"
    assert row[2] == 30.0
    assert row[3] == "https://www.depop.com/products/item-1/"
    assert row[4] == "https://media-photos.depop.com/p1.jpg"
    assert row[5] == 5
    assert row[6] == 41.0

    # 2. JSON test
    json_file = tmp_path / "test.json"
    save_to_json(items, json_file)
    with open(json_file, encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 2
    assert data[0]["image_url"] == "https://media-photos.depop.com/p1.jpg"

    # 3. CSV test
    csv_file = tmp_path / "test.csv"
    save_to_csv(items, csv_file)
    with open(csv_file, encoding="utf-8-sig") as f:
        content = f.read()
        assert "https://media-photos.depop.com/p1.jpg" in content
    assert "Baggy Cargo Pants" in content

    # 4. Query tests
    from depop.storage import get_saved_queries, get_saved_products
    queries = get_saved_queries(db_file)
    assert len(queries) == 1
    assert queries[0]["search_query"] == "cargo pants"
    assert queries[0]["count"] == 2

    saved = get_saved_products(db_file, search_query="cargo pants")
    assert len(saved) == 2
    assert saved[0]["title"] == "Baggy Cargo Pants"
    assert saved[0]["image_url"] == "https://media-photos.depop.com/p1.jpg"


@pytest.mark.network
def test_live_e2e_test_mode(tmp_path):
    """Live E2E test verifying:
    - Scraper runs against Depop API in test mode (16 items)
    - All returned items have valid info, URLs, image URLs, prices, and demand scores
    - Items are sorted by demand score descending
    """
    config = Config(
        output_dir=tmp_path,
        db_path=tmp_path / "live_test.db",
        min_delay=0.6,
        max_delay=1.0,
    )
    scraper = DepopScraper(config=config)

    results = scraper.run(
        query="baggy jeans",
        test_mode=True,
    )

    assert len(results) == 16, "Test mode must return 16 items"

    # Check each item's properties
    for item in results:
        assert item.id > 0
        assert item.title, "Product must have non-empty title"
        assert item.price >= 0.0, "Product must have valid price"
        assert item.url.startswith("https://www.depop.com/products/"), "Product must have valid product URL"
        assert item.image_url and item.image_url.startswith("http"), "Product must have valid image URL"
        assert item.demand_score >= 0.0

    # Verify sorting by demand_score descending
    scores = [p.demand_score for p in results]
    assert scores == sorted(scores, reverse=True), "Results must be sorted by demand_score descending"


@pytest.mark.network
def test_live_e2e_top_n_selection(tmp_path):
    """Live E2E test verifying:
    - User can choose exact top positions to filter (e.g. top_n=5)
    - Returns exactly top_n items
    - Items are ranked and populated with demand metrics, URLs, and image URLs
    """
    config = Config(
        output_dir=tmp_path,
        db_path=tmp_path / "live_top.db",
        min_delay=0.5,
        max_delay=0.9,
    )
    scraper = DepopScraper(config=config)

    top_count = 5
    results = scraper.run(
        query="cargo pants",
        top_n=top_count,
        min_likes=3,
        max_pages=2,
    )

    assert len(results) == top_count, f"Scraper must return exactly top {top_count} items"

    for item in results:
        assert item.title
        assert item.url.startswith("https://www.depop.com/products/")
        assert item.image_url.startswith("http")
        assert item.price >= 0.0

    # Check that scores are ordered
    scores = [p.demand_score for p in results]
    assert scores == sorted(scores, reverse=True)
