"""Tests for the state management store."""

import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

from src.models import JobListing
from src.store import find_new_listings, load_seen, save_seen


def _make_listing(title: str, org: str) -> JobListing:
    return JobListing(
        title=title,
        organization=org,
        url=f"https://example.com/{title.replace(' ', '-').lower()}",
        source="test",
    )


def test_load_nonexistent():
    """Loading from a nonexistent path should return empty store."""
    result = load_seen(Path("/tmp/nonexistent_store_test.json"))
    assert result == {"last_run": None, "seen": {}}


def test_save_and_load():
    """Save and load should roundtrip correctly."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)

    data = {
        "last_run": "2025-01-20",
        "seen": {
            "abc123": {
                "title": "Test Job",
                "org": "TestOrg",
                "first_seen": "2025-01-20",
                "last_seen": "2025-01-20",
            }
        },
    }

    save_seen(data, path)
    loaded = load_seen(path)

    assert loaded["last_run"] == "2025-01-20"
    assert "abc123" in loaded["seen"]
    assert loaded["seen"]["abc123"]["title"] == "Test Job"

    path.unlink()


def test_find_new_listings_all_new():
    """On first run, all listings should be new."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = Path(f.name)
        f.write(b'{"last_run": null, "seen": {}}')

    listings = [
        _make_listing("Job A", "Org A"),
        _make_listing("Job B", "Org B"),
    ]

    new, all_current = find_new_listings(listings, store_path=path)
    assert len(new) == 2
    assert len(all_current) == 2

    path.unlink()


def test_find_new_listings_some_seen():
    """Previously seen listings should not appear as new."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        path = Path(f.name)
        listing_a = _make_listing("Job A", "Org A")
        store = {
            "last_run": date.today().isoformat(),
            "seen": {
                listing_a.fingerprint: {
                    "title": "Job A",
                    "org": "Org A",
                    "first_seen": date.today().isoformat(),
                    "last_seen": date.today().isoformat(),
                }
            },
        }
        json.dump(store, f)

    listings = [
        _make_listing("Job A", "Org A"),  # Already seen
        _make_listing("Job C", "Org C"),  # New
    ]

    new, _ = find_new_listings(listings, store_path=path)
    assert len(new) == 1
    assert new[0].title == "Job C"

    path.unlink()


def test_expired_listings_pruned():
    """Listings not seen for > SEEN_EXPIRY_WEEKS should be pruned."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
        path = Path(f.name)
        old_date = (date.today() - timedelta(weeks=5)).isoformat()
        store = {
            "last_run": old_date,
            "seen": {
                "old_hash": {
                    "title": "Old Job",
                    "org": "Old Org",
                    "first_seen": old_date,
                    "last_seen": old_date,
                }
            },
        }
        json.dump(store, f)

    # Run with no current listings
    new, _ = find_new_listings([], store_path=path)

    # The old listing should have been pruned
    updated = load_seen(path)
    assert "old_hash" not in updated["seen"]

    path.unlink()
