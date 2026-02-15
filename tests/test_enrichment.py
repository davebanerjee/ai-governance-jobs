"""Tests for the LLM enrichment module."""

import json
from unittest.mock import MagicMock, patch

from src.enrichment import (
    VALID_RELEVANCE_TAGS,
    VALID_SENIORITY_LEVELS,
    VALID_WORK_MODES,
    _enrich_single,
    enrich_listings,
)
from src.models import JobListing


def _make_listing(**kwargs):
    defaults = {
        "title": "Policy Analyst",
        "organization": "GovAI",
        "url": "https://example.com",
        "description": "We are looking for a mid-level policy analyst to work remotely.",
    }
    defaults.update(kwargs)
    return JobListing(**defaults)


def _mock_response(text):
    """Create a mock Anthropic API response."""
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


class TestEnrichSingle:
    def test_valid_response(self):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            json.dumps({
                "work_mode": "Remote (Global)",
                "visa_sponsorship": True,
                "seniority_level": "Mid",
            })
        )
        listing = _make_listing()
        result = _enrich_single(client, listing)
        assert result.work_mode == "Remote (Global)"
        assert result.visa_sponsorship is True
        assert result.seniority_level == "Mid"

    def test_code_fence_response(self):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            '```json\n{"work_mode": "Hybrid", "visa_sponsorship": null, "seniority_level": "Senior"}\n```'
        )
        listing = _make_listing()
        result = _enrich_single(client, listing)
        assert result.work_mode == "Hybrid"
        assert result.seniority_level == "Senior"

    def test_invalid_enum_values_become_none(self):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            json.dumps({
                "work_mode": "Fully Remote",
                "visa_sponsorship": False,
                "seniority_level": "Junior",
            })
        )
        listing = _make_listing()
        result = _enrich_single(client, listing)
        assert result.work_mode is None  # "Fully Remote" not in valid set
        assert result.visa_sponsorship is False
        assert result.seniority_level is None  # "Junior" not in valid set

    def test_empty_description_skipped(self):
        client = MagicMock()
        listing = _make_listing(description="", description_snippet="")
        result = _enrich_single(client, listing)
        client.messages.create.assert_not_called()
        assert result.work_mode is None

    def test_falls_back_to_snippet(self):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            json.dumps({
                "work_mode": "In-Person",
                "visa_sponsorship": None,
                "seniority_level": "Entry",
            })
        )
        listing = _make_listing(description="", description_snippet="Short snippet about the role")
        result = _enrich_single(client, listing)
        client.messages.create.assert_called_once()
        assert result.work_mode == "In-Person"


    def test_valid_relevance_response(self):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            json.dumps({
                "work_mode": "Remote (Global)",
                "visa_sponsorship": True,
                "seniority_level": "Mid",
                "relevance_tag": "AGI Safety & Governance",
                "relevance_reason": "Focuses on reducing existential risks from advanced AI",
            })
        )
        listing = _make_listing()
        result = _enrich_single(client, listing)
        assert result.relevance_tag == "AGI Safety & Governance"
        assert result.relevance_reason == "Focuses on reducing existential risks from advanced AI"

    def test_invalid_relevance_tag_becomes_none(self):
        client = MagicMock()
        client.messages.create.return_value = _mock_response(
            json.dumps({
                "work_mode": "Hybrid",
                "visa_sponsorship": False,
                "seniority_level": "Senior",
                "relevance_tag": "Some Invalid Tag",
                "relevance_reason": "This should be cleared",
            })
        )
        listing = _make_listing()
        result = _enrich_single(client, listing)
        assert result.relevance_tag is None
        assert result.relevance_reason is None

    def test_relevance_reason_truncation(self):
        client = MagicMock()
        long_reason = "A" * 200
        client.messages.create.return_value = _mock_response(
            json.dumps({
                "work_mode": "Hybrid",
                "visa_sponsorship": None,
                "seniority_level": "Mid",
                "relevance_tag": "AI Ethics/Responsible AI",
                "relevance_reason": long_reason,
            })
        )
        listing = _make_listing()
        result = _enrich_single(client, listing)
        assert result.relevance_tag == "AI Ethics/Responsible AI"
        assert len(result.relevance_reason) == 150
        assert result.relevance_reason.endswith("...")


class TestEnrichListings:
    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False)
    def test_missing_api_key_returns_unchanged(self):
        listings = [_make_listing()]
        result = enrich_listings(listings)
        assert len(result) == 1
        assert result[0].work_mode is None

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False)
    def test_enriches_with_api_key(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _mock_response(
            json.dumps({
                "work_mode": "Hybrid",
                "visa_sponsorship": None,
                "seniority_level": "Mid",
            })
        )
        with patch("anthropic.Anthropic", return_value=mock_client):
            listings = [_make_listing()]
            result = enrich_listings(listings)
            assert result[0].work_mode == "Hybrid"

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}, clear=False)
    def test_failure_keeps_listing(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API error")
        with patch("anthropic.Anthropic", return_value=mock_client):
            listings = [_make_listing()]
            result = enrich_listings(listings)
            assert len(result) == 1
            assert result[0].work_mode is None
