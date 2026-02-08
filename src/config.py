"""Configuration for all scraper sources, keywords, and settings."""

# ---------------------------------------------------------------------------
# Governance keyword filter
# Applied to title + description for broad think tanks (Sections B/C).
# AI-focused orgs (Section A) skip filtering — all their listings are relevant.
# ---------------------------------------------------------------------------

GOVERNANCE_KEYWORDS = [
    # Core governance terms
    "governance",
    "policy",
    "regulation",
    "regulatory",
    "government affairs",
    "public policy",
    "government relations",
    "legislative",
    "compliance",
    "standards",
    # AI-specific
    "ai safety",
    "ai ethics",
    "responsible ai",
    "ai policy",
    "ai risk",
    "ai governance",
    "existential risk",
    "artificial intelligence",
    "machine learning",
    "technology policy",
    "tech policy",
    "digital policy",
    "frontier model",
    "foundation model",
    "algorithmic",
    "autonomous systems",
]

# ---------------------------------------------------------------------------
# Tier 1 — Aggregator APIs
# ---------------------------------------------------------------------------

EIGHTY_K_API_BASE = "https://backend.eawork.org/api/jobs/"
EIGHTY_K_TAGS = ["AI safety & policy"]

# ---------------------------------------------------------------------------
# Tier 2 — ATS Platform Orgs
# Each entry: {"name": display name, "slug": ATS identifier, "ai_focused": bool}
# ai_focused=True means take all listings; False means apply keyword filter
# ---------------------------------------------------------------------------

# NOTE: Only include verified working ATS slugs here.
# Orgs with unknown/custom ATS go in LLM_SCRAPE_ORGS below.

LEVER_ORGS = [
    {"name": "Center for AI Safety", "slug": "aisafety", "ai_focused": True},
    {"name": "Apollo Research", "slug": "apolloresearch", "ai_focused": True},
]

GREENHOUSE_ORGS = [
    {"name": "Anthropic", "slug": "anthropic", "ai_focused": True},
]

ASHBY_ORGS = [
    {"name": "OpenAI", "slug": "openai", "ai_focused": True},
]

# ---------------------------------------------------------------------------
# Tier 3 — LLM-Assisted HTML Extraction
# For orgs with custom career pages (no ATS API).
# Each entry: {"name": ..., "careers_url": ..., "ai_focused": bool}
# ---------------------------------------------------------------------------

