"""Generate formatted LinkedIn post drafts from job listings."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from src.models import JobListing

logger = logging.getLogger(__name__)

DEFAULT_DRAFTS_DIR = Path(__file__).parent.parent / "data" / "drafts"

# Category mapping: keywords in title/tags → category
CATEGORY_RULES = [
    ("fellowship", "Fellowships & Internships"),
    ("internship", "Fellowships & Internships"),
    ("intern ", "Fellowships & Internships"),
    ("fellow ", "Fellowships & Internships"),
    ("research", "Research"),
    ("scientist", "Research"),
    ("analyst", "Research"),
    ("engineer", "Research"),
    ("policy", "Policy & Governance"),
    ("governance", "Policy & Governance"),
    ("regulatory", "Policy & Governance"),
    ("government", "Policy & Governance"),
    ("legislative", "Policy & Governance"),
    ("counsel", "Policy & Governance"),
    ("legal", "Policy & Governance"),
    ("advocacy", "Policy & Governance"),
    ("communications", "Operations & Other"),
    ("operations", "Operations & Other"),
    ("program", "Operations & Other"),
    ("manager", "Operations & Other"),
    ("director", "Operations & Other"),
]

CATEGORY_ORDER = [
    "Policy & Governance",
    "Research",
    "Fellowships & Internships",
    "Operations & Other",
]

CATEGORY_ICONS = {
    "Policy & Governance": "\U0001f3db\ufe0f",  # 🏛️
    "Research": "\U0001f52c",  # 🔬
    "Fellowships & Internships": "\U0001f393",  # 🎓
    "Operations & Other": "\U0001f4bc",  # 💼
}


def categorize_listing(listing: JobListing) -> str:
    """Assign a listing to a category based on its title and tags."""
    searchable = f"{listing.title.lower()} {' '.join(listing.tags).lower()}"

    for keyword, category in CATEGORY_RULES:
        if keyword in searchable:
            return category

    return "Operations & Other"


def generate_post(
    new_listings: list[JobListing],
    failed_sources: list[str] | None = None,
    scraper_errors: dict[str, str] | None = None,
    log_file: "Path | None" = None,
    author_name: str = "AI Governance Jobs Bot",
) -> str:
    """Generate a formatted LinkedIn post draft.

    Args:
        new_listings: New listings to include in the post.
        failed_sources: Names of scrapers that failed (for transparency).
        scraper_errors: Dict mapping source name to error message.
        log_file: Path to the log file for this run.
        author_name: Name to credit in the post footer.

    Returns:
        Formatted markdown string for the LinkedIn post.
    """
    today = date.today()
    week_str = today.strftime("%B %d, %Y")

    if not new_listings:
        content = f"# AI Governance Job Roundup \u2014 Week of {week_str}\n\n"
        if failed_sources:
            content += _format_errors_section(failed_sources, scraper_errors, log_file)
        content += "No new roles found this week. Check back next Monday!\n"
        return content

    # Group by category
    categories: dict[str, list[JobListing]] = {cat: [] for cat in CATEGORY_ORDER}
    for listing in new_listings:
        cat = categorize_listing(listing)
        categories[cat].append(listing)

    # Sort within each category by org name
    for cat in categories:
        categories[cat].sort(key=lambda x: x.organization.lower())

    # Build the post
    lines = []
    lines.append(f"\U0001f50d AI Governance Job Roundup \u2014 Week of {week_str}\n")

    # ERRORS AT TOP — so they're immediately visible
    if failed_sources:
        lines.append(_format_errors_section(failed_sources, scraper_errors, log_file))

    lines.append(
        f"{len(new_listings)} new role{'s' if len(new_listings) != 1 else ''} "
        "this week in AI governance, policy, and safety:\n"
    )

    for cat in CATEGORY_ORDER:
        cat_listings = categories[cat]
        if not cat_listings:
            continue

        icon = CATEGORY_ICONS[cat]
        lines.append(f"{icon} {cat.upper()}")

        for listing in cat_listings:
            loc = f" ({listing.location})" if listing.location else ""
            salary = f" | {listing.salary_range}" if listing.salary_range else ""
            closing = ""
            if listing.date_closes:
                closing = f" | Closes {listing.date_closes.strftime('%b %d')}"

            lines.append(f"\u2022 {listing.title} \u2014 {listing.organization}{loc}{salary}{closing}")
            lines.append(f"  {listing.url}")

        lines.append("")

    # Footer
    lines.append("---")

    source_count = len(set(l.source for l in new_listings))
    lines.append(f"Sources: 80,000 Hours, AISafety.com, + {source_count} org career pages")
    lines.append(f"Compiled automatically, curated by {author_name}")

    lines.append("\n#AIGovernance #AIPolicy #AISafety #TechPolicy #Careers")

    return "\n".join(lines)


def _format_errors_section(
    failed_sources: list[str],
    scraper_errors: dict[str, str] | None = None,
    log_file: "Path | None" = None,
) -> str:
    """Format the errors section for the draft.

    Args:
        failed_sources: Names of scrapers that failed.
        scraper_errors: Dict mapping source name to error message.
        log_file: Path to the log file for this run.

    Returns:
        Formatted markdown section for errors.
    """
    lines = ["\u26a0\ufe0f **SCRAPER ISSUES** \u2014 Some sources could not be reached:\n"]

    for source in failed_sources:
        error_msg = ""
        if scraper_errors and source in scraper_errors:
            error_msg = f": {scraper_errors[source]}"
        lines.append(f"  \u2022 {source}{error_msg}")

    if log_file:
        lines.append(f"\n  See full details in: `{log_file}`")

    lines.append("\n")
    return "\n".join(lines)


def save_draft(
    content: str,
    drafts_dir: Path = DEFAULT_DRAFTS_DIR,
) -> Path:
    """Save the post draft to a file.

    Returns:
        Path to the saved draft file.
    """
    drafts_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    filepath = drafts_dir / f"{today}.md"
    filepath.write_text(content, encoding="utf-8")
    logger.info(f"Draft saved to {filepath}")
    return filepath
