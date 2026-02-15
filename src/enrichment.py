"""LLM-based enrichment to extract structured metadata from job listings."""

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
VALID_RELEVANCE_TAGS = {
    "AGI Safety & Governance",
    "AI Safety (Technical)",
    "Biosecurity/Catastrophic Risk",
    "AI Ethics/Responsible AI",
    "General Tech Policy",
}

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
- "relevance_tag": one of "AGI Safety & Governance", "AI Safety (Technical)", "Biosecurity/Catastrophic Risk", "AI Ethics/Responsible AI", "General Tech Policy", or null if unclear
- "relevance_reason": a single sentence (max 20 words) explaining why this tag was chosen, or null if relevance_tag is null

Rules for seniority:
- "Entry" = internship, fellowship, junior, entry-level, 0-2 years experience
- "Mid" = mid-level, 3-7 years experience
- "Senior" = senior, lead, director, head, principal, 8+ years experience
- "All Levels" = explicitly states open to multiple levels

Rules for work_mode:
- If it says "remote" without geographic restriction, use "Remote (Global)"
- For visa_sponsorship, only set true/false if explicitly mentioned

Rules for relevance classification:
- "AGI Safety & Governance": Roles directly addressing catastrophic/existential AI risks, AI alignment policy, frontier AI regulation, AI control/monitoring, governance of advanced AI systems, extreme power concentration due to AI, gradual disempowerment, suffering risks, AGI treaty/coordination work
- "AI Safety (Technical)": Technical alignment research, interpretability, mechanistic interpretability, red-teaming, evaluations (evals), AI safety engineering, scalable oversight
- "Biosecurity/Catastrophic Risk": Biological weapons, pandemic prevention, WMD policy, dual-use research governance, other existential risks (not AI-specific)
- "AI Ethics/Responsible AI": Fairness, bias, accountability, transparency, algorithmic justice, AI and society (without focus on catastrophic/existential risks from advanced AI)
- "General Tech Policy": Broader tech policy, privacy, data protection, antitrust, general innovation policy (may mention AI but not safety-focused)
- If the role description is too vague or the focus is unclear, use null for both relevance fields"""


def enrich_listings(listings: list[JobListing]) -> list[JobListing]:
    """Enrich listings with metadata extracted via LLM.

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
            if result.work_mode or result.seniority_level or result.visa_sponsorship is not None or result.relevance_tag:
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
        max_tokens=512,
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

    relevance_tag = data.get("relevance_tag")
    if relevance_tag not in VALID_RELEVANCE_TAGS:
        relevance_tag = None

    relevance_reason = data.get("relevance_reason")
    if relevance_tag is None:
        relevance_reason = None
    elif relevance_reason is not None and not isinstance(relevance_reason, str):
        relevance_reason = None
    if relevance_reason and len(relevance_reason) > 150:
        relevance_reason = relevance_reason[:147] + "..."

    listing.work_mode = work_mode
    listing.visa_sponsorship = visa
    listing.seniority_level = seniority
    listing.relevance_tag = relevance_tag
    listing.relevance_reason = relevance_reason

    return listing
