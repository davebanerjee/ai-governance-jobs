"""LLM-assisted HTML extraction for custom career pages (Tier 3)."""

from __future__ import annotations

import json
import logging
import os
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.config import (
    LLM_EXTRACTION_PROMPT,
    LLM_MAX_HTML_CHARS,
    LLM_MODEL,
    LLM_SCRAPE_ORGS,
)
from src.models import JobListing
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class LLMScraper(BaseScraper):
    """Scraper that uses an LLM to extract job listings from arbitrary HTML.

    For orgs that don't use a standard ATS platform, we:
    1. Fetch the careers page HTML
    2. Clean it with BeautifulSoup
    3. Send to Claude Haiku for structured extraction
    4. Parse the JSON response into JobListing objects
    """

    name = "llm"

    def __init__(self):
        super().__init__()
        self._client = None

    @property
    def client(self):
        """Lazy-init the Anthropic client."""
        if self._client is None:
            import anthropic
            self._client = anthropic.Anthropic()
        return self._client

    def fetch_listings(self) -> list[JobListing]:
        """Fetch listings from all configured LLM scrape orgs."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            logger.warning(
                f"[{self.name}] ANTHROPIC_API_KEY not set — skipping LLM extraction"
            )
            return []

        all_listings = []

        for org_config in LLM_SCRAPE_ORGS:
            org_name = org_config["name"]
            careers_url = org_config["careers_url"]
            ai_focused = org_config.get("ai_focused", True)

            try:
                listings = self._scrape_org(org_name, careers_url)
                listings = self.filter_governance(listings, ai_focused=ai_focused)
                all_listings.extend(listings)
                logger.info(f"[{self.name}:{org_name}] Found {len(listings)} listings")
            except Exception as e:
                logger.error(f"[{self.name}:{org_name}] Failed: {e}")

        return all_listings

    def _scrape_org(self, org_name: str, careers_url: str) -> list[JobListing]:
        """Scrape a single org's career page using LLM extraction."""
        # Step 1: Fetch HTML
        response = self._rate_limited_get(careers_url)
        html = response.text

        # Step 2: Clean HTML
        cleaned = self._clean_html(html)
        if not cleaned.strip():
            logger.warning(f"[{self.name}:{org_name}] Empty page after cleaning")
            return []

        # Truncate to control costs
        if len(cleaned) > LLM_MAX_HTML_CHARS:
            cleaned = cleaned[:LLM_MAX_HTML_CHARS]
            logger.info(f"[{self.name}:{org_name}] Truncated HTML to {LLM_MAX_HTML_CHARS} chars")

        # Step 3: LLM extraction
        prompt = LLM_EXTRACTION_PROMPT.format(base_url=careers_url)
        extracted = self._llm_extract(cleaned, prompt, org_name)

        # Step 4: Parse into JobListings
        listings = []
        for item in extracted:
            listing = self._parse_extracted(item, org_name, careers_url)
            if listing:
                listings.append(listing)

        return listings

    def _clean_html(self, html: str) -> str:
        """Strip boilerplate from HTML, keeping main content."""
        soup = BeautifulSoup(html, "html.parser")

        # Remove non-content elements
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "noscript", "svg", "iframe"]):
            tag.decompose()

        # Try to find main content area
        main = (
            soup.find("main")
            or soup.find(role="main")
            or soup.find("article")
            or soup.find("div", class_=re.compile(r"content|jobs|careers|listings|opportunities|vacancies", re.I))
            or soup.body
        )

        if main is None:
            main = soup

        # Get simplified HTML (preserve structure for the LLM)
        return str(main)

    def _llm_extract(self, html: str, prompt: str, org_name: str) -> list[dict]:
        """Send HTML to the LLM and parse the JSON response."""
        try:
            message = self.client.messages.create(
                model=LLM_MODEL,
                max_tokens=4096,
                messages=[
                    {
                        "role": "user",
                        "content": f"{prompt}\n\n---\n\n{html}",
                    }
                ],
            )

            response_text = message.content[0].text.strip()

            # Extract JSON from response (handle markdown code blocks)
            if response_text.startswith("```"):
                # Remove markdown code fences
                response_text = re.sub(r"^```(?:json)?\n?", "", response_text)
                response_text = re.sub(r"\n?```$", "", response_text)

            parsed = json.loads(response_text)

            if not isinstance(parsed, list):
                logger.warning(f"[{self.name}:{org_name}] LLM returned non-list: {type(parsed)}")
                return []

            return parsed

        except json.JSONDecodeError as e:
            logger.error(f"[{self.name}:{org_name}] LLM returned invalid JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"[{self.name}:{org_name}] LLM extraction failed: {e}")
            return []

    def _parse_extracted(
        self, item: dict, org_name: str, base_url: str
    ) -> JobListing | None:
        """Parse an LLM-extracted item into a JobListing."""
        try:
            title = item.get("title", "").strip()
            url = item.get("url", "").strip()

            if not title:
                return None

            # Resolve relative URLs
            if url and not url.startswith("http"):
                url = urljoin(base_url, url)
            if not url:
                url = base_url  # Fallback to the careers page itself

            location = item.get("location")
            role_type = item.get("role_type")

            return JobListing(
                title=title,
                organization=org_name,
                url=url,
                location=location,
                role_type=role_type,
                source=f"{self.name}:{org_name.lower().replace(' ', '_')}",
            )
        except Exception as e:
            logger.warning(f"[{self.name}:{org_name}] Failed to parse extracted item: {e}")
            return None
