"""Data models for job listings."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional


@dataclass
class JobListing:
    """A single job listing scraped from any source."""

    # Identity
    title: str
    organization: str
    url: str

    # Details
    location: Optional[str] = None
    salary_range: Optional[str] = None
    role_type: Optional[str] = None  # Full-time, Fellowship, Internship, Part-time
    description_snippet: str = ""
    description: str = ""  # Full description text (for LLM enrichment)
    work_mode: Optional[str] = None  # "Remote (Global)", "Remote (US)", "Remote (EU)", "Hybrid", "In-Person"
    visa_sponsorship: Optional[bool] = None
    seniority_level: Optional[str] = None  # "Entry", "Mid", "Senior", "All Levels"
    relevance_tag: Optional[str] = None  # AGI focus category
    relevance_reason: Optional[str] = None  # One-sentence explanation

    # Metadata
    date_posted: Optional[date] = None
    date_closes: Optional[date] = None
    source: str = ""  # Which scraper found it (e.g. "80k_hours", "lever:anthropic")
    date_scraped: date = field(default_factory=date.today)
    tags: list[str] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        """Generate a dedup fingerprint based on org + title."""
        normalized = f"{self.organization.lower().strip()}|{self.title.lower().strip()}"
        return hashlib.md5(normalized.encode()).hexdigest()

    @property
    def id(self) -> str:
        """Alias for fingerprint."""
        return self.fingerprint

    def to_dict(self) -> dict:
        """Serialize to dict for JSON storage."""
        d = asdict(self)
        # Convert dates to ISO strings
        for key in ("date_posted", "date_closes", "date_scraped"):
            if d[key] is not None:
                d[key] = d[key].isoformat()
        d["id"] = self.id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> JobListing:
        """Deserialize from dict."""
        d = d.copy()
        # Remove computed/extra keys not in __init__
        d.pop("id", None)
        d.pop("fingerprint", None)
        for key in ("date_posted", "date_closes", "date_scraped"):
            if d.get(key) is not None:
                d[key] = date.fromisoformat(d[key])
        # Tolerate unknown keys (forward compatibility)
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        d = {k: v for k, v in d.items() if k in valid_fields}
        return cls(**d)
