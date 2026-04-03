"""Streamlit dashboard for reviewing job listings and building LinkedIn posts."""

from __future__ import annotations

import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import requests
import streamlit as st

from src.enrichment import score_single_listing
from src.listing_store import (
    DEFAULT_LISTINGS_PATH,
    load_listings,
    save_listings,
    update_review_status,
)
from src.models import JobListing

st.set_page_config(page_title="AI Governance Jobs", page_icon="\U0001f50d", layout="wide")

# Relevance tag display config
RELEVANCE_COLORS = {
    "AGI Safety & Governance": "#10b981",
    "AI Safety (Technical)": "#3b82f6",
    "Biosecurity/Catastrophic Risk": "#f59e0b",
    "AI Ethics/Responsible AI": "#8b5cf6",
    "General Tech Policy": "#6b7280",
}

RELEVANCE_ICONS = {
    "AGI Safety & Governance": "\U0001f3af",
    "AI Safety (Technical)": "\U0001f52c",
    "Biosecurity/Catastrophic Risk": "\u26a0\ufe0f",
    "AI Ethics/Responsible AI": "\u2696\ufe0f",
    "General Tech Policy": "\U0001f3db\ufe0f",
}


def _impact_badge_html(score: int) -> str:
    """Return an HTML badge for the given impact score."""
    if score >= 8:
        color, label = "#dc2626", f"Impact {score}/10"   # red
    elif score >= 5:
        color, label = "#d97706", f"Impact {score}/10"   # amber
    else:
        color, label = "#6b7280", f"Impact {score}/10"   # gray
    return (
        f'<span style="background-color: {color}; color: white; '
        f'padding: 2px 8px; border-radius: 4px; font-size: 0.8em; '
        f'font-weight: 600;">{label}</span>'
    )


def main():
    st.sidebar.title("\U0001f50d AI Governance Jobs")
    page = st.sidebar.radio("Navigation", ["Review Listings", "Post Builder"])

    # Save & Push button in sidebar
    st.sidebar.markdown("---")
    if st.sidebar.button("\U0001f4e4 Save & Push to GitHub", help="Commits data/listings.json and pushes to GitHub, persisting your approve/reject decisions so rejected listings are never re-surfaced by the pipeline."):
        _git_push()

    if page == "Review Listings":
        review_page()
    else:
        post_builder_page()


# ---------------------------------------------------------------------------
# Review Listings Page
# ---------------------------------------------------------------------------

