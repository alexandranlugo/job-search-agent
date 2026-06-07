#!/bin/bash
# Daily job search pipeline
# Runs at 7:00 AM every morning

cd /Users/alugo/job-search-agent

LOG="/Users/alugo/job-search-agent/logs/pipeline_$(date +%Y-%m-%d).log"

echo "===== Pipeline started: $(date) =====" >> "$LOG"

echo "Step 1: Scraping Built In NYC..." >> "$LOG"
/Users/alugo/anaconda3/bin/python ingestion/scrape_builtinnyc.py --pages=10 >> "$LOG" 2>&1

echo "Step 2: Scraping target companies..." >> "$LOG"
/Users/alugo/anaconda3/bin/python ingestion/scrape_greenhouse.py >> "$LOG" 2>&1

echo "Step 3: Scoring filtered postings..." >> "$LOG"
/Users/alugo/anaconda3/bin/python scoring/evaluate.py >> "$LOG" 2>&1

echo "Step 4: Generating digest..." >> "$LOG"
/Users/alugo/anaconda3/bin/python output/digest.py >> "$LOG" 2>&1

echo "Step 5: Sending email..." >> "$LOG"
/Users/alugo/anaconda3/bin/python output/send_email.py >> "$LOG" 2>&1

echo "===== Pipeline complete: $(date) =====" >> "$LOG"
echo "Done. Check output/digests/ for today's digest."
