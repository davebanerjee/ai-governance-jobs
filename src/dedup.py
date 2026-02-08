"""Deduplication logic for job listings."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher

from src.models import JobListing

logger = logging.getLogger(__name__)

FUZZY_THRESHOLD = 0.85


def deduplicate(listings: list[JobListing]) -> list[JobListing]:
    """Remove duplicate listings using exact + fuzzy matching.

    Args:
        listings: All scraped listings (may contain duplicates across sources).

    Returns:
        Deduplicated list. When duplicates are found, the first occurrence is kept.
    """
    seen_fingerprints: dict[str, JobListing] = {}
    seen_signatures: list[tuple[str, JobListing]] = []  # (normalized_sig, listing)
    unique: list[JobListing] = []
    dupes_exact = 0
    dupes_fuzzy = 0

    for listing in listings:
        fp = listing.fingerprint

        # Level 1: Exact fingerprint match
        if fp in seen_fingerprints:
            dupes_exact += 1
            logger.debug(
                f"Exact dupe: '{listing.title}' at {listing.organization} "
                f"(matches {seen_fingerprints[fp].source})"
            )
            continue

        # Level 2: Fuzzy match on org|title
        sig = f"{listing.organization.lower().strip()}|{listing.title.lower().strip()}"
        is_fuzzy_dupe = False
        for existing_sig, existing_listing in seen_signatures:
            ratio = SequenceMatcher(None, sig, existing_sig).ratio()
            if ratio >= FUZZY_THRESHOLD:
                dupes_fuzzy += 1
                logger.debug(
                    f"Fuzzy dupe ({ratio:.2f}): '{listing.title}' at {listing.organization} "
                    f"~ '{existing_listing.title}' at {existing_listing.organization}"
                )
                is_fuzzy_dupe = True
                break

        if is_fuzzy_dupe:
            continue

        # Not a duplicate
        seen_fingerprints[fp] = listing
        seen_signatures.append((sig, listing))
        unique.append(listing)

    logger.info(
        f"Dedup: {len(listings)} → {len(unique)} "
        f"({dupes_exact} exact dupes, {dupes_fuzzy} fuzzy dupes)"
    )
    return unique
