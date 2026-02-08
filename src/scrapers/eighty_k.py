"""Scraper for the 80,000 Hours job board API."""

from __future__ import annotations

import logging
from datetime import date

from src.config import EIGHTY_K_API_BASE, EIGHTY_K_TAGS
from src.models import JobListing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class EightyKHoursScraper(BaseScraper):
    """Scraper using the 80,000 Hours REST API (backend.eawork.org)."""

    name = "80k_hours"

    def fetch_listings(self) -> list[JobListing]:
        """Fetch AI governance listings from the 80K Hours API."""
        all_listings = []

        for tag in EIGHTY_K_TAGS:
            listings = self._fetch_tag(tag)
            all_listings.extend(listings)

        # Apply strict policy role filter
        return self.filter_policy_roles(all_listings)

    def _fetch_tag(self, tag: str) -> list[JobListing]:
        """Fetch listings for a specific tag, handling pagination."""
        listings = []
        url = EIGHTY_K_API_BASE
        params = {
            "format": "json",
            "tags_area": tag,
            "limit": 100,
            "offset": 0,
        }

        while url:
            logger.info(f"[{self.name}] Fetching: {tag} (offset={params.get('offset', 0)})")
            response = self._rate_limited_get(url, params=params)
            data = response.json()

            results = data.get("results", data) if isinstance(data, dict) else data
            if isinstance(data, dict):
                next_url = data.get("next")
            else:
                next_url = None

            if isinstance(results, list):
                for item in results:
                    listing = self._parse_listing(item)
                    if listing:
                        listings.append(listing)

            # Handle pagination
            if next_url:
                url = next_url
                params = {}  # Next URL includes params
            else:
                break

        return listings

    @staticmethod
    def _extract_tag_names(tag_list: list) -> list[str]:
        """Extract name strings from tag objects.

        The API returns tags as dicts like {"pk": 1, "name": "AI safety"}.
        """
        if not tag_list:
            return []
        names = []
        for tag in tag_list:
            if isinstance(tag, dict):
                name = tag.get("name", "")
            else:
                name = str(tag)
            if name:
                names.append(name)
        return names

    def _parse_listing(self, item: dict) -> JobListing | None:
        """Parse a single API result into a JobListing."""
        try:
            title = item.get("title", "").strip()

            # Company name is nested under post.company.name
            post = item.get("post", {}) or {}
            company = post.get("company", {}) or {}
            org = company.get("name", "").strip()

            url = item.get("url_external", "") or item.get("url", "")

            if not title or not url:
                return None

            # Parse location from tags (tags are objects with "name" key)
            locations = self._extract_tag_names(item.get("tags_city", []))
            countries = self._extract_tag_names(item.get("tags_country", []))
            location_parts = locations or countries  # Prefer city-level
            location = ", ".join(location_parts) if location_parts else None

            # Parse location type (remote/hybrid/onsite)
            location_types = self._extract_tag_names(item.get("tags_location_type", []))
            if location_types:
                location_label = ", ".join(location_types)
                if location:
                    location = f"{location} ({location_label})"
                else:
                    location = location_label

            # Parse salary
            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")
            if salary_min and salary_max and (salary_min > 0 or salary_max > 0):
                salary_range = f"${salary_min:,.0f}-${salary_max:,.0f}"
            elif salary_min and salary_min > 0:
                salary_range = f"${salary_min:,.0f}+"
            else:
                salary_range = None

            # Parse role type
            role_types = self._extract_tag_names(item.get("tags_role_type", []))
            role_type = role_types[0] if role_types else None

            # Parse dates
            date_posted = self._parse_date(item.get("posted_at"))
            date_closes = self._parse_date(item.get("closes_at"))

            # Description snippet
            description = item.get("description_short", "") or item.get("description", "")
            # Strip HTML tags for snippet
            import re
            description = re.sub(r"<[^>]+>", " ", description)
            description = re.sub(r"\s+", " ", description).strip()
            snippet = description[:300] if description else ""

            # Collect tags (extract names from tag objects)
            tags = []
            tags.extend(self._extract_tag_names(item.get("tags_area", [])))
            tags.extend(self._extract_tag_names(item.get("tags_skill", [])))

            return JobListing(
                title=title,
                organization=org,
                url=url,
                location=location,
                salary_range=salary_range,
                role_type=role_type,
                description_snippet=snippet,
                date_posted=date_posted,
                date_closes=date_closes,
                source=self.name,
                tags=tags,
            )
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to parse listing: {e}")
            return None

    @staticmethod
    def _parse_date(date_str: str | None) -> date | None:
        """Parse an ISO date string to a date object."""
        if not date_str:
            return None
        try:
            from dateutil.parser import parse as parse_date
            return parse_date(date_str).date()
        except (ValueError, TypeError):
            return None
