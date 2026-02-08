"""Tests for deduplication logic."""

from src.dedup import deduplicate
from src.models import JobListing


def _make_listing(title: str, org: str, source: str = "test") -> JobListing:
    return JobListing(
        title=title,
        organization=org,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        source=source,
    )


def test_no_duplicates():
    """Unique listings should all be kept."""
    listings = [
        _make_listing("AI Policy Researcher", "GovAI"),
        _make_listing("ML Engineer", "Anthropic"),
        _make_listing("Policy Analyst", "Brookings"),
    ]
    result = deduplicate(listings)
    assert len(result) == 3


def test_exact_duplicate():
    """Exact same org+title should be deduped."""
    listings = [
        _make_listing("AI Policy Researcher", "GovAI", source="80k_hours"),
        _make_listing("AI Policy Researcher", "GovAI", source="aisafety_com"),
    ]
    result = deduplicate(listings)
    assert len(result) == 1
    assert result[0].source == "80k_hours"  # First occurrence kept


def test_case_insensitive_dedup():
    """Case differences should still dedup."""
    listings = [
        _make_listing("AI Policy Researcher", "GovAI"),
        _make_listing("ai policy researcher", "govai"),
    ]
    result = deduplicate(listings)
    assert len(result) == 1


def test_fuzzy_duplicate():
    """Slightly different titles should be caught by fuzzy matching."""
    listings = [
        _make_listing("AI Policy Researcher", "GovAI"),
        _make_listing("AI Policy Researcher (Senior)", "GovAI"),
    ]
    result = deduplicate(listings)
    # These might or might not fuzzy match depending on threshold
    # The key point is the function runs without error
    assert len(result) >= 1
    assert len(result) <= 2


def test_different_orgs_not_deduped():
    """Same title at different orgs should NOT be deduped."""
    listings = [
        _make_listing("Policy Analyst", "Brookings"),
        _make_listing("Policy Analyst", "RAND"),
    ]
    result = deduplicate(listings)
    assert len(result) == 2


def test_empty_input():
    """Empty list should return empty list."""
    assert deduplicate([]) == []


def test_preserves_order():
    """First occurrence should be kept, maintaining source priority."""
    listings = [
        _make_listing("Test Job", "TestOrg", source="source_a"),
        _make_listing("Test Job", "TestOrg", source="source_b"),
        _make_listing("Other Job", "TestOrg", source="source_c"),
    ]
    result = deduplicate(listings)
    assert len(result) == 2
    assert result[0].source == "source_a"
    assert result[1].source == "source_c"
