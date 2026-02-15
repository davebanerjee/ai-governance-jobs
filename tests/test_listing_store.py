"""Tests for the persistent listing store."""

import json
from pathlib import Path

from src.listing_store import (
    add_new_listings,
    get_listings_by_status,
    get_stored_fingerprints,
    load_listings,
    save_listings,
    update_review_status,
)
from src.models import JobListing


def _make_listing(title="Test Job", org="TestOrg", url="https://example.com"):
    return JobListing(title=title, organization=org, url=url)


def test_load_empty(tmp_path):
    """Loading a non-existent file returns empty dict."""
    path = tmp_path / "listings.json"
    assert load_listings(path) == {}


def test_save_and_load(tmp_path):
    """Saved data should be loadable."""
    path = tmp_path / "listings.json"
    data = {"abc": {"listing": {}, "review_status": "unreviewed"}}
    save_listings(data, path)
    loaded = load_listings(path)
    assert loaded == data


def test_add_new_listings(tmp_path):
    """New listings should be added with unreviewed status."""
    path = tmp_path / "listings.json"
    listings = [_make_listing("Job A", "Org1"), _make_listing("Job B", "Org2")]
    added = add_new_listings(listings, path)
    assert added == 2

    store = load_listings(path)
    assert len(store) == 2
    for entry in store.values():
        assert entry["review_status"] == "unreviewed"
        assert entry["reviewed_at"] is None


def test_no_duplicate_add(tmp_path):
    """Adding the same listing twice should not duplicate it."""
    path = tmp_path / "listings.json"
    listing = _make_listing("Job A", "Org1")
    add_new_listings([listing], path)
    added = add_new_listings([listing], path)
    assert added == 0
    assert len(load_listings(path)) == 1


def test_irrelevant_not_readded(tmp_path):
    """A listing marked irrelevant should not be re-added."""
    path = tmp_path / "listings.json"
    listing = _make_listing("Job A", "Org1")
    add_new_listings([listing], path)
    update_review_status(listing.fingerprint, "irrelevant", path)

    # Try to add again
    added = add_new_listings([listing], path)
    assert added == 0

    store = load_listings(path)
    assert store[listing.fingerprint]["review_status"] == "irrelevant"


def test_update_review_status(tmp_path):
    """Review status should be updatable."""
    path = tmp_path / "listings.json"
    listing = _make_listing()
    add_new_listings([listing], path)
    update_review_status(listing.fingerprint, "relevant", path)

    store = load_listings(path)
    assert store[listing.fingerprint]["review_status"] == "relevant"
    assert store[listing.fingerprint]["reviewed_at"] is not None


def test_get_listings_by_status(tmp_path):
    """Should filter listings by review status."""
    path = tmp_path / "listings.json"
    listings = [_make_listing("A", "Org1"), _make_listing("B", "Org2"), _make_listing("C", "Org3")]
    add_new_listings(listings, path)
    update_review_status(listings[0].fingerprint, "relevant", path)
    update_review_status(listings[1].fingerprint, "irrelevant", path)

    relevant = get_listings_by_status("relevant", path)
    assert len(relevant) == 1
    assert relevant[0]["listing"]["title"] == "A"

    unreviewed = get_listings_by_status("unreviewed", path)
    assert len(unreviewed) == 1


def test_get_stored_fingerprints(tmp_path):
    """Should return all fingerprints in the store."""
    path = tmp_path / "listings.json"
    listings = [_make_listing("A", "Org1"), _make_listing("B", "Org2")]
    add_new_listings(listings, path)
    fps = get_stored_fingerprints(path)
    assert fps == {listings[0].fingerprint, listings[1].fingerprint}
