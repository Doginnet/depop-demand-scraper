import argparse
import sys
from pathlib import Path
from loguru import logger

from depop.config import Config
from depop.scraper import DepopScraper


def setup_logger(verbose: bool = False):
    """Configure Loguru logger formatting."""
    logger.remove()
    log_level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level=log_level,
    )
    logger.add(
        "logs/depop_scraper_{time:YYYY-MM-DD}.log",
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        encoding="utf-8",
    )


def print_summary_table(products):
    """Display a concise summary table in terminal."""
    if not products:
        print("\nNo products found matching criteria.")
        return

    # Ensure stdout handles non-ASCII characters on Windows consoles
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("\n" + "=" * 105)
    print(
        f"{'#':<3} | {'SCORE':<6} | {'OFFERS':<6} | {'BAGS':<4} | {'LIKES':<5} | {'PRICE':<8} | {'TITLE':<45} | {'URL'}"
    )
    print("-" * 105)
    for i, p in enumerate(products, 1):
        clean_title = p.title.replace("\n", " ").strip()
        title = (clean_title[:42] + "...") if len(clean_title) > 45 else clean_title
        try:
            print(
                f"{i:<3} | {p.demand_score:<6.1f} | {p.offers_count:<6} | {p.in_bags_count:<4} | {p.like_count:<5} | {f'{p.price:.2f} {p.currency}':<8} | {title:<45} | {p.url}"
            )
        except UnicodeEncodeError:
            safe_title = title.encode("ascii", errors="replace").decode("ascii")
            print(
                f"{i:<3} | {p.demand_score:<6.1f} | {p.offers_count:<6} | {p.in_bags_count:<4} | {p.like_count:<5} | {f'{p.price:.2f} {p.currency}':<8} | {safe_title:<45} | {p.url}"
            )
    print("=" * 105 + "\n")


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(
        description="Depop Scraper for dropshipping demand analysis (Likes, Offers, In-bag counts)."
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="baggy jeans",
        help="Search query to scrape (default: 'baggy jeans')",
    )
    parser.add_argument(
        "--test",
        "-t",
        action="store_true",
        help="Test mode: collects and enriches only the first 16 items for quick analysis.",
    )
    parser.add_argument(
        "--min-likes",
        "-l",
        type=int,
        default=5,
        help="Minimum likes threshold to qualify for HTML offer enrichment (default: 5).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top items to export (default: 20).",
    )
    parser.add_argument(
        "--pages",
        "-p",
        type=int,
        default=None,
        help="Maximum search pages to paginate through (default: dynamic based on --top).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable detailed debug logging.",
    )

    args = parser.parse_args()

    setup_logger(verbose=args.verbose)

    config = Config()
    scraper = DepopScraper(config=config)

    top_items = scraper.run(
        query=args.query,
        min_likes=args.min_likes,
        top_n=args.top,
        max_pages=args.pages,
        test_mode=args.test,
    )

    print_summary_table(top_items)


if __name__ == "__main__":
    main()
