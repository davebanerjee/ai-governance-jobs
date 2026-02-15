"""Generic scraper for organizations using Greenhouse ATS."""

from __future__ import annotations

import logging
from datetime import date

from src.config import GREENHOUSE_ORGS
from src.models import JobListing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

GREENHOUSE_API_BASE = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseScraper(BaseScraper):
    """Scraper for all orgs using Greenhouse ATS.

    Greenhouse provides a public JSON API at:
    https://boards-api.greenhouse.io/v1/boards/{company}/jobs
    """

    name = "greenhouse"

    def fetch_listings(self) -> list[JobListing]:
        """Fetch listings from all configured Greenhouse orgs."""
        all_listings = []

        for org_config in GREENHOUSE_ORGS:
            org_name = org_config["name"]
            slug = org_config["slug"]
            ai_focused = org_config.get("ai_focused", True)

            try:
                listings = self._fetch_org(org_name, slug)
                # Apply strict policy role filter to ALL listings
                listings = self.filter_policy_roles(listings)
                all_listings.extend(listings)
                logger.info(f"[{self.name}:{slug}] Found {len(listings)} policy roles")
            except Exception as e:
                logger.error(f"[{self.name}:{slug}] Failed: {e}")

        return all_listings

    def _fetch_org(self, org_name: str, slug: str) -> list[JobListing]:
        """Fetch all listings for a single Greenhouse org."""
        url = f"{GREENHOUSE_API_BASE}/{slug}/jobs"
        params = {"content": "true"}  # Include job description
        response = self._rate_limited_get(url, params=params)
        data = response.json()

        jobs = data.get("jobs", [])
        if not isinstance(jobs, list):
            logger.warning(f"[{self.name}:{slug}] Unexpected response format")
            return []

        listings = []
        for item in jobs:
            listing = self._parse_listing(item, org_name, slug)
            if listing:
                listings.append(listing)

        return listings

    def _parse_listing(
        self, item: dict, org_name: str, slug: str
    ) -> JobListing | None:
        """Parse a Greenhouse job into a JobListing."""
        try:
            title = item.get("title", "").strip()
            url = item.get("absolute_url", "")

            if not title or not url:
                return None

            # Location
            location_obj = item.get("location", {})
            location = location_obj.get("name") if location_obj else None

            # Description
            content = item.get("content", "")
            # Strip HTML
            import re
            plain = re.sub(r"<[^>]+>", " ", content)
            plain = re.sub(r"\s+", " ", plain).strip()
            snippet = plain[:300] if plain else ""

            # Departments as tags
            tags = []
            departments = item.get("departments", [])
            for dept in departments:
                name = dept.get("name", "")
                if name:
                    tags.append(name)

            # Date
            updated_at = item.get("updated_at")
            date_posted = None
            if updated_at:
                from dateutil.parser import parse as parse_date
                date_posted = parse_date(updated_at).date()

            return JobListing(
                title=title,
                organization=org_name,
                url=url,
                location=location,
                description_snippet=snippet,
                description=plain or "",
                date_posted=date_posted,
                source=f"{self.name}:{slug}",
                tags=tags,
            )
        except Exception as e:
            logger.warning(f"[{self.name}:{slug}] Failed to parse: {e}")
            return None