def review_page():
    st.title("Review Listings")

    # Fix emoji button centering at intermediate viewport widths.
    # The data-testid is on the wrapper div, not the <button> element itself.
    # use_container_width stretches the button but Streamlit defaults to
    # left-aligned text inside, so we target the wrapper and force centering.
    st.markdown("""
    <style>
    [data-testid="stButton"] > button {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 100% !important;
    }
    [data-testid="stButton"] > button > div {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: auto !important;
    }
    [data-testid="stButton"] > button p {
        margin: 0 !important;
        line-height: 1 !important;
        width: auto !important;
        text-align: center !important;
    }
    </style>
    """, unsafe_allow_html=True)

    store = load_listings()
    if not store:
        st.info("No listings found. Run the scraper first: `python -m src.main`")
        return

    # Status filter
    status_filter = st.selectbox(
        "Filter by status",
        ["unreviewed", "relevant", "irrelevant", "all"],
        index=0,
    )

    # Get entries matching status
    if status_filter == "all":
        entries = list(store.items())
    else:
        entries = [(fp, e) for fp, e in store.items() if e["review_status"] == status_filter]

    # Sidebar filters
    all_orgs = sorted({e["listing"].get("organization", "") for _, e in entries})
    all_work_modes = sorted({
        e["listing"].get("work_mode", "") or "Unknown"
        for _, e in entries
    })
    all_seniority = sorted({
        e["listing"].get("seniority_level", "") or "Unknown"
        for _, e in entries
    })
    all_relevance = sorted({
        e["listing"].get("relevance_tag", "") or "Unknown"
        for _, e in entries
    })

    st.sidebar.markdown("### Filters")
    selected_relevance = st.sidebar.multiselect("Relevance", all_relevance, default=[])
    selected_orgs = st.sidebar.multiselect("Organization", all_orgs, default=[])
    selected_work_modes = st.sidebar.multiselect("Work Mode", all_work_modes, default=[])
    selected_seniority = st.sidebar.multiselect("Seniority", all_seniority, default=[])

    # Apply filters
    if selected_relevance:
        entries = [
            (fp, e) for fp, e in entries
            if (e["listing"].get("relevance_tag") or "Unknown") in selected_relevance
        ]
    if selected_orgs:
        entries = [(fp, e) for fp, e in entries if e["listing"].get("organization") in selected_orgs]
    if selected_work_modes:
        entries = [
            (fp, e) for fp, e in entries
            if (e["listing"].get("work_mode") or "Unknown") in selected_work_modes
        ]
    if selected_seniority:
        entries = [
            (fp, e) for fp, e in entries
            if (e["listing"].get("seniority_level") or "Unknown") in selected_seniority
        ]

    st.write(f"**{len(entries)}** listings")

    # Bulk actions
    if entries and status_filter == "unreviewed":
        col1, col2 = st.columns(2)
        with col1:
            if st.button("\u2705 Approve All Visible", use_container_width=True):
                for fp, _ in entries:
                    update_review_status(fp, "relevant")
                st.rerun()
        with col2:
            if st.button("\u274c Reject All Visible", use_container_width=True):
                for fp, _ in entries:
                    update_review_status(fp, "irrelevant")
                st.rerun()

    # Reset button for reviewed listings
    if entries and status_filter in ("relevant", "irrelevant"):
        if st.button("\U0001f504 Reset All Visible to Unreviewed"):
            for fp, _ in entries:
                update_review_status(fp, "unreviewed")
            st.rerun()

    # Display listings — buttons inline, relevance badge, details in expander
    for fp, entry in entries:
        listing_data = entry["listing"]
        title = listing_data.get("title", "Unknown")
        org = listing_data.get("organization", "Unknown")
        location = listing_data.get("location") or ""
        status = entry["review_status"]
        relevance_tag = listing_data.get("relevance_tag")
        relevance_reason = listing_data.get("relevance_reason")

        status_icon = {"unreviewed": "\u2753", "relevant": "\u2705", "irrelevant": "\u274c"}.get(status, "")
        loc_str = f" \u2022 {location}" if location else ""

        # Row: buttons | title summary with relevance badge
        btn_cols = st.columns([0.8, 0.8, 0.8, 10])

        with btn_cols[0]:
            if status != "relevant":
                if st.button("\u2705", key=f"approve_{fp}", help="Approve"):
                    update_review_status(fp, "relevant")
                    st.rerun()
            else:
                st.write("\u2705")

        with btn_cols[1]:
            if status != "irrelevant":
                if st.button("\u274c", key=f"reject_{fp}", help="Reject"):
                    update_review_status(fp, "irrelevant")
                    st.rerun()
            else:
                st.write("\u274c")

        with btn_cols[2]:
            if status != "unreviewed":
                if st.button("\U0001f504", key=f"reset_{fp}", help="Reset to unreviewed"):
                    update_review_status(fp, "unreviewed")
                    st.rerun()

        with btn_cols[3]:
            # Build badges: relevance tag + impact score
            badge_html = ""
            if relevance_tag:
                color = RELEVANCE_COLORS.get(relevance_tag, "#6b7280")
                r_icon = RELEVANCE_ICONS.get(relevance_tag, "")
                badge_html += (
                    f' <span style="background-color: {color}; color: white; '
                    f'padding: 2px 8px; border-radius: 4px; font-size: 0.8em;">'
                    f'{r_icon} {relevance_tag}</span>'
                )

            impact_score = listing_data.get("impact_score")
            if impact_score is not None:
                badge_html += f" {_impact_badge_html(impact_score)}"

            st.markdown(
                f"{status_icon} **{title}** \u2014 {org}{loc_str}{badge_html}",
                unsafe_allow_html=True,
            )

            with st.expander("View details"):
                work_mode = listing_data.get("work_mode") or "Unknown"
                seniority = listing_data.get("seniority_level") or "Unknown"
                visa = listing_data.get("visa_sponsorship")
                visa_str = "Yes" if visa is True else "No" if visa is False else "Unknown"
                salary = listing_data.get("salary_range") or "Not listed"
                source = listing_data.get("source", "")
                url = listing_data.get("url", "")

                # Relevance row
                relevance_display = relevance_tag or "Unknown"
                if relevance_reason:
                    relevance_display += f" \u2014 {relevance_reason}"

                # Impact score row
                impact_reason = listing_data.get("impact_reason")
                if impact_score is not None:
                    impact_display = f"{impact_score}/10"
                    if impact_reason:
                        impact_display += f" \u2014 {impact_reason}"
                else:
                    impact_display = "Not scored"

                st.markdown(f"""
| Field | Value |
|-------|-------|
| **Impact Score** | {impact_display} |
| **Relevance** | {relevance_display} |
| **Location** | {location or 'Not specified'} |
| **Work Mode** | {work_mode} |
| **Seniority** | {seniority} |
| **Visa Sponsorship** | {visa_str} |
| **Salary** | {salary} |
| **Source** | {source} |
| **Added** | {entry.get('added_at', 'Unknown')} |
""")
                if url:
                    st.markdown(f"[\U0001f517 View Job Posting]({url})")

                # On-demand scoring for listings that haven't been scored yet
                if impact_score is None:
                    if st.button("\u26a1 Score impact", key=f"score_{fp}"):
                        with st.spinner("Scoring..."):
                            listing_obj = JobListing.from_dict(listing_data)
                            score, reason = score_single_listing(listing_obj)
                        if score is not None:
                            store = load_listings()
                            store[fp]["listing"]["impact_score"] = score
                            store[fp]["listing"]["impact_reason"] = reason
                            save_listings(store)
                            st.rerun()
                        else:
                            st.warning("Scoring failed — is ANTHROPIC_API_KEY set?")

                snippet = listing_data.get("description_snippet", "")
                if snippet:
                    st.caption(snippet)


