"""Tests for the JobListing model."""

from datetime import date

from src.models import JobListing


def test_fingerprint_consistency():
    """Same org+title should produce the same fingerprint."""
    a = JobListing(title="AI Policy Researcher", organization="GovAI", url="https://example.com/1")
    b = JobListing(title="AI Policy Researcher", organization="GovAI", url="https://example.com/2")
    assert a.fingerprint == b.fingerprint


def test_fingerprint_case_insensitive():
    """Fingerprints should be case-insensitive."""
    a = JobListing(title="AI Policy Researcher", organization="GovAI", url="https://example.com/1")
    b = JobListing(title="ai policy researcher", organization="govai", url="https://example.com/2")
    assert a.fingerprint == b.fingerprint


def test_fingerprint_different_jobs():
    """Different jobs should have different fingerprints."""
    a = JobListing(title="AI Policy Researcher", organization="GovAI", url="https://example.com/1")
    b = JobListing(title="ML Engineer", organization="GovAI", url="https://example.com/2")
    assert a.fingerprint != b.fingerprint


def test_to_dict_roundtrip():
    """Serialization and deserialization should be lossless."""
    listing = JobListing(
        title="AI Policy Researcher",
        organization="GovAI",
        url="https://example.com/job/1",
        location="Oxford, UK",
        salary_range="$80k-$120k",
        role_type="Full-time",
        description_snippet="Research AI governance frameworks...",
        date_posted=date(2025, 1, 15),
        date_closes=date(2025, 2, 15),
        source="80k_hours",
        date_scraped=date(2025, 1, 20),
        tags=["governance", "research"],
    )

    d = listing.to_dict()
    restored = JobListing.from_dict(d)

    assert restored.title == listing.title
    assert restored.organization == listing.organization
    assert restored.url == listing.url
    assert restored.location == listing.location
    assert restored.salary_range == listing.salary_range
    assert restored.role_type == listing.role_type
    assert restored.date_posted == listing.date_posted
    assert restored.date_closes == listing.date_closes
    assert restored.source == listing.source
    assert restored.tags == listing.tags


def test_id_is_fingerprint():
    """The id property should return the fingerprint."""
    listing = JobListing(title="Test Job", organization="TestOrg", url="https://example.com")
    assert listing.id == listing.fingerprint
