"""Scraper for AISafety.com/jobs page."""

from __future__ import annotations

import logging
import re

from bs4 import BeautifulSoup

from src.models import JobListing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

AISAFETY_JOBS_URL = "https://www.aisafety.com/jobs"


class AISafetyComScraper(BaseScraper):
    """Scraper for the AISafety.com jobs listing page.

    This page aggregates AI safety job listings. We scrape the HTML
    and extract job entries. Since this is an AI-focused aggregator,
    all listings are relevant (no keyword filtering needed).
    """

    name = "aisafety_com"

    def fetch_listings(self) -> list[JobListing]:
        """Fetch job listings from aisafety.com/jobs."""
        response = self._rate_limited_get(AISAFETY_JOBS_URL)
        html = response.text
        soup = BeautifulSoup(html, "html.parser")

        listings = []

        # Try to find job listing elements
        # AISafety.com typically uses card-style layouts for job listings
        # We'll look for common patterns: links with job-like text in structured containers

        # Strategy 1: Look for structured job cards/items
        job_containers = soup.find_all(
            ["div", "li", "article", "a"],
            class_=re.compile(r"job|listing|position|opening|card|item", re.I),
        )

        if job_containers:
            for container in job_containers:
                listing = self._parse_container(container)
                if listing:
                    listings.append(listing)

        # Strategy 2: If no structured containers, look for links with org/title patterns
        if not listings:
            links = soup.find_all("a", href=True)
            for link in links:
                text = link.get_text(strip=True)
                href = link.get("href", "")

                # Skip navigation and non-job links
                if not text or len(text) < 10 or len(text) > 200:
                    continue
                if href.startswith("#") or href.startswith("javascript"):
                    continue
                if any(skip in href.lower() for skip in [
                    "/about", "/contact", "/blog", "/news", "/donate",
                    "/login", "/signup", "/privacy", "/terms",
                ]):
                    continue

                # Check if it looks like a job posting link
                if any(kw in text.lower() for kw in [
                    "researcher", "engineer", "analyst", "fellow",
                    "director", "manager", "coordinator", "specialist",
                    "intern", "policy", "governance",
                ]):
                    url = href if href.startswith("http") else f"https://www.aisafety.com{href}"
                    listings.append(
                        JobListing(
                            title=text,
                            organization="(via AISafety.com)",
                            url=url,
                            source=self.name,
                        )
                    )

        logger.info(f"[{self.name}] Extracted {len(listings)} listings from aisafety.com/jobs")
        return listings

    def _parse_container(self, container) -> JobListing | None:
        """Parse a job container element into a JobListing."""
        try:
            # Find the title — usually the first prominent link or heading
            title_el = (
                container.find(["h2", "h3", "h4"])
                or container.find("a")
            )
            if not title_el:
                return None

            title = title_el.get_text(strip=True)
            if not title or len(title) < 5:
                return None

            # Find the URL
            link = container.find("a", href=True)
            url = ""
            if link:
                url = link.get("href", "")
                if url and not url.startswith("http"):
                    url = f"https://www.aisafety.com{url}"

            if not url:
                return None

            # Try to find org name (often in a subtitle or separate element)
            org = "(via AISafety.com)"
            org_el = container.find(
                class_=re.compile(r"org|company|employer", re.I)
            )
            if org_el:
                org = org_el.get_text(strip=True)

            # Try to find location
            location = None
            loc_el = container.find(
                class_=re.compile(r"location|place|city", re.I)
            )
            if loc_el:
                location = loc_el.get_text(strip=True)

            return JobListing(
                title=title,
                organization=org,
                url=url,
                location=location,
                source=self.name,
            )
        except Exception as e:
            logger.warning(f"[{self.name}] Failed to parse container: {e}")
            return None