# ---------------------------------------------------------------------------
# Post Builder Page
# ---------------------------------------------------------------------------

def post_builder_page():
    st.title("Post Builder")

    store = load_listings()
    if not store:
        st.info("No listings found. Run the scraper first.")
        return

    # Only show approved listings
    approved = [(fp, e) for fp, e in store.items() if e["review_status"] == "relevant"]

    if not approved:
        st.warning("No approved listings yet. Go to Review Listings to approve some first.")
        return

    # Sidebar filters for thematic grouping
    st.sidebar.markdown("### Post Filters")

    all_orgs = sorted({e["listing"].get("organization", "") for _, e in approved})
    all_seniority = sorted({
        e["listing"].get("seniority_level", "") or "Unknown"
        for _, e in approved
    })
    all_work_modes = sorted({
        e["listing"].get("work_mode", "") or "Unknown"
        for _, e in approved
    })
    all_relevance = sorted({
        e["listing"].get("relevance_tag", "") or "Unknown"
        for _, e in approved
    })

    selected_relevance = st.sidebar.multiselect("Relevance", all_relevance, default=[], key="pb_rel")
    selected_orgs = st.sidebar.multiselect("Organization", all_orgs, default=[], key="pb_orgs")
    selected_seniority = st.sidebar.multiselect("Seniority", all_seniority, default=[], key="pb_sen")
    selected_work_modes = st.sidebar.multiselect("Work Mode", all_work_modes, default=[], key="pb_wm")
    location_search = st.sidebar.text_input("Location search", key="pb_loc")

    # Apply filters
    filtered = approved
    if selected_relevance:
        filtered = [
            (fp, e) for fp, e in filtered
            if (e["listing"].get("relevance_tag") or "Unknown") in selected_relevance
        ]
    if selected_orgs:
        filtered = [(fp, e) for fp, e in filtered if e["listing"].get("organization") in selected_orgs]
    if selected_seniority:
        filtered = [
            (fp, e) for fp, e in filtered
            if (e["listing"].get("seniority_level") or "Unknown") in selected_seniority
        ]
    if selected_work_modes:
        filtered = [
            (fp, e) for fp, e in filtered
            if (e["listing"].get("work_mode") or "Unknown") in selected_work_modes
        ]
    if location_search:
        search_lower = location_search.lower()
        filtered = [
            (fp, e) for fp, e in filtered
            if search_lower in (e["listing"].get("location") or "").lower()
        ]

    st.write(f"**{len(filtered)}** approved listings match filters")

    # Checkboxes for selection
    selected_fps = []
    for fp, entry in filtered:
        listing_data = entry["listing"]
        title = listing_data.get("title", "Unknown")
        org = listing_data.get("organization", "Unknown")
        location = listing_data.get("location") or ""
        loc_str = f" ({location})" if location else ""

        if st.checkbox(f"{title} — {org}{loc_str}", key=f"sel_{fp}"):
            selected_fps.append(fp)

    st.write(f"**{len(selected_fps)}** selected")

    if selected_fps:
        btn_col1, btn_col2 = st.columns(2)
        roundup_clicked = btn_col1.button(
            "\U0001f4dd Generate Roundup Post",
            disabled=len(selected_fps) == 0,
            use_container_width=True,
        )
        spotlight_clicked = btn_col2.button(
            "\u2728 Generate Spotlight Post",
            disabled=len(selected_fps) != 1,
            help="Select exactly one listing to generate a spotlight post",
            use_container_width=True,
        )

        if roundup_clicked:
            with st.spinner(f"Verifying {len(selected_fps)} listing(s) are still open..."):
                url_results = _check_listings_open(selected_fps, store)

            closed_fps = []
            for fp in selected_fps:
                status_val, reason = url_results[fp]
                title = store[fp]["listing"].get("title", "?")
                org = store[fp]["listing"].get("organization", "?")
                icon = "\u2705" if status_val == "open" else "\u274c" if status_val == "closed" else "\u2753"
                st.write(f"{icon} **{title}** — {org}: *{reason}*")
                if status_val == "closed":
                    closed_fps.append(fp)

            active_fps = [fp for fp in selected_fps if fp not in closed_fps]

            if not active_fps:
                st.error("All selected listings appear to be closed. No post generated.")
            else:
                if closed_fps:
                    st.warning(
                        f"{len(closed_fps)} listing(s) appear closed and were excluded. "
                        f"Generating post with {len(active_fps)} active listing(s)."
                    )
                listings = [JobListing.from_dict(store[fp]["listing"]) for fp in active_fps]
                with st.spinner(f"Writing roundup post for {len(listings)} listing(s)..."):
                    post_content = _generate_themed_post(listings)
                # draft_editor not yet rendered — safe to set directly
                st.session_state.draft_editor = post_content
                st.session_state.draft_label = f"Roundup ({len(active_fps)} listings)"

        if spotlight_clicked:
            fp = selected_fps[0]
            listing_data = store[fp]["listing"]
            title = listing_data.get("title", "?")
            org = listing_data.get("organization", "?")

            with st.spinner(f"Verifying listing is still open..."):
                status_val, reason = _check_listing_url(listing_data.get("url", ""))

            if status_val == "closed":
                st.error(f"This listing appears to be closed ({reason}). Spotlight not generated.")
            else:
                if status_val == "unknown":
                    st.warning(f"Could not verify listing status ({reason}) — generating anyway.")
                with st.spinner(f"Writing spotlight for {title} — {org}..."):
                    listing_obj = JobListing.from_dict(listing_data)
                    post_content = _generate_spotlight_post(listing_obj)
                if post_content:
                    # draft_editor not yet rendered — safe to set directly
                    st.session_state.draft_editor = post_content
                    st.session_state.draft_label = f"Spotlight: {title} \u2014 {org}"
                else:
                    st.error("Spotlight generation failed — is ANTHROPIC_API_KEY set?")

    # ------------------------------------------------------------------
    # Current draft — persists across checkbox/filter changes via session state
    # ------------------------------------------------------------------

    # _pending_load is set by the Load button (which renders after the text
    # area, so it can't write draft_editor directly). Apply it here, before
    # the widget is rendered, so the new content is picked up cleanly.
    if "_pending_load" in st.session_state:
        st.session_state.draft_editor = st.session_state.pop("_pending_load")
        st.session_state.draft_label = st.session_state.pop("_pending_label", "Draft")

    if st.session_state.get("draft_editor"):
        st.markdown("---")
        label = st.session_state.get("draft_label", "Draft")
        st.subheader(f"\U0001f4c4 {label}")

        st.text_area("Edit before posting to LinkedIn", key="draft_editor", height=500)

        save_col, dl_col, clear_col = st.columns(3)
        if save_col.button("\U0001f4be Save Draft", use_container_width=True):
            path = _save_draft_to_disk(
                st.session_state.draft_editor,
                st.session_state.get("draft_label", "draft"),
            )
            st.success(f"Saved to {path.name}")
        dl_col.download_button(
            "\U0001f4e5 Download",
            st.session_state.draft_editor,
            file_name=f"draft_{date.today().isoformat()}.md",
            mime="text/markdown",
            use_container_width=True,
        )
        if clear_col.button("\U0001f5d1\ufe0f Clear Draft", use_container_width=True):
            del st.session_state.draft_editor
            st.session_state.pop("draft_label", None)
            st.rerun()

    # ------------------------------------------------------------------
    # Saved drafts browser
    # ------------------------------------------------------------------
    saved = _list_saved_drafts()
    if saved:
        st.markdown("---")
        st.subheader("\U0001f4c2 Saved Drafts")
        for draft_path in saved:
            col_name, col_load, col_delete = st.columns([6, 1, 1])
            col_name.write(draft_path.stem)
            if col_load.button("Load", key=f"load_{draft_path.name}", use_container_width=True):
                # Can't set draft_editor here — widget already rendered above.
                # Use _pending_load flag; it will be applied on the next run.
                st.session_state._pending_load = draft_path.read_text(encoding="utf-8")
                st.session_state._pending_label = draft_path.stem
                st.rerun()
            if col_delete.button("Del", key=f"del_{draft_path.name}", use_container_width=True):
                draft_path.unlink()
                st.rerun()


