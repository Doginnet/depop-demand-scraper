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
        max_pages: int = 3,
        test_mode: bool = False,
    ) -> list[ProductItem]:
        min_likes = (
            min_likes
            if min_likes is not None
            else self.config.default_min_likes
        )
        top_n = top_n if top_n is not None else self.config.default_top_n

        logger.info(
            f"=== Starting Depop Scraper for query: '{query}' (test_mode={test_mode}, min_likes={min_likes}, top_n={top_n}) ==="
        )

        candidates: list[ProductItem] = []

        with DepopClient(self.config) as client:
            # 1. Collect search results from API
            cursor = ""
            limit = 16 if test_mode else self.config.default_limit
            pages_to_fetch = 1 if test_mode else max_pages

            for page in range(1, pages_to_fetch + 1):
                logger.info(f"Fetching search results page {page}...")
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
                cursor = meta.cursor

            logger.info(f"Total raw items collected from search: {len(candidates)}")

            # 2. Filter candidates for offer enrichment
            if test_mode:
                filtered_candidates = candidates
            else:
                filtered_candidates = [
                    p for p in candidates if p.like_count >= min_likes
                ]
                # If no products meet the threshold, fallback to top products by likes
                if not filtered_candidates and candidates:
                    logger.warning(
                        f"No products found with >= {min_likes} likes. Falling back to top {top_n} products by likes."
                    )
                    candidates.sort(key=lambda x: x.like_count, reverse=True)
                    filtered_candidates = candidates[:top_n]

            # To stay lightweight and polite, cap candidate enrichment pool
            enrichment_limit = 16 if test_mode else max(top_n * 2, 30)
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
