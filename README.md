# AI Governance Jobs

Weekly scraper that collects AI governance and policy job listings from ~60 organizations, deduplicates them, enriches them with metadata via Claude, and provides a Streamlit dashboard for curating LinkedIn posts.

## How It Works

1. **Scrape** — pulls listings from 80,000 Hours API, ATS platforms (Lever, Greenhouse, Ashby), and ~50 custom career pages via LLM-assisted HTML extraction
2. **Dedup + filter** — deduplicates across sources and filters to policy/governance roles only
3. **Enrich** — Claude Haiku extracts work mode, visa sponsorship, seniority, and relevance tags for each new listing
4. **Store** — new listings land in `data/listings.json` with `unreviewed` status
5. **Review** — Streamlit dashboard lets you approve/reject listings and generate LinkedIn posts on demand

The pipeline runs automatically every Monday via GitHub Actions and commits updated data back to the repo.

## Setup

**Requirements:** Python 3.12+, an [Anthropic API key](https://console.anthropic.com/)

```bash
git clone <repo-url>
cd ai-governance-jobs
pip install -r requirements.txt
```

## Running

### Automated (recommended)

The GitHub Actions workflow runs every Monday at 9am UTC. To enable it:

1. Go to your repo's **Settings → Secrets and variables → Actions**
2. Add a secret named `ANTHROPIC_API_KEY` with your Anthropic API key
3. The workflow will scrape, commit updated data, and upload logs as artifacts

You can also trigger it manually from the **Actions** tab.

### Manual run

```bash
ANTHROPIC_API_KEY=your_key_here python -m src.main
```

Logs are written to `data/logs/<YYYY-MM-DD>.log`. The pipeline also saves a draft LinkedIn post to `data/drafts/`.

### Dashboard

Pull the latest scraped data and launch the review dashboard:

```bash
./run_dashboard.sh
```

Or run directly (if you don't need to pull first):

```bash
PYTHONPATH=$(pwd) streamlit run src/dashboard.py
```

The dashboard has two views:
- **Review Listings** — approve or reject new listings, with filters by org, work mode, and seniority
- **Post Builder** — select from approved listings and generate a themed LinkedIn post on demand

## Adding Organizations

Edit `src/config.py`:

- **Lever/Greenhouse/Ashby ATS**: add to the corresponding `*_ORGS` list with `{"name": "...", "slug": "...", "ai_focused": True/False}`
- **Custom career page**: add to `LLM_SCRAPE_ORGS` with `{"name": "...", "careers_url": "...", "ai_focused": True/False}`

Set `ai_focused: True` for AI safety/governance orgs (broader inclusion), `False` for general think tanks (governance keyword filter still applies).

## Project Structure

```
src/
  main.py           # Pipeline orchestrator
  config.py         # Org lists, keywords, LLM settings
  models.py         # JobListing dataclass
  dedup.py          # Fingerprint + fuzzy deduplication
  store.py          # Seen-listings tracker (seen_listings.json)
  listing_store.py  # Persistent review store (listings.json)
  enrichment.py     # LLM metadata extraction
  dashboard.py      # Streamlit UI
  post_generator.py # LinkedIn post drafting
  scrapers/
    base.py         # BaseScraper with rate limiting + filtering
    eighty_k.py     # 80,000 Hours API
    lever.py        # Lever ATS
    greenhouse.py   # Greenhouse ATS
    ashby.py        # Ashby ATS
    llm_scraper.py  # HTML extraction via Claude Haiku
data/
  listings.json     # Permanent review store (committed)
  seen_listings.json # Ephemeral seen tracker (committed)
  drafts/           # Generated LinkedIn post drafts
  logs/             # Run logs
```

## Tests

```bash
pytest                                              # all tests
pytest tests/test_models.py                        # single file
pytest tests/test_models.py::test_fingerprint_deterministic -v  # single test
```
