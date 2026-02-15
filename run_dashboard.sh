#!/bin/bash
# Pull latest scraped data from GitHub Actions, then launch the dashboard.
git pull origin main
streamlit run src/dashboard.py
