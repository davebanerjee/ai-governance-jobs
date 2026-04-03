# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Weekly scraper that collects AI governance/policy job listings from ~60 organizations, deduplicates them, enriches them with metadata via LLM, persists full listings for review, and provides a Streamlit dashboard for curating LinkedIn posts.

**Pipeline:** scrape → dedup → find new → filter already-stored → **enrich via LLM** → **store in listings.json** → **review in Streamlit** → **build themed post on demand**

## Commands

```bash
# Run the full pipeline (requires ANTHROPIC_API_KEY for LLM scraper + enrichment)
ANTHROPIC_API_KEY=... python -m src.main

# Launch the Streamlit dashboard (pulls latest data first)
./run_dashboard.sh

# Or run dashboard directly
streamlit run src/dashboard.py

# Run tests
pytest

# Run a single test file
pytest tests/test_models.py

# Run a single test
pytest tests/test_models.py::test_fingerprint_deterministic -v
```

## Architecture

### Scraper Tiers (in `src/scrapers/`)

All scrapers inherit from `BaseScraper` (`base.py`), which provides rate-limited HTTP, retry logic, and two filtering methods:

- **Tier 1 — Aggregator API**: `eighty_k.py` hits the 80,000 Hours REST API with pagination
- **Tier 2 — ATS Platform APIs**: `lever.py`, `greenhouse.py`, `ashby.py` each scrape public JSON APIs for orgs configured in `src/config.py` (e.g., Anthropic via Greenhouse, OpenAI via Ashby)
- **Tier 3 — LLM extraction**: `llm_scraper.py` fetches raw HTML from custom career pages, cleans it with BeautifulSoup, then sends to Claude Haiku for structured JSON extraction. This covers ~50 orgs (think tanks, fellowships, etc.)

### Filtering

Every scraper applies `filter_policy_roles()` — a strict title-keyword filter that drops non-governance roles (engineering, sales, etc.) even from AI-focused orgs. Keywords are configured in `src/config.py` under `POLICY_ROLE_KEYWORDS` and `ALWAYS_INCLUDE_KEYWORDS`.

### LLM Enrichment (`src/enrichment.py`)

After scraping, new listings are sent to Claude Haiku to extract:
- `work_mode`: Remote (Global/US/EU), Hybrid, In-Person
- `visa_sponsorship`: True/False/None
- `seniority_level`: Entry, Mid, Senior, All Levels
- `relevance_tag`: AGI safety focus category (e.g., "AGI Safety", "Ethics", "General Policy")
- `relevance_reason`: One-sentence explanation of why the role is relevant

Uses description text (full from ATS scrapers, snippet fallback for LLM-scraped). Skips if `ANTHROPIC_API_KEY` not set.

### Pipeline Flow (`src/main.py`)

1. Run all scrapers sequentially, collecting `JobListing` objects
2. `dedup.py` — exact fingerprint match + fuzzy matching (SequenceMatcher, threshold 0.85)
3. `store.py` — compare against `seen_listings.json` (ephemeral, 4-week expiry) to identify new listings
4. Filter out fingerprints already in `listings.json` (permanent store — prevents re-surfacing rejected listings)
5. `enrichment.py` — LLM enrichment of new listings
6. `listing_store.py` — persist enriched listings with review metadata
7. `post_generator.py` — generate fallback LinkedIn draft saved to `data/drafts/`

### Two Persistent Stores

- **`data/seen_listings.json`** (`src/store.py`) — ephemeral "have we seen this before" tracker. Entries expire after 4 weeks. Used only to detect which listings are *new* each run.
- **`data/listings.json`** (`src/listing_store.py`) — permanent review store, keyed by fingerprint. Stores full listing data + review metadata (`unreviewed`, `relevant`, `irrelevant`). Listings already in this store are **never re-added**, so rejecting a listing permanently suppresses it.

Run logs are written to `data/logs/<YYYY-MM-DD>.log` (DEBUG level; console shows INFO only).

### Streamlit Dashboard (`src/dashboard.py`)

Two views:
- **Review Listings**: Filter by status/org/work mode/seniority, approve/reject individually or in bulk
- **Post Builder**: Select from approved listings with thematic filters, generate LinkedIn post on demand

### Key Data Model

`JobListing` (`src/models.py`) — fingerprint is MD5 of `org|title` (lowercased). Fields include `description` (full text), `work_mode`, `visa_sponsorship`, `seniority_level`, `relevance_tag`, `relevance_reason`. The `from_dict` method tolerates unknown keys (forward-compatible deserialization).

## Adding a New Organization

- **If it uses Lever/Greenhouse/Ashby**: Add an entry to the corresponding `*_ORGS` list in `src/config.py`
- **If it has a custom careers page**: Add to `LLM_SCRAPE_ORGS` in `src/config.py`
- Set `ai_focused: True` for AI safety/governance orgs (all listings taken, then policy-filtered), `False` for general orgs (same filter applies either way now, but the flag is kept for legacy `filter_governance`)

## Adding a New Scraper

1. Create `src/scrapers/new_scraper.py` subclassing `BaseScraper`
2. Implement `fetch_listings()` returning `list[JobListing]`
3. Call `self.filter_policy_roles()` on results before returning
4. Register the class in the `SCRAPERS` list in `src/main.py`
