import random
import time
from urllib.parse import urlencode
from curl_cffi import requests
from loguru import logger

from depop.config import Config, default_config
from depop.schemas import SearchResponseMeta


class DepopClient:
    """Lightweight HTTP client for Depop with browser impersonation and polite rate-limiting."""

    def __init__(self, config: Config = default_config):
        self.config = config
        self.session = requests.Session(impersonate=self.config.impersonate_target)
        self._warmed_up = False

    def warm_up(self) -> bool:
        """Warm up session cookies and TLS context against the main domain."""
        if self._warmed_up:
            return True
        for attempt in range(1, 3):
            try:
                logger.info(f"Warming up Depop session (attempt {attempt})...")
                resp = self.session.get(
                    self.config.base_url,
                    headers=self.config.html_headers,
                    timeout=15,
                )
                if resp.status_code == 200:
                    self._warmed_up = True
                    logger.info("Session warmed up successfully.")
                    return True
                else:
                    logger.warning(
                        f"Warm-up returned status {resp.status_code}. Retrying in 1.5s..."
                    )
                    time.sleep(1.5)
            except Exception as e:
                logger.error(f"Warm-up request failed: {e}")
                time.sleep(1.5)
        return False

    def _sleep_delay(self):
        """Random delay between requests to simulate human interaction."""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        time.sleep(delay)

    def search(
        self,
        query: str,
        limit: int = 160,
        cursor: str = "",
        country: str = "us",
        currency: str = "USD",
    ) -> tuple[list[dict], SearchResponseMeta]:
        """Query the search products API endpoint.

        Returns raw objects and pagination metadata.
        """
        self.warm_up()
        self._sleep_delay()

        params = {
            "what": query,
            "after": cursor,
            "limit": limit,
            "country": country,
            "currency": currency,
            "from": "in_country_search",
            "include_like_count": "true",
        }
        url = f"{self.config.search_api_url}?{urlencode(params)}"
        logger.info(
            f"Searching Depop for '{query}' (limit={limit}, cursor='{cursor[:15]}...')..."
        )

        for attempt in range(1, 4):
            try:
                resp = self.session.get(
                    url, headers=self.config.api_headers, timeout=20
                )
                if resp.status_code == 200:
                    data = resp.json()
                    objects = data.get("objects", [])
                    meta_info = data.get("meta", {})
                    page_info = data.get("page_info", {})

                    meta = SearchResponseMeta(
                        total_count=meta_info.get("total_count", 0),
                        has_more=page_info.get("has_more", False),
                        cursor=page_info.get("last", "") or "",
                    )

                    logger.info(
                        f"Retrieved {len(objects)} products (Total in category: {meta.total_count}, has_more={meta.has_more})"
                    )
                    return objects, meta
                elif resp.status_code in (403, 429):
                    logger.warning(
                        f"Search API returned {resp.status_code} (attempt {attempt}/3). Backing off for {attempt * 2.0}s..."
                    )
                    time.sleep(attempt * 2.0)
                    self._warmed_up = False
                    self.warm_up()
                else:
                    logger.error(
                        f"Search API returned status {resp.status_code}: {resp.text[:200]}"
                    )
                    break
            except Exception as e:
                logger.error(f"Search request attempt {attempt} failed: {e}")
                time.sleep(attempt * 1.5)

        return [], SearchResponseMeta()

    def fetch_product_html(self, slug_or_url: str) -> str | None:
        """Fetch the HTML of a product page to extract offers and nudge metrics."""
        self.warm_up()
        self._sleep_delay()

        if slug_or_url.startswith("http"):
            url = slug_or_url
        else:
            url = f"{self.config.base_url}/products/{slug_or_url}/"

        logger.debug(f"Fetching product page HTML: {url}")
        for attempt in range(1, 3):
            try:
                resp = self.session.get(
                    url, headers=self.config.html_headers, timeout=15
                )
                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code in (403, 429):
                    logger.warning(
                        f"Product page {url} returned status {resp.status_code} (attempt {attempt}). Retrying..."
                    )
                    time.sleep(attempt * 1.5)
                else:
                    logger.warning(
                        f"Product page {url} returned status {resp.status_code}"
                    )
                    break
            except Exception as e:
                logger.error(f"Failed to fetch product HTML for {url}: {e}")
                time.sleep(1.0)

        return None

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
