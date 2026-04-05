"""Main orchestrator: scrape → dedup → find new → enrich → store → draft."""

from __future__ import annotations

import logging

from dotenv import load_dotenv
load_dotenv()
import sys
import time
import traceback
from datetime import date
from pathlib import Path

from src.dedup import deduplicate
from src.enrichment import enrich_listings
from src.listing_store import add_new_listings, get_stored_fingerprints
from src.post_generator import generate_post, save_draft
from src.scrapers.ashby import AshbyScraper
from src.scrapers.eighty_k import EightyKHoursScraper
from src.scrapers.greenhouse import GreenhouseScraper
from src.scrapers.lever import LeverScraper
from src.scrapers.llm_scraper import LLMScraper
from src.store import find_new_listings

# ---------------------------------------------------------------------------
# Logging setup — logs to both console and file
# ---------------------------------------------------------------------------

DEFAULT_LOGS_DIR = Path(__file__).parent.parent / "data" / "logs"


def setup_logging(logs_dir: Path = DEFAULT_LOGS_DIR) -> Path:
    """Configure logging to both console and file.

    Returns:
        Path to the log file.
    """
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / f"{date.today().isoformat()}.log"

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture everything

    # Console handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )

    # File handler (DEBUG and above — captures everything)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s\n"
            "    %(pathname)s:%(lineno)d"
        )
    )

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return log_file


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scraper registry
# ---------------------------------------------------------------------------

SCRAPERS = [
    EightyKHoursScraper,
    LeverScraper,
    GreenhouseScraper,
    AshbyScraper,
    LLMScraper,
]


def run(
    store_path: Path | None = None,
    listings_path: Path | None = None,
) -> Path:
    """Run the full scraping pipeline.

    Args:
        store_path: Optional override for the seen listings store path.
        listings_path: Optional override for the persistent listings store path.

    Returns:
        Path to the generated draft file.
    """
    # Set up file logging
    log_file = setup_logging()

    run_start = time.time()
    logger.info("=" * 60)
    logger.info("AI Governance Job Scraper — Starting run")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 60)

    # Step 1: Run all scrapers
    all_listings = []
    failed_sources = []
    scraper_errors: dict[str, str] = {}  # Track error messages for reporting

    for scraper_cls in SCRAPERS:
        scraper = scraper_cls()
        scraper_start = time.time()
        logger.info(f"Running scraper: {scraper.name}")

        try:
            listings = scraper.scrape()
            elapsed = time.time() - scraper_start

            if listings:
                all_listings.extend(listings)
                logger.info(
                    f"[{scraper.name}] Completed: {len(listings)} listings in {elapsed:.1f}s"
                )
            else:
                failed_sources.append(scraper.name)
                scraper_errors[scraper.name] = "No listings returned (may be empty or failed)"
                logger.warning(
                    f"[{scraper.name}] No listings returned after {elapsed:.1f}s"
                )
        except Exception as e:
            elapsed = time.time() - scraper_start
            failed_sources.append(scraper.name)
            error_msg = f"{type(e).__name__}: {str(e)}"
            scraper_errors[scraper.name] = error_msg
            logger.error(
                f"[{scraper.name}] Failed after {elapsed:.1f}s: {error_msg}"
            )
            logger.debug(f"[{scraper.name}] Full traceback:\n{traceback.format_exc()}")

    logger.info(f"Total raw listings: {len(all_listings)}")

    # Step 2: Deduplicate
    unique_listings = deduplicate(all_listings)
    logger.info(f"After dedup: {len(unique_listings)} unique listings")

    # Step 2b: Drop listings with no description text (empty shells from failed LLM extraction)
    non_empty = [l for l in unique_listings if l.description or l.description_snippet]
    if len(non_empty) < len(unique_listings):
        logger.info(
            f"Filtered {len(unique_listings) - len(non_empty)} empty listings "
            f"(no description or snippet), {len(non_empty)} remaining"
        )
    unique_listings = non_empty

    # Step 3: Find new listings (compare against seen store)
    seen_kwargs = {}
    if store_path:
        seen_kwargs["store_path"] = store_path

    new_listings, _ = find_new_listings(unique_listings, **seen_kwargs)
    logger.info(f"New listings this run: {len(new_listings)}")

    # Step 4: Filter out listings already in persistent store
    # (prevents re-surfacing listings marked irrelevant)
    listings_kwargs = {}
    if listings_path:
        listings_kwargs["path"] = listings_path

    stored_fps = get_stored_fingerprints(**listings_kwargs)
    truly_new = [l for l in new_listings if l.fingerprint not in stored_fps]
    if len(truly_new) < len(new_listings):
        logger.info(
            f"Filtered {len(new_listings) - len(truly_new)} already-stored listings, "
            f"{len(truly_new)} truly new"
        )

    # Step 5: Enrich new listings via LLM
    if truly_new:
        truly_new = enrich_listings(truly_new)

    # Step 6: Store enriched listings in persistent store
    if truly_new:
        added = add_new_listings(truly_new, **listings_kwargs)
        logger.info(f"Added {added} listings to persistent store")

    # Step 7: Generate LinkedIn draft (fallback — dashboard is primary now)
    draft_content = generate_post(
        new_listings=truly_new,
        failed_sources=failed_sources if failed_sources else None,
        scraper_errors=scraper_errors if scraper_errors else None,
        log_file=log_file,
    )

    draft_path = save_draft(draft_content)

    # Summary
    run_elapsed = time.time() - run_start
    logger.info("=" * 60)
    logger.info(f"Run complete in {run_elapsed:.1f}s")
    logger.info(f"  Total scraped:  {len(all_listings)}")
    logger.info(f"  After dedup:    {len(unique_listings)}")
    logger.info(f"  New this week:  {len(truly_new)}")
    logger.info(f"  Draft saved to: {draft_path}")
    logger.info(f"  Log file:       {log_file}")
    if failed_sources:
        logger.warning(f"  Failed sources: {', '.join(failed_sources)}")
        for src, err in scraper_errors.items():
            logger.warning(f"    - {src}: {err}")
    logger.info("=" * 60)

    return draft_path


if __name__ == "__main__":
    run()
