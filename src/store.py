"""State management — track previously seen listings across runs."""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

from src.config import SEEN_EXPIRY_WEEKS
from src.models import JobListing

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path(__file__).parent.parent / "data" / "seen_listings.json"


def load_seen(path: Path = DEFAULT_STORE_PATH) -> dict:
    """Load the seen listings store from disk.

    Returns:
        Dict with 'last_run' and 'seen' keys.
    """
    if not path.exists():
        return {"last_run": None, "seen": {}}

    with open(path, "r") as f:
        data = json.load(f)

    return data


def save_seen(data: dict, path: Path = DEFAULT_STORE_PATH) -> None:
    """Save the seen listings store to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Saved {len(data.get('seen', {}))} seen listings to {path}")


def find_new_listings(
    listings: list[JobListing],
    store_path: Path = DEFAULT_STORE_PATH,
) -> tuple[list[JobListing], list[JobListing]]:
    """Compare listings against the seen store to find new ones.

    Args:
        listings: Deduplicated listings from the current scrape.
        store_path: Path to the seen listings JSON file.

    Returns:
        Tuple of (new_listings, all_listings).
        new_listings: Listings not previously seen.
        all_listings: All current listings (for updating the store).
    """
    store = load_seen(store_path)
    seen = store.get("seen", {})
    today = date.today()

    new_listings = []
    for listing in listings:
        fp = listing.fingerprint
        if fp not in seen:
            new_listings.append(listing)

    logger.info(
        f"Found {len(new_listings)} new listings "
        f"(out of {len(listings)} total, {len(seen)} previously seen)"
    )

    # Update the store
    updated_seen = {}

    # Keep all current listings
    for listing in listings:
        fp = listing.fingerprint
        if fp in seen:
            # Update last_seen
            entry = seen[fp]
            entry["last_seen"] = today.isoformat()
            updated_seen[fp] = entry
        else:
            # New entry
            updated_seen[fp] = {
                "title": listing.title,
                "org": listing.organization,
                "first_seen": today.isoformat(),
                "last_seen": today.isoformat(),
            }

    # Keep old entries that haven't expired yet
    expiry_cutoff = today - timedelta(weeks=SEEN_EXPIRY_WEEKS)
    for fp, entry in seen.items():
        if fp not in updated_seen:
            last_seen = date.fromisoformat(entry["last_seen"])
            if last_seen >= expiry_cutoff:
                updated_seen[fp] = entry
            else:
                logger.debug(f"Pruning expired listing: {entry.get('title')} at {entry.get('org')}")

    updated_store = {
        "last_run": today.isoformat(),
        "seen": updated_seen,
    }
    save_seen(updated_store, store_path)

    return new_listings, listings