DRAFTS_DIR = Path(__file__).parent.parent / "data" / "drafts"


def _save_draft_to_disk(content: str, label: str) -> Path:
    """Save draft content to data/drafts/ and return the path."""
    from datetime import datetime
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = "spotlight" if label.lower().startswith("spotlight") else "roundup"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = DRAFTS_DIR / f"{timestamp}_{slug}.md"
    path.write_text(content, encoding="utf-8")
    return path


def _list_saved_drafts() -> list[Path]:
    """Return saved draft files sorted newest first."""
    if not DRAFTS_DIR.exists():
        return []
    return sorted(DRAFTS_DIR.glob("*.md"), reverse=True)


def _check_listing_url(url: str) -> tuple[str, str]:
    """Check whether a job listing URL is still active.

    Returns (status, reason) where status is 'open', 'closed', or 'unknown'.
    """
    if not url:
        return "unknown", "No URL"
    try:
        resp = requests.get(
            url, timeout=8, allow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; job-checker/1.0)"},
        )
        if resp.status_code == 404:
            return "closed", "404 — page not found"
        if resp.status_code >= 400:
            return "unknown", f"HTTP {resp.status_code}"

        text = resp.text.lower()
        closed_phrases = [
            "this job is no longer available",
            "this position has been filled",
            "no longer accepting applications",
            "this role is no longer available",
            "position has been closed",
            "posting is no longer active",
            "job has been filled",
            "position is filled",
            "this opening is no longer available",
            "this position is no longer open",
        ]
        for phrase in closed_phrases:
            if phrase in text:
                return "closed", "Page indicates position is filled"

        return "open", "Listing appears active"
    except requests.exceptions.ConnectionError:
        return "unknown", "Could not connect"
    except requests.exceptions.Timeout:
        return "unknown", "Request timed out"
    except Exception as e:
        return "unknown", str(e)[:80]


