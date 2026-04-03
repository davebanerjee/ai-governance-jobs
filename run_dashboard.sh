#!/bin/bash
# Pull latest scraped data from GitHub Actions, then launch the dashboard.
cd "$(dirname "$0")"

# Load .env if present (e.g. ANTHROPIC_API_KEY=sk-ant-...)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

git pull origin main
PYTHONPATH="$(pwd)" streamlit run src/dashboard.py
