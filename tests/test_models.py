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


def test_new_fields_defaults():
    """New fields should default to None/empty."""
    listing = JobListing(title="Test", organization="Org", url="https://example.com")
    assert listing.description == ""
    assert listing.work_mode is None
    assert listing.visa_sponsorship is None
    assert listing.seniority_level is None


def test_new_fields_roundtrip():
    """New fields should survive serialization roundtrip."""
    listing = JobListing(
        title="Policy Analyst",
        organization="GovAI",
        url="https://example.com/job",
        description="Full description of the role...",
        work_mode="Remote (Global)",
        visa_sponsorship=True,
        seniority_level="Mid",
    )
    d = listing.to_dict()
    restored = JobListing.from_dict(d)
    assert restored.description == listing.description
    assert restored.work_mode == listing.work_mode
    assert restored.visa_sponsorship == listing.visa_sponsorship
    assert restored.seniority_level == listing.seniority_level


def test_backward_compat_missing_new_fields():
    """Old dicts without new fields should still deserialize."""
    old_dict = {
        "title": "Old Job",
        "organization": "OldOrg",
        "url": "https://example.com",
        "location": None,
        "salary_range": None,
        "role_type": None,
        "description_snippet": "",
        "date_posted": None,
        "date_closes": None,
        "source": "test",
        "date_scraped": "2025-01-01",
        "tags": [],
    }
    listing = JobListing.from_dict(old_dict)
    assert listing.title == "Old Job"
    assert listing.description == ""
    assert listing.work_mode is None
    assert listing.relevance_tag is None
    assert listing.relevance_reason is None


def test_relevance_fields_roundtrip():
    """Relevance fields should survive serialization roundtrip."""
    listing = JobListing(
        title="AGI Safety Researcher",
        organization="AI Safety Org",
        url="https://example.com/job",
        relevance_tag="AGI Safety & Governance",
        relevance_reason="Focuses on AI alignment and control mechanisms",
    )
    d = listing.to_dict()
    restored = JobListing.from_dict(d)
    assert restored.relevance_tag == listing.relevance_tag
    assert restored.relevance_reason == listing.relevance_reason


def test_from_dict_ignores_unknown_keys():
    """from_dict should tolerate unknown keys."""
    d = {
        "title": "Test",
        "organization": "Org",
        "url": "https://example.com",
        "date_scraped": "2025-01-01",
        "unknown_future_field": "value",
    }
    listing = JobListing.from_dict(d)
    assert listing.title == "Test"
