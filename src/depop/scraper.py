from datetime import datetime
from pathlib import Path
from loguru import logger

from depop.client import DepopClient
from depop.config import Config, default_config
from depop.extractor import extract_nudges
from depop.schemas import ProductItem
from depop.storage import save_to_csv, save_to_json, save_to_sqlite


class DepopScraper:
    """Orchestrates search collection, candidate filtering, HTML offer enrichment,

    ranking by demand score, and exporting.
    """

    def __init__(self, config: Config = default_config):
        self.config = config

    def calculate_score(self, item: ProductItem) -> float:
        """Calculate weighted demand score prioritizing offers and in-bag counts."""
        return (
            (item.offers_count * self.config.weight_offers)
            + (item.in_bags_count * self.config.weight_in_bags)
            + (item.like_count * self.config.weight_likes)
        )

    def run(
        self,
        query: str,
        min_likes: int | None = None,
        top_n: int | None = None,
        max_pages: int | None = None,
        test_mode: bool = False,
    ) -> list[ProductItem]:
        min_likes = (
            min_likes
            if min_likes is not None
            else self.config.default_min_likes
        )
        top_n = top_n if top_n is not None else self.config.default_top_n

        # If user explicitly provided max_pages, use it. Otherwise, calculate a smart ceiling
        if test_mode:
            pages_ceiling = 1
        elif max_pages is not None:
            pages_ceiling = max_pages
        else:
            pages_ceiling = max(5, min(12, (top_n // 4) + 2))

        logger.info(
            f"=== Starting Depop Scraper for query: '{query}' (test_mode={test_mode}, min_likes={min_likes}, top_n={top_n}, max_pages={pages_ceiling}) ==="
        )

        candidates: list[ProductItem] = []

        with DepopClient(self.config) as client:
            # 1. Collect search results from API
            cursor = ""
            limit = 16 if test_mode else self.config.default_limit

            page = 1
            while page <= pages_ceiling:
                logger.info(f"Fetching search results page {page}/{pages_ceiling}...")
                objects, meta = client.search(
                    query=query, limit=limit, cursor=cursor
                )
                if not objects:
                    logger.warning("No more products returned from search API.")
                    break

                for obj in objects:
                    item = ProductItem.from_api_object(
                        obj, base_url=self.config.base_url
                    )
                    candidates.append(item)

                if test_mode or not meta.has_more or not meta.cursor:
                    break

                # Stop early if we already have enough candidate items meeting min_likes
                qualified_count = sum(1 for p in candidates if p.like_count >= min_likes)
                if not test_mode and max_pages is None and qualified_count >= int(top_n * 1.25):
                    logger.info(
                        f"Collected {qualified_count} candidate items meeting min_likes={min_likes}. Sufficient for top-{top_n}."
                    )
                    break

                cursor = meta.cursor
                page += 1

            logger.info(f"Total raw items collected from search: {len(candidates)}")

            # 2. Filter candidates for offer enrichment
            if test_mode:
                filtered_candidates = candidates
            else:
                qualified = [p for p in candidates if p.like_count >= min_likes]
                # If qualified is less than top_n, backfill with remaining best candidates by likes
                if len(qualified) < top_n and len(candidates) > len(qualified):
                    remaining = [p for p in candidates if p.like_count < min_likes]
                    remaining.sort(key=lambda x: x.like_count, reverse=True)
                    needed = top_n - len(qualified)
                    backfill = remaining[:needed]
                    logger.info(
                        f"Found {len(qualified)} items with >= {min_likes} likes. Adding {len(backfill)} next best items by likes to ensure top-{top_n} selection."
                    )
                    filtered_candidates = qualified + backfill
                else:
                    filtered_candidates = qualified

            # To stay lightweight and polite, cap candidate enrichment pool
            enrichment_limit = 16 if test_mode else max(top_n, 40)
            if len(filtered_candidates) > enrichment_limit:
                filtered_candidates.sort(key=lambda x: x.like_count, reverse=True)
                filtered_candidates = filtered_candidates[:enrichment_limit]

            logger.info(
                f"Enriching {len(filtered_candidates)} candidate products with offers and in-bag counts from HTML..."
            )

            # 3. Enrich candidates with HTML offers & in_bags counts
            for i, item in enumerate(filtered_candidates, 1):
                logger.info(
                    f"[{i}/{len(filtered_candidates)}] Inspecting: {item.slug} (Likes: {item.like_count})"
                )
                html = client.fetch_product_html(item.url)
                if html:
                    nudges = extract_nudges(html)
                    item.offers_count = nudges.get("offers_sent", 0)
                    item.in_bags_count = nudges.get("in_bags", 0)
                item.demand_score = self.calculate_score(item)

            # 4. Rank candidates by demand score
            filtered_candidates.sort(
                key=lambda x: (x.demand_score, x.offers_count, x.in_bags_count, x.like_count),
                reverse=True,
            )
            top_products = filtered_candidates[:top_n]

            logger.info(
                f"Selected Top-{len(top_products)} products based on demand score."
            )

            # 5. Export results
            self._export_results(top_products, query)

            return top_products

    def _export_results(self, products: list[ProductItem], query: str):
        if not products:
            logger.warning("No products to export.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_query = "".join(
            c if c.isalnum() else "_" for c in query
        ).strip("_")

        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        # 1. SQLite
        save_to_sqlite(products, self.config.db_path, search_query=query)

        # 2. JSON
        json_file = (
            self.config.output_dir / f"products_{sanitized_query}_{timestamp}.json"
        )
        save_to_json(products, json_file)

        # 3. CSV
        csv_file = (
            self.config.output_dir / f"products_{sanitized_query}_{timestamp}.csv"
        )
        save_to_csv(products, csv_file)

        logger.info(f"Export completed: DB={self.config.db_path}, JSON={json_file}, CSV={csv_file}")
