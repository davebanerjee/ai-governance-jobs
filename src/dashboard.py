"""Streamlit dashboard for reviewing job listings and building LinkedIn posts."""

from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import streamlit as st

from src.listing_store import (
    DEFAULT_LISTINGS_PATH,
    load_listings,
    save_listings,
    update_review_status,
)
from src.models import JobListing
from src.post_generator import categorize_listing, CATEGORY_ICONS, CATEGORY_ORDER

st.set_page_config(page_title="AI Governance Jobs", page_icon="\U0001f50d", layout="wide")


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

    st.sidebar.markdown("### Filters")
    selected_orgs = st.sidebar.multiselect("Organization", all_orgs, default=[])
    selected_work_modes = st.sidebar.multiselect("Work Mode", all_work_modes, default=[])
    selected_seniority = st.sidebar.multiselect("Seniority", all_seniority, default=[])

    # Apply filters
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
            if st.button("\u2705 Approve All Visible"):
                for fp, _ in entries:
                    update_review_status(fp, "relevant")
                st.rerun()
        with col2:
            if st.button("\u274c Reject All Visible"):
                for fp, _ in entries:
                    update_review_status(fp, "irrelevant")
                st.rerun()

    # Reset button for reviewed listings
    if entries and status_filter in ("relevant", "irrelevant"):
        if st.button("\U0001f504 Reset All Visible to Unreviewed"):
            for fp, _ in entries:
                update_review_status(fp, "unreviewed")
            st.rerun()

    # Display listings — buttons inline, details in expander
    for fp, entry in entries:
        listing_data = entry["listing"]
        title = listing_data.get("title", "Unknown")
        org = listing_data.get("organization", "Unknown")
        location = listing_data.get("location") or ""
        status = entry["review_status"]

        status_icon = {"unreviewed": "\u2753", "relevant": "\u2705", "irrelevant": "\u274c"}.get(status, "")
        loc_str = f" \u2022 {location}" if location else ""

        # Row: buttons | title summary
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
            with st.expander(f"{status_icon} **{title}** — {org}{loc_str}"):
                work_mode = listing_data.get("work_mode") or "Unknown"
                seniority = listing_data.get("seniority_level") or "Unknown"
                visa = listing_data.get("visa_sponsorship")
                visa_str = "Yes" if visa is True else "No" if visa is False else "Unknown"
                salary = listing_data.get("salary_range") or "Not listed"
                source = listing_data.get("source", "")
                url = listing_data.get("url", "")

                st.markdown(f"""
| Field | Value |
|-------|-------|
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

    selected_orgs = st.sidebar.multiselect("Organization", all_orgs, default=[], key="pb_orgs")
    selected_seniority = st.sidebar.multiselect("Seniority", all_seniority, default=[], key="pb_sen")
    selected_work_modes = st.sidebar.multiselect("Work Mode", all_work_modes, default=[], key="pb_wm")
    location_search = st.sidebar.text_input("Location search", key="pb_loc")

    # Apply filters
    filtered = approved
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
        # Convert selected entries to JobListing objects
        listings = []
        for fp in selected_fps:
            entry = store[fp]
            listing = JobListing.from_dict(entry["listing"])
            listings.append(listing)

        post_content = _generate_themed_post(listings)
        st.text_area("Generated Post", post_content, height=400)

        # Download button
        st.download_button(
            "\U0001f4e5 Download as Markdown",
            post_content,
            file_name=f"linkedin_post_{date.today().isoformat()}.md",
            mime="text/markdown",
        )


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
