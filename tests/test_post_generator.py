"""Tests for the LinkedIn post generator."""

from datetime import date

from src.models import JobListing
from src.post_generator import categorize_listing, generate_post


def _make_listing(**kwargs) -> JobListing:
    defaults = {
        "title": "Test Job",
        "organization": "TestOrg",
        "url": "https://example.com/job",
        "source": "test",
    }
    defaults.update(kwargs)
    return JobListing(**defaults)


def test_categorize_policy():
    listing = _make_listing(title="AI Policy Director")
    assert categorize_listing(listing) == "Policy & Governance"


def test_categorize_research():
    listing = _make_listing(title="Senior Research Scientist")
    assert categorize_listing(listing) == "Research"


def test_categorize_fellowship():
    listing = _make_listing(title="AI Safety Fellowship")
    assert categorize_listing(listing) == "Fellowships & Internships"


def test_categorize_internship():
    listing = _make_listing(title="Summer Internship - AI Governance")
    assert categorize_listing(listing) == "Fellowships & Internships"


def test_categorize_default():
    listing = _make_listing(title="Executive Assistant")
    assert categorize_listing(listing) == "Operations & Other"


def test_generate_post_with_listings():
    listings = [
        _make_listing(
            title="AI Policy Researcher",
            organization="GovAI",
            location="Oxford, UK",
            url="https://governance.ai/jobs/1",
        ),
        _make_listing(
            title="ML Research Engineer",
            organization="Anthropic",
            location="San Francisco, CA",
            url="https://anthropic.com/jobs/1",
        ),
        _make_listing(
            title="AI Safety Fellowship",
            organization="CAIS",
            url="https://safe.ai/fellowship",
        ),
    ]

    post = generate_post(listings)

    assert "AI Governance Job Roundup" in post
    assert "3 new roles" in post
    assert "AI Policy Researcher" in post
    assert "GovAI" in post
    assert "ML Research Engineer" in post
    assert "AI Safety Fellowship" in post
    assert "#AIGovernance" in post


def test_generate_post_empty():
    post = generate_post([])
    assert "No new roles found" in post


def test_generate_post_with_failed_sources():
    listings = [
        _make_listing(title="Test Policy Job"),
    ]
    post = generate_post(listings, failed_sources=["lever", "ashby"])
    assert "SCRAPER ISSUES" in post
    assert "lever" in post
    assert "ashby" in post


def test_generate_post_with_errors_at_top():
    """Errors should appear at the TOP of the post, before listings."""
    listings = [
        _make_listing(title="Test Policy Job"),
    ]
    post = generate_post(
        listings,
        failed_sources=["llm"],
        scraper_errors={"llm": "AuthenticationError: Invalid API key"}
    )
    # Error section should appear before the role count
    error_pos = post.find("SCRAPER ISSUES")
    roles_pos = post.find("new role")
    assert error_pos < roles_pos, "Errors should appear before role count"
    assert "AuthenticationError" in post


def test_generate_post_single_listing():
    listings = [_make_listing(title="Solo Job")]
    post = generate_post(listings)
    assert "1 new role " in post  # Singular
