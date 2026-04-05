"""Generic scraper for organizations using Lever ATS."""

from __future__ import annotations

import logging
from datetime import date

from src.config import LEVER_ORGS
from src.models import JobListing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

LEVER_API_BASE = "https://api.lever.co/v0/postings"


class LeverScraper(BaseScraper):
    """Scraper for all orgs using Lever ATS.

    Lever provides a public JSON API at:
    https://api.lever.co/v0/postings/{company}?mode=json
    """

    name = "lever"

    def fetch_listings(self) -> list[JobListing]:
        """Fetch listings from all configured Lever orgs."""
        all_listings = []

        for org_config in LEVER_ORGS:
            org_name = org_config["name"]
            slug = org_config["slug"]

            try:
                ai_focused = org_config.get("ai_focused", False)
                listings = self._fetch_org(org_name, slug)
                listings = self.filter_policy_roles(listings, ai_focused=ai_focused)
                all_listings.extend(listings)
                logger.info(f"[{self.name}:{slug}] Found {len(listings)} policy roles")
            except Exception as e:
                logger.error(f"[{self.name}:{slug}] Failed: {e}")

        return all_listings

    def _fetch_org(self, org_name: str, slug: str) -> list[JobListing]:
        """Fetch all listings for a single Lever org."""
        url = f"{LEVER_API_BASE}/{slug}?mode=json"
        response = self._rate_limited_get(url)
        data = response.json()

        if not isinstance(data, list):
            logger.warning(f"[{self.name}:{slug}] Unexpected response format")
            return []

        listings = []
        for item in data:
            listing = self._parse_listing(item, org_name, slug)
            if listing:
                listings.append(listing)

        return listings

    def _parse_listing(
        self, item: dict, org_name: str, slug: str
    ) -> JobListing | None:
        """Parse a Lever posting into a JobListing."""
        try:
            title = item.get("text", "").strip()
            url = item.get("hostedUrl", "") or item.get("applyUrl", "")

            if not title or not url:
                return None

            # Location
            categories = item.get("categories", {})
            location = categories.get("location", None)
            commitment = categories.get("commitment", None)  # Full-time, Part-time, etc.

            # Description
            desc_plain = item.get("descriptionPlain", "")
            snippet = desc_plain[:300].strip() if desc_plain else ""

            # Tags from categories
            tags = []
            team = categories.get("team", "")
            department = categories.get("department", "")
            if team:
                tags.append(team)
            if department:
                tags.append(department)

            # Parse created date
            created_at = item.get("createdAt")
            date_posted = None
            if created_at:
                # Lever uses millisecond timestamps
                from datetime import datetime
                date_posted = datetime.fromtimestamp(created_at / 1000).date()

            return JobListing(
                title=title,
                organization=org_name,
                url=url,
                location=location,
                role_type=commitment,
                description_snippet=snippet,
                description=desc_plain or "",
                date_posted=date_posted,
                source=f"{self.name}:{slug}",
                tags=tags,
            )
        except Exception as e:
            logger.warning(f"[{self.name}:{slug}] Failed to parse: {e}")
            return None
