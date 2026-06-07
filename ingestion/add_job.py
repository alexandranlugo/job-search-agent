"""
ingestion/add_job.py
Manually add any job URL to the pipeline for scoring and resume generation.
Works for Wellfound, LinkedIn, or any job posting.
Usage: python ingestion/add_job.py <url>
"""

import sqlite3, hashlib, os, sys
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")


def url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()


def fetch_job(url):
    print(f"Fetching: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page    = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        title    = ""
        company  = ""
        location = ""

        # Try common selectors for job title
        for selector in ["h1", "[data-test='job-title']", ".job-title", "title"]:
            el = page.query_selector(selector)
            if el:
                title = el.inner_text().strip()
                if len(title) > 3 and len(title) < 150:
                    break

        raw_text = page.inner_text("main, article, body")[:8000]
        browser.close()

    return title, company, location, raw_text


def add_job(url, title=None, company=None, location=None):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Check if already exists
    existing = cur.execute(
        "SELECT id, title FROM postings WHERE url_hash = ?",
        (url_hash(url),)
    ).fetchone()

    if existing:
        print(f"Already in pipeline: {existing[1]}")
        con.close()
        return existing[0]

    if not title:
        fetched_title, fetched_company, fetched_location, raw_text = fetch_job(url)
        title    = title    or fetched_title    or "Unknown Title"
        company  = company  or fetched_company  or "Unknown Company"
        location = location or fetched_location or ""
    else:
        _, _, _, raw_text = fetch_job(url)

    cur.execute("""
        INSERT INTO postings (url, url_hash, company, title, location, raw_text, source, filtered_in)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (url, url_hash(url), company, title, location, raw_text, "manual", 1))
    con.commit()
    posting_id = cur.lastrowid
    con.close()

    print(f"Added: {title} — {company}")
    print(f"Posting ID: {posting_id}")
    print(f"Now run: python scoring/evaluate.py")
    return posting_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ingestion/add_job.py <url> [title] [company] [location]")
        print("Example: python ingestion/add_job.py https://wellfound.com/jobs/123 'Data Analyst' 'Spotify' 'New York'")
        sys.exit(1)

    url      = sys.argv[1]
    title    = sys.argv[2] if len(sys.argv) > 2 else None
    company  = sys.argv[3] if len(sys.argv) > 3 else None
    location = sys.argv[4] if len(sys.argv) > 4 else None

    add_job(url, title, company, location)