def _check_listings_open(fps: list[str], store: dict) -> dict[str, tuple[str, str]]:
    """Check multiple listing URLs in parallel. Returns {fp: (status, reason)}."""
    def check_one(fp):
        url = store[fp]["listing"].get("url", "")
        return fp, _check_listing_url(url)

    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_one, fp): fp for fp in fps}
        for future in as_completed(futures):
            fp, result = future.result()
            results[fp] = result
    return results


def _generate_spotlight_post(listing: JobListing) -> str | None:
    """Generate a LinkedIn spotlight post for a single listing using Claude.

    Follows the Jonas Freund format:
      opening hook
      emoji fact block (dates, location, salary, deadline, link)
      ▶︎ About the role
      ▶︎ About the org
      ▶︎ Should you apply?
      hashtags
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    import anthropic

    description = listing.description or listing.description_snippet or "(no description available)"
    description = description[:3000]

    salary = listing.salary_range or "Not specified"
    location = listing.location or "Not specified"
    role_type = listing.role_type or "Role"
    deadline = listing.date_closes.strftime("%B %-d, %Y") if listing.date_closes else None

    prompt = f"""Write a LinkedIn spotlight post for the job listing below. Follow this format exactly:

[One punchy opening sentence introducing the opportunity. End with: "Feel free to share or tag someone who might be a great fit."]

[Emoji fact block — include only lines where the info is actually known:]
📅 When? [dates/duration if known]
📍 Where? [location]
💵 Salary: [amount + any benefits if known]
⚠️ Deadline: [deadline if known]
🔗 Learn more: [URL]

▶︎ About the {role_type}
[2–4 sentences: what the person will do, what makes this role interesting or impactful]

