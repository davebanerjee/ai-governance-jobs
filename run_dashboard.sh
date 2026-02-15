#!/bin/bash
# Pull latest scraped data from GitHub Actions, then launch the dashboard.
cd "$(dirname "$0")"
git pull origin main
PYTHONPATH="$(pwd)" streamlit run src/dashboard.py
