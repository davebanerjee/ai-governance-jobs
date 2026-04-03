"""Streamlit dashboard for reviewing job listings and building LinkedIn posts."""

from __future__ import annotations

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
from src.post_generator import categorize_listing, CATEGORY_ICONS, CATEGORY_ORDER

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
    if st.sidebar.button("\U0001f4e4 Save & Push to GitHub"):
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

    if selected_fps and st.button("\U0001f4dd Generate LinkedIn Post"):
        # Check all selected URLs in parallel before generating
        with st.spinner(f"Verifying {len(selected_fps)} listing(s) are still open..."):
            url_results = _check_listings_open(selected_fps, store)

        # Show per-listing check results
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
            post_content = _generate_themed_post(listings)
            st.text_area("Generated Post", post_content, height=400)

            st.download_button(
                "\U0001f4e5 Download as Markdown",
                post_content,
                file_name=f"linkedin_post_{date.today().isoformat()}.md",
                mime="text/markdown",
            )


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


def _generate_themed_post(listings: list[JobListing]) -> str:
    """Generate a LinkedIn post from selected listings."""
    today = date.today()
    week_str = today.strftime("%B %d, %Y")

    # Group by category
    categories: dict[str, list[JobListing]] = {cat: [] for cat in CATEGORY_ORDER}
    for listing in listings:
        cat = categorize_listing(listing)
        categories[cat].append(listing)

    for cat in categories:
        categories[cat].sort(key=lambda x: x.organization.lower())

    lines = []
    lines.append(f"\U0001f50d AI Governance Job Roundup \u2014 Week of {week_str}\n")
    lines.append(
        f"{len(listings)} curated role{'s' if len(listings) != 1 else ''} "
        "in AI governance, policy, and safety:\n"
    )

    for cat in CATEGORY_ORDER:
        cat_listings = categories[cat]
        if not cat_listings:
            continue

        icon = CATEGORY_ICONS[cat]
        lines.append(f"{icon} {cat.upper()}")

        for listing in cat_listings:
            loc = f" ({listing.location})" if listing.location else ""
            salary = f" | {listing.salary_range}" if listing.salary_range else ""
            closing = ""
            if listing.date_closes:
                closing = f" | Closes {listing.date_closes.strftime('%b %d')}"

            lines.append(f"\u2022 {listing.title} \u2014 {listing.organization}{loc}{salary}{closing}")
            lines.append(f"  {listing.url}")

        lines.append("")

    lines.append("---")

    source_count = len(set(l.source for l in listings))
    lines.append(f"Sources: 80,000 Hours + {source_count} org career pages")
    lines.append("\n#AIGovernance #AIPolicy #AISafety #TechPolicy #Careers")

    return "\n".join(lines)


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