▶︎ About {listing.organization}
[2–3 sentences: org mission, why it matters for AI safety/governance/biosecurity]

▶︎ Should you apply?
[2–3 sentences: encourage anyone motivated to reduce catastrophic or existential risks from AI or bioweapons to apply; keep it general and welcoming]

#AIGovernance #AIPolicy #AISafety #TechPolicy #Careers

---
Listing details:
Title: {listing.title}
Organization: {listing.organization}
Location: {location}
Salary: {salary}
{"Deadline: " + deadline if deadline else ""}
URL: {listing.url}
Description:
{description}
---
Rules:
- Never use "we", "our", "us", or "I" — the post is written by a third party sharing the opportunity, not by the hiring org. Refer to the organization by name (e.g. "GovAI is hiring" or "Applications are open for...")
- Omit any emoji fact line if the information is not present in the listing
- Do not invent specific details (salary figures, dates, benefits) not in the description
- Keep the ▶︎ headers exactly as shown
- The tone should be warm, clear, and professional — not hype-y"""

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception:
        return None


def _format_listing_bullet(listing: JobListing) -> str:
    """Format a single listing as a bullet line for the roundup post."""
    header = f"{listing.title} \u2014 {listing.organization}"
    if listing.location:
        header += f" ({listing.location})"

    details = []
    if listing.work_mode:
        details.append(listing.work_mode)
    if listing.seniority_level:
        details.append(listing.seniority_level)
    if listing.salary_range:
        details.append(listing.salary_range)
    if listing.visa_sponsorship is True:
        details.append("Visa \u2713")
    elif listing.visa_sponsorship is False:
        details.append("Visa \u2717")
    if listing.date_closes:
        details.append(f"Closes {listing.date_closes.strftime('%b %-d')}")

    line = "\u2022 " + header
    if details:
        line += " | " + " | ".join(details)
    line += f"\n  {listing.url}"
    return line


def _generate_themed_post(listings: list[JobListing]) -> str:
    """Generate a LinkedIn roundup post using Claude, falling back to plain template."""
    bullets = "\n\n".join(_format_listing_bullet(l) for l in listings)

    fallback = (
        "\U0001f50d AI Governance Job Roundup\n\n"
        f"{len(listings)} curated role{'s' if len(listings) != 1 else ''}:\n\n"
        f"{bullets}\n\n"
        "#AIGovernance #AIPolicy #AISafety #TechPolicy #Careers"
    )

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return fallback

    import anthropic

    prompt = f"""Write a LinkedIn roundup post for these AI governance/policy job listings.

Your tasks:
1. Write 1–2 sentences of engaging intro prose that captures the theme of this specific batch (e.g. a wave of biosecurity roles, technical alignment positions, policy fellowships, or a mix — infer from the listings below)
2. Follow immediately with a concise summary line (e.g. "8 curated roles spanning biosecurity and AI governance" — use the actual count and reflect the actual subfield mix)
3. Then reproduce the job listing bullets exactly as provided — preserve all fields, formatting, and URLs

Output format:
🔍 AI Governance Job Roundup

[1–2 sentences of intro prose]
[Summary line]

[job listing bullets]

#AIGovernance #AIPolicy #AISafety #TechPolicy #Careers

---
Job listings ({len(listings)} total):
{bullets}"""

    try:
        client = anthropic.Anthropic()
        message = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()
    except Exception:
        return fallback


# ---------------------------------------------------------------------------
# Git push helper
# ---------------------------------------------------------------------------

def _git_push():
    """Commit and push listings.json changes."""
    try:
        result = subprocess.run(
            ["git", "add", "data/listings.json"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        if result.returncode != 0:
            st.sidebar.error(f"git add failed: {result.stderr}")
            return

        result = subprocess.run(
            ["git", "commit", "-m", "Update listing reviews"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        if result.returncode != 0:
            if "nothing to commit" in result.stdout:
                st.sidebar.info("No changes to commit.")
                return
            st.sidebar.error(f"git commit failed: {result.stderr}")
            return

        result = subprocess.run(
            ["git", "push"],
            capture_output=True, text=True, cwd=Path(__file__).parent.parent,
        )
        if result.returncode != 0:
            st.sidebar.error(f"git push failed: {result.stderr}")
            return

        st.sidebar.success("Changes pushed to GitHub!")
    except Exception as e:
        st.sidebar.error(f"Git operation failed: {e}")


if __name__ == "__main__":
    main()