LLM_SCRAPE_ORGS = [
    # --- A. AI Safety & Governance Focused ---
    {"name": "Centre for the Governance of AI (GovAI)", "careers_url": "https://www.governance.ai/opportunities", "ai_focused": True},
    {"name": "Center for Security and Emerging Technology (CSET)", "careers_url": "https://cset.georgetown.edu/careers/", "ai_focused": True},
    {"name": "AI Policy Institute", "careers_url": "https://theaipi.org/careers/", "ai_focused": True},
    {"name": "Institute for AI Policy and Strategy (IAPS)", "careers_url": "https://www.iaps.ai/careers", "ai_focused": True},
    {"name": "Centre for Future Generations", "careers_url": "https://cfg.eu/careers/", "ai_focused": True},
    {"name": "Simon Institute for Longterm Governance", "careers_url": "https://www.simoninstitute.ch/about/jobs/", "ai_focused": True},
    {"name": "The Future Society", "careers_url": "https://thefuturesociety.org/careers/", "ai_focused": True},
    {"name": "UK AI Safety Institute", "careers_url": "https://www.aisi.gov.uk/work-with-us", "ai_focused": True},
    {"name": "Americans for Responsible Innovation", "careers_url": "https://ari.us/careers/", "ai_focused": True},
    {"name": "SaferAI", "careers_url": "https://safer-ai.org/careers/", "ai_focused": True},
    {"name": "Secure AI Project", "careers_url": "https://secureaiproject.org/careers/", "ai_focused": True},
    {"name": "AI Governance & Safety Canada", "careers_url": "https://aigs.ca/careers/", "ai_focused": True},
    {"name": "Center for Law & AI Risk (CLAIR)", "careers_url": "https://clair-ai.org/careers/", "ai_focused": True},
    {"name": "AI Standards Lab", "careers_url": "https://aistandardslab.org/careers/", "ai_focused": True},
    {"name": "Google DeepMind", "careers_url": "https://deepmind.google/about/careers/", "ai_focused": True},
    {"name": "Future of Life Institute", "careers_url": "https://futureoflife.org/our-work/careers/", "ai_focused": True},
    {"name": "Open Philanthropy", "careers_url": "https://www.openphilanthropy.org/careers/", "ai_focused": True},
    {"name": "Alignment Research Center (ARC)", "careers_url": "https://alignment.org/careers/", "ai_focused": True},
    {"name": "Center for Human-Compatible AI (CHAI)", "careers_url": "https://humancompatible.ai/jobs/", "ai_focused": True},
    {"name": "AI Now Institute", "careers_url": "https://ainowinstitute.org/jobs", "ai_focused": True},
    {"name": "Responsible AI Institute", "careers_url": "https://www.responsible.ai/careers/", "ai_focused": True},
    {"name": "Stanford HAI", "careers_url": "https://hai.stanford.edu/about/careers", "ai_focused": True},
    {"name": "Ada Lovelace Institute", "careers_url": "https://www.adalovelaceinstitute.org/about/jobs/", "ai_focused": True},
    {"name": "Alan Turing Institute", "careers_url": "https://www.turing.ac.uk/work-turing", "ai_focused": True},
    {"name": "Gray Swan", "careers_url": "https://grayswan.ai/careers/", "ai_focused": True},

    # --- B. Major US Think Tanks ---
    {"name": "Brookings Institution", "careers_url": "https://www.brookings.edu/careers/", "ai_focused": False},
    {"name": "Carnegie Endowment for International Peace", "careers_url": "https://carnegieendowment.org/about/employment", "ai_focused": False},
    {"name": "Center for a New American Security (CNAS)", "careers_url": "https://www.cnas.org/careers", "ai_focused": False},
    {"name": "Council on Foreign Relations", "careers_url": "https://www.cfr.org/career-opportunities", "ai_focused": False},
    {"name": "New America", "careers_url": "https://www.newamerica.org/careers/", "ai_focused": False},
    {"name": "Aspen Institute", "careers_url": "https://www.aspeninstitute.org/careers/", "ai_focused": False},
    {"name": "Bipartisan Policy Center", "careers_url": "https://bipartisanpolicy.org/about/careers/", "ai_focused": False},
    {"name": "Heritage Foundation", "careers_url": "https://www.heritage.org/about-heritage/careers", "ai_focused": False},
    {"name": "American Enterprise Institute", "careers_url": "https://www.aei.org/jobs/", "ai_focused": False},
    {"name": "Cato Institute", "careers_url": "https://www.cato.org/employment-opportunities", "ai_focused": False},
    {"name": "R Street Institute", "careers_url": "https://www.rstreet.org/jobs/", "ai_focused": False},
    {"name": "Technology Policy Institute", "careers_url": "https://techpolicyinstitute.org/about-us/careers/", "ai_focused": False},
    {"name": "Information Technology and Innovation Foundation", "careers_url": "https://itif.org/about/jobs/", "ai_focused": False},
    {"name": "Stimson Center", "careers_url": "https://www.stimson.org/about/careers/", "ai_focused": False},
    {"name": "Georgetown Law Center on Privacy & Technology", "careers_url": "https://www.law.georgetown.edu/privacy-technology-center/", "ai_focused": False},

    # --- C. UK & European Think Tanks ---
    {"name": "Chatham House", "careers_url": "https://www.chathamhouse.org/about-us/work-us", "ai_focused": False},
    {"name": "Bruegel", "careers_url": "https://www.bruegel.org/about/careers", "ai_focused": False},
    {"name": "Centre for European Reform", "careers_url": "https://www.cer.eu/about/vacancies", "ai_focused": False},
    {"name": "European Policy Centre", "careers_url": "https://www.epc.eu/en/vacancies", "ai_focused": False},
    {"name": "European Council on Foreign Relations", "careers_url": "https://ecfr.eu/about/jobs/", "ai_focused": False},
    {"name": "Tony Blair Institute for Global Change", "careers_url": "https://institute.global/careers/", "ai_focused": False},
    {"name": "Oxford Internet Institute", "careers_url": "https://www.oii.ox.ac.uk/about/jobs/", "ai_focused": False},
    {"name": "Oxford Martin School", "careers_url": "https://www.oxfordmartin.ox.ac.uk/vacancies/", "ai_focused": False},
    {"name": "Cambridge CSER", "careers_url": "https://www.cser.ac.uk/opportunities/", "ai_focused": True},
    {"name": "Leverhulme Centre for the Future of Intelligence", "careers_url": "https://lcfi.ac.uk/opportunities/", "ai_focused": True},
    {"name": "Royal United Services Institute (RUSI)", "careers_url": "https://rusi.org/about/careers", "ai_focused": False},
    {"name": "Institute for Government", "careers_url": "https://www.instituteforgovernment.org.uk/about-us/work-for-us", "ai_focused": False},
    {"name": "Istituto Affari Internazionali", "careers_url": "https://www.iai.it/en/jobs", "ai_focused": False},

    # --- D. Fellowships ---
    {"name": "Horizon Fellowship", "careers_url": "https://www.horizonfellowship.org/", "ai_focused": True},
    {"name": "TechCongress", "careers_url": "https://www.techcongress.io/", "ai_focused": True},
    {"name": "AAAS S&T Policy Fellowships", "careers_url": "https://www.aaas.org/page/stpf", "ai_focused": False},
]

# ---------------------------------------------------------------------------
# LLM extraction settings
# ---------------------------------------------------------------------------

LLM_MODEL = "claude-haiku-4-20250514"
LLM_EXTRACTION_PROMPT = """Extract all job/position listings from this career page HTML.
Return a JSON array where each element has:
- "title": job title string
- "url": full URL to the job posting (resolve relative URLs against {base_url})
- "location": location if mentioned, else null
- "role_type": "Full-time", "Part-time", "Fellowship", "Internship", or null

Only include actual job openings, internships, and fellowships.
Ignore navigation links, news articles, blog posts, event listings, etc.
If there are no job listings on the page, return an empty array: []
Return ONLY valid JSON, no other text."""

LLM_MAX_HTML_CHARS = 50000  # Truncate HTML beyond this to control costs

# ---------------------------------------------------------------------------
# General settings
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT = 30  # seconds
REQUEST_DELAY = 1.5  # seconds between requests to same domain
MAX_RETRIES = 2
SEEN_EXPIRY_WEEKS = 4  # Prune listings not seen for this many weeks
