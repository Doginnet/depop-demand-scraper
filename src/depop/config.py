from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    base_url: str = "https://www.depop.com"
    search_api_url: str = "https://www.depop.com/presentation/api/v1/search/products/"
    impersonate_target: str = "chrome124"

    headers: dict = field(
        default_factory=lambda: {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "origin": "https://www.depop.com",
            "referer": "https://www.depop.com/",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
        }
    )

    # Scraper thresholds & defaults
    default_limit: int = 160
    default_min_likes: int = 5
    default_top_n: int = 20

    # Weights for demand scoring (offers are primary indicator)
    weight_offers: float = 5.0
    weight_in_bags: float = 3.0
    weight_likes: float = 1.0

    # Rate limiting delays (in seconds)
    min_delay: float = 0.6
    max_delay: float = 1.4

    # Output paths
    output_dir: Path = Path("output")
    db_path: Path = Path("output/depop.db")
    raw_dir: Path = Path("raw")


default_config = Config()
