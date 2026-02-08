"""Main orchestrator: scrape → deduplicate → generate LinkedIn draft."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.dedup import deduplicate
from src.post_generator import generate_post, save_draft
from src.scrapers.aisafety_com import AISafetyComScraper
from src.scrapers.ashby import AshbyScraper
from src.scrapers.eighty_k import EightyKHoursScraper
from src.scrapers.greenhouse import GreenhouseScraper
from src.scrapers.lever import LeverScraper
from src.scrapers.llm_scraper import LLMScraper
from src.store import find_new_listings

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scraper registry
# ---------------------------------------------------------------------------

SCRAPERS = [
    EightyKHoursScraper,
    LeverScraper,
    GreenhouseScraper,
    AshbyScraper,
    AISafetyComScraper,
    LLMScraper,
]


def run(store_path: Path | None = None) -> Path:
    """Run the full scraping pipeline.

    Args:
        store_path: Optional override for the seen listings store path.

    Returns:
        Path to the generated draft file.
    """
    logger.info("=" * 60)
    logger.info("AI Governance Job Scraper — Starting run")
    logger.info("=" * 60)

    # Step 1: Run all scrapers
    all_listings = []
    failed_sources = []

    for scraper_cls in SCRAPERS:
        scraper = scraper_cls()
        logger.info(f"Running scraper: {scraper.name}")
        listings = scraper.scrape()

        if listings:
            all_listings.extend(listings)
        else:
            failed_sources.append(scraper.name)

    logger.info(f"Total raw listings: {len(all_listings)}")

    # Step 2: Deduplicate
    unique_listings = deduplicate(all_listings)
    logger.info(f"After dedup: {len(unique_listings)} unique listings")

    # Step 3: Find new listings (compare against seen store)
    kwargs = {}
    if store_path:
        kwargs["store_path"] = store_path

    new_listings, _ = find_new_listings(unique_listings, **kwargs)
    logger.info(f"New listings this run: {len(new_listings)}")

    # Step 4: Generate LinkedIn draft
    draft_content = generate_post(
        new_listings=new_listings,
        failed_sources=failed_sources if failed_sources else None,
    )

    draft_path = save_draft(draft_content)

    # Summary
    logger.info("=" * 60)
    logger.info(f"Run complete!")
    logger.info(f"  Total scraped:  {len(all_listings)}")
    logger.info(f"  After dedup:    {len(unique_listings)}")
    logger.info(f"  New this week:  {len(new_listings)}")
    logger.info(f"  Draft saved to: {draft_path}")
    if failed_sources:
        logger.warning(f"  Failed sources: {', '.join(failed_sources)}")
    logger.info("=" * 60)

    return draft_path


if __name__ == "__main__":
    run()
