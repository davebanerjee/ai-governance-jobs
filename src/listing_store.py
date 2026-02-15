"""Persistent listing storage with review status tracking."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from src.models import JobListing

logger = logging.getLogger(__name__)

DEFAULT_LISTINGS_PATH = Path(__file__).parent.parent / "data" / "listings.json"


def load_listings(path: Path = DEFAULT_LISTINGS_PATH) -> dict:
    """Load the listings store from disk.

    Returns:
        Dict keyed by fingerprint, each value has 'listing', 'review_status',
        'reviewed_at', and 'added_at'.
    """
    if not path.exists():
        return {}

    with open(path, "r") as f:
        return json.load(f)


def save_listings(data: dict, path: Path = DEFAULT_LISTINGS_PATH) -> None:
    """Save the listings store to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logger.info(f"Saved {len(data)} listings to {path}")


def add_new_listings(
    listings: list[JobListing],
    path: Path = DEFAULT_LISTINGS_PATH,
) -> int:
    """Add listings that aren't already in the store.

    Returns:
        Number of listings actually added.
    """
    store = load_listings(path)
    added = 0
    today = date.today().isoformat()

    for listing in listings:
        fp = listing.fingerprint
        if fp not in store:
            store[fp] = {
                "listing": listing.to_dict(),
                "review_status": "unreviewed",
                "reviewed_at": None,
                "added_at": today,
            }
            added += 1

    if added:
        save_listings(store, path)
        logger.info(f"Added {added} new listings to store")

    return added


def update_review_status(
    fingerprint: str,
    status: str,
    path: Path = DEFAULT_LISTINGS_PATH,
) -> None:
    """Update the review status of a listing."""
    store = load_listings(path)
    if fingerprint in store:
        store[fingerprint]["review_status"] = status
        store[fingerprint]["reviewed_at"] = date.today().isoformat()
        save_listings(store, path)


def get_listings_by_status(
    status: str,
    path: Path = DEFAULT_LISTINGS_PATH,
) -> list[dict]:
    """Get all listing entries matching a review status.

    Returns:
        List of store entries (each has 'listing', 'review_status', etc.).
    """
    store = load_listings(path)
    return [
        entry for entry in store.values()
        if entry["review_status"] == status
    ]


def get_stored_fingerprints(path: Path = DEFAULT_LISTINGS_PATH) -> set[str]:
    """Get the set of all fingerprints currently in the store."""
    store = load_listings(path)
    return set(store.keys())
