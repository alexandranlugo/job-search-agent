#!/bin/bash
# Daily job search pipeline
# Intended to run once a morning via cron — see README for the crontab line.

# Resolve the repo root from this script's own location, so the pipeline works
# from any checkout and from cron (which does not inherit your shell's cwd).
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR" || exit 1

# Override with PYTHON=/path/to/python if you use a venv or conda env.
PYTHON="${PYTHON:-python3}"

mkdir -p "$REPO_DIR/logs"
LOG="$REPO_DIR/logs/pipeline_$(date +%Y-%m-%d).log"

echo "===== Pipeline started: $(date) =====" >> "$LOG"

echo "Step 1: Scraping Built In NYC..." >> "$LOG"
"$PYTHON" ingestion/scrape_builtinnyc.py --pages=25 >> "$LOG" 2>&1

echo "Step 2: Scraping target companies..." >> "$LOG"
"$PYTHON" ingestion/scrape_greenhouse.py >> "$LOG" 2>&1

echo "Step 3: Scoring filtered postings..." >> "$LOG"
"$PYTHON" scoring/evaluate.py >> "$LOG" 2>&1

echo "Step 4: Generating digest..." >> "$LOG"
"$PYTHON" output/digest.py >> "$LOG" 2>&1

echo "Step 5: Sending email..." >> "$LOG"
"$PYTHON" output/send_email.py >> "$LOG" 2>&1

echo "===== Pipeline complete: $(date) =====" >> "$LOG"
echo "Done. Check output/digests/ for today's digest."
