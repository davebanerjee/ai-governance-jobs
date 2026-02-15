"""LLM-based enrichment to extract work_mode, visa_sponsorship, and seniority_level."""

from __future__ import annotations

import json
import logging
import os
import re

from src.config import LLM_MODEL
from src.models import JobListing

logger = logging.getLogger(__name__)

ENRICHMENT_DESCRIPTION_MAX_CHARS = 3000

VALID_WORK_MODES = {
    "Remote (Global)", "Remote (US)", "Remote (EU)", "Hybrid", "In-Person",
}
VALID_SENIORITY_LEVELS = {"Entry", "Mid", "Senior", "All Levels"}

ENRICHMENT_PROMPT = """Analyze this job listing and extract the following fields. Return ONLY valid JSON, no other text.

Job Title: {title}
Organization: {organization}
Location: {location}
Description:
{description}

Return a JSON object with exactly these keys:
- "work_mode": one of "Remote (Global)", "Remote (US)", "Remote (EU)", "Hybrid", "In-Person", or null if unclear
- "visa_sponsorship": true, false, or null if not mentioned
- "seniority_level": one of "Entry", "Mid", "Senior", "All Levels", or null if unclear

Rules:
- "Entry" = internship, fellowship, junior, entry-level, 0-2 years experience
- "Mid" = mid-level, 3-7 years experience
- "Senior" = senior, lead, director, head, principal, 8+ years experience
- "All Levels" = explicitly states open to multiple levels
- For work_mode, if it says "remote" without geographic restriction, use "Remote (Global)"
- For visa_sponsorship, only set true/false if explicitly mentioned"""


def enrich_listings(listings: list[JobListing]) -> list[JobListing]:
    """Enrich listings with work_mode, visa_sponsorship, and seniority_level.

    Calls Claude Haiku for each listing that has description text.
    If ANTHROPIC_API_KEY is not set, returns listings unchanged.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping enrichment")
        return listings

    import anthropic
    client = anthropic.Anthropic()

    enriched = []
    success_count = 0

    for listing in listings:
        try:
            result = _enrich_single(client, listing)
            enriched.append(result)
            if result.work_mode or result.seniority_level or result.visa_sponsorship is not None:
                success_count += 1
        except Exception as e:
            logger.warning(f"Enrichment failed for {listing.title} at {listing.organization}: {e}")
            enriched.append(listing)

    logger.info(f"Enriched {success_count}/{len(listings)} listings with metadata")
    return enriched


def _enrich_single(client, listing: JobListing) -> JobListing:
    """Enrich a single listing via LLM."""
    text = listing.description or listing.description_snippet
    if not text:
        return listing

    text = text[:ENRICHMENT_DESCRIPTION_MAX_CHARS]

    prompt = ENRICHMENT_PROMPT.format(
        title=listing.title,
        organization=listing.organization,
        location=listing.location or "Not specified",
        description=text,
    )

    message = client.messages.create(
        model=LLM_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Strip code fences if present
    if response_text.startswith("```"):
        response_text = re.sub(r"^```(?:json)?\n?", "", response_text)
        response_text = re.sub(r"\n?```$", "", response_text)

    data = json.loads(response_text)

    # Validate and apply
    work_mode = data.get("work_mode")
    if work_mode not in VALID_WORK_MODES:
        work_mode = None

    seniority = data.get("seniority_level")
    if seniority not in VALID_SENIORITY_LEVELS:
        seniority = None

    visa = data.get("visa_sponsorship")
    if visa is not None and not isinstance(visa, bool):
        visa = None

    listing.work_mode = work_mode
    listing.visa_sponsorship = visa
    listing.seniority_level = seniority

    return listing
