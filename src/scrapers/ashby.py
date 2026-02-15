"""Generic scraper for organizations using Ashby ATS."""

from __future__ import annotations

import logging
from datetime import date

from src.config import ASHBY_ORGS
from src.models import JobListing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

ASHBY_API_BASE = "https://api.ashbyhq.com/posting-api/job-board"


class AshbyScraper(BaseScraper):
    """Scraper for all orgs using Ashby ATS.

    Ashby provides a public JSON API at:
    https://api.ashbyhq.com/posting-api/job-board/{company}
    """

    name = "ashby"

    def fetch_listings(self) -> list[JobListing]:
        """Fetch listings from all configured Ashby orgs."""
        all_listings = []

        for org_config in ASHBY_ORGS:
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
        """Fetch all listings for a single Ashby org."""
        url = f"{ASHBY_API_BASE}/{slug}"
        response = self._rate_limited_get(url)
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
        """Parse an Ashby job into a JobListing."""
        try:
            title = item.get("title", "").strip()

            # Ashby uses either publishedUrl or a constructed URL
            job_id = item.get("id", "")
            url = item.get("publishedUrl", "") or item.get("jobUrl", "")
            if not url and job_id:
                url = f"https://jobs.ashbyhq.com/{slug}/{job_id}"

            if not title or not url:
                return None

            # Location
            location = item.get("location", None)
            if isinstance(location, dict):
                location = location.get("name")

            employment_type = item.get("employmentType", None)

            # Description
            full_description = item.get("descriptionPlain", "") or item.get("description", "")
            if full_description:
                import re
                full_description = re.sub(r"<[^>]+>", " ", full_description)
                full_description = re.sub(r"\s+", " ", full_description).strip()
            snippet = full_description[:300] if full_description else ""

            # Department/team as tags
            tags = []
            department = item.get("department", "")
            team = item.get("team", "")
            if isinstance(department, dict):
                department = department.get("name", "")
            if isinstance(team, dict):
                team = team.get("name", "")
            if department:
                tags.append(department)
            if team:
                tags.append(team)

            # Date
            published_at = item.get("publishedAt") or item.get("createdAt")
            date_posted = None
            if published_at:
                from dateutil.parser import parse as parse_date
                date_posted = parse_date(published_at).date()

            return JobListing(
                title=title,
                organization=org_name,
                url=url,
                location=location,
                role_type=employment_type,
                description_snippet=snippet,
                description=full_description or "",
                date_posted=date_posted,
                source=f"{self.name}:{slug}",
                tags=tags,
            )
        except Exception as e:
            logger.warning(f"[{self.name}:{slug}] Failed to parse: {e}")
            return None
