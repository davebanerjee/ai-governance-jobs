"""Base scraper class that all scrapers inherit from."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import (
    GOVERNANCE_KEYWORDS,
    MAX_RETRIES,
    REQUEST_DELAY,
    REQUEST_TIMEOUT,
)
from src.models import JobListing

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for all job scrapers."""

    name: str = "base"

    def __init__(self):
        self.session = self._build_session()
        self._last_request_time: float = 0

    @staticmethod
    def _build_session() -> requests.Session:
        """Build a requests session with retry logic."""
        session = requests.Session()
        retry = Retry(
            total=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(
            {
                "User-Agent": "AI-Governance-Job-Scraper/1.0 (weekly job roundup bot)",
                "Accept": "application/json, text/html",
            }
        )
        return session

    def _rate_limited_get(self, url: str, **kwargs) -> requests.Response:
        """GET request with rate limiting between calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        response = self.session.get(url, **kwargs)
        self._last_request_time = time.time()
        response.raise_for_status()
        return response

    @abstractmethod
    def fetch_listings(self) -> list[JobListing]:
        """Fetch all relevant job listings from this source.

        Returns:
            List of JobListing objects.
        """
        ...

    @staticmethod
    def matches_governance_keywords(text: str) -> bool:
        """Check if text matches any governance/AI policy keyword."""
        text_lower = text.lower()
        return any(kw in text_lower for kw in GOVERNANCE_KEYWORDS)

    def filter_governance(
        self, listings: list[JobListing], ai_focused: bool = True
    ) -> list[JobListing]:
        """Filter listings by AI governance keywords.

        Args:
            listings: Raw listings from the source.
            ai_focused: If True, return all listings (org is AI-focused).
                        If False, apply keyword filter.
        """
        if ai_focused:
            return listings

        filtered = []
        for listing in listings:
            searchable = f"{listing.title} {listing.description_snippet}"
            if self.matches_governance_keywords(searchable):
                filtered.append(listing)

        logger.info(
            f"[{self.name}] Keyword filter: {len(filtered)}/{len(listings)} listings matched"
        )
        return filtered

    def scrape(self) -> list[JobListing]:
        """Run the full scrape pipeline: fetch + handle errors.

        Returns:
            List of JobListing objects (may be empty on failure).
        """
        try:
            listings = self.fetch_listings()
            logger.info(f"[{self.name}] Fetched {len(listings)} listings")
            return listings
        except Exception as e:
            logger.error(f"[{self.name}] Scrape failed: {e}")
            return []
