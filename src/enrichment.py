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
- "impact_score": integer 1-10 rating of this role's potential impact on reducing existential/catastrophic risk (see rubric below)
- "impact_reason": a single sentence (max 20 words) explaining the impact score

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
- If the role description is too vague or the focus is unclear, use null for both relevance fields

Impact score rubric (focus on reducing existential/catastrophic risk from AI or bioweapons):
- 9-10: Core x-risk role at an org whose primary mission is reducing existential risk (e.g., IAPS, ARC, MIRI, Secure Bio, AISI, Anthropic alignment/policy, GovAI, FLI, CSER)
- 7-8: Strong x-risk relevance at a frontier AI lab or major x-risk-adjacent org (OpenAI safety/policy, DeepMind safety, CSET, biosecurity-focused roles)
- 5-6: AI governance/policy with meaningful but not primary x-risk component (congressional AI policy, Brookings AI security, major think tanks with AI safety programs)
- 3-4: General AI ethics or tech policy with some safety relevance but no clear x-risk focus
- 1-2: Tangential — broad tech/data policy that mentions AI without safety focus, or compliance roles"""

IMPACT_SCORE_PROMPT = """Rate this job listing's potential impact on reducing existential and catastrophic risks (from AI or bioweapons). Return ONLY valid JSON, no other text.

Job Title: {title}
Organization: {organization}
Description:
{description}

Return a JSON object with exactly these keys:
- "impact_score": integer 1-10
- "impact_reason": a single sentence (max 20 words) explaining the score

Scoring rubric:
- 9-10: Core x-risk role at an org whose primary mission is reducing existential risk (IAPS, ARC, MIRI, Secure Bio, AISI, Anthropic alignment/policy, GovAI, FLI, CSER, Apollo Research)
- 7-8: Strong x-risk relevance at a frontier AI lab or major x-risk-adjacent org (OpenAI safety/policy, DeepMind safety, CSET, biosecurity-focused roles)
- 5-6: AI governance/policy with meaningful but not primary x-risk component (congressional AI policy, major think tanks with AI safety programs)
- 3-4: General AI ethics or tech policy with some safety relevance but no clear x-risk focus
- 1-2: Tangential — broad tech/data policy that mentions AI without safety focus"""


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

    impact_score = data.get("impact_score")
    if not isinstance(impact_score, int) or not (1 <= impact_score <= 10):
        impact_score = None

    impact_reason = data.get("impact_reason")
    if impact_score is None:
        impact_reason = None
    elif impact_reason is not None and not isinstance(impact_reason, str):
        impact_reason = None
    if impact_reason and len(impact_reason) > 150:
        impact_reason = impact_reason[:147] + "..."

    listing.work_mode = work_mode
    listing.visa_sponsorship = visa
    listing.seniority_level = seniority
    listing.relevance_tag = relevance_tag
    listing.relevance_reason = relevance_reason
    listing.impact_score = impact_score
    listing.impact_reason = impact_reason

    return listing


def score_single_listing(listing: JobListing) -> tuple[int | None, str | None]:
    """Score a single listing's x-risk impact potential via LLM.

    Returns (impact_score, impact_reason), or (None, None) if scoring fails
    or ANTHROPIC_API_KEY is not set.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None, None

    import anthropic
    client = anthropic.Anthropic()

    text = listing.description or listing.description_snippet
    if not text:
        text = "(no description available)"
    text = text[:ENRICHMENT_DESCRIPTION_MAX_CHARS]

    prompt = IMPACT_SCORE_PROMPT.format(
        title=listing.title,
        organization=listing.organization,
        description=text,
    )

    try:
        message = client.messages.create(
            model=LLM_MODEL,
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\n?", "", response_text)
            response_text = re.sub(r"\n?```$", "", response_text)

        data = json.loads(response_text)
        score = data.get("impact_score")
        reason = data.get("impact_reason")

        if not isinstance(score, int) or not (1 <= score <= 10):
            return None, None
        if reason and len(reason) > 150:
            reason = reason[:147] + "..."

        return score, reason if isinstance(reason, str) else None
    except Exception as e:
        logger.warning(f"Impact scoring failed for {listing.title}: {e}")
        return None, None
