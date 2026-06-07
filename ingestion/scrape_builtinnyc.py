"""
ingestion/scrape_builtinnyc.py
Scrapes Data & Analytics job postings from Built In NYC with full job descriptions.
Usage: python ingestion/scrape_builtinnyc.py [--pages=N]
"""

import sqlite3, hashlib, os, sys
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH  = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
BASE_URL = "https://builtin.com/jobs/nyc/data-analytics?page={}"

POSITIVE_KEYWORDS = [
    "data analyst", "product analyst", "insights analyst", "growth analyst",
    "business analyst", "analytics engineer", "bi analyst", "junior data scientist",
    "storytelling analyst", "marketing analyst", "decision analytics",
    "analyst", "analytics", "intelligence analyst", "data scientist",
    "data specialist", "data insights"
]

NEGATIVE_KEYWORDS = [
    "senior", "sr.", "sr ", "principal", "director", "manager", "lead",
    "head of", "vp ", "vice president", "architect", "expert",
    "staff engineer", "staff data engineer", "staff software"
]

LOCATION_KEYWORDS = ["new york", "nyc", "remote", "hybrid", "usa"]


NON_NYC_CITIES = [
    "boston", "chicago", "san francisco", "seattle", "austin",
    "los angeles", "atlanta", "denver", "dallas", "phoenix",
    "miami", "boise", "stamford", "littleton", "long beach", "denver", "englewood"
]

def passes_filters(title, location):
    title_lower = title.lower()
    location_lower = location.lower() if location else ""

    if not any(k in title_lower for k in POSITIVE_KEYWORDS):
        return False
    if any(k in title_lower for k in NEGATIVE_KEYWORDS):
        return False
    if not any(k in location_lower for k in LOCATION_KEYWORDS):
        return False

    # Reject non-NYC cities unless remote is explicitly mentioned
    if "remote" not in location_lower:
        if any(city in location_lower for city in NON_NYC_CITIES):
            return False

    return True


def url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()

def is_duplicate_title(cur, company, title):
    import re
    def normalize(s):
        s = s.lower()
        s = re.sub(r"[^a-z0-9 ]", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s
    normalized = normalize(title)
    existing = cur.execute(
        "SELECT title FROM postings WHERE company = ? AND filtered_in = 1",
        (company,)
    ).fetchall()
    for row in existing:
        if normalize(row[0]) == normalized:
            return True
    return False


def fetch_full_description(page, url):
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        desc_el = page.query_selector('[data-id="job-description"]')
        if desc_el:
            return desc_el.inner_text().strip()
        for selector in ["#job-description", ".job-description", "article", "main"]:
            el = page.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                if len(text) > 200:
                    return text
        return page.inner_text("body")[:3000]
    except Exception as e:
        print(f"    Could not fetch description: {e}")
        return ""


def save_posting(cur, posting):
    try:
        cur.execute("""
            INSERT INTO postings
                (url, url_hash, company, title, location, raw_text, source, filtered_in)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            posting["url"],
            url_hash(posting["url"]),
            posting["company"],
            posting["title"],
            posting["location"],
            posting["raw_text"],
            "builtinnyc",
            1 if posting["filtered_in"] else 0
        ))
        return True
    except sqlite3.IntegrityError:
        return False


def scrape(max_pages=10):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    new_total    = 0
    passed_filter = 0

    with sync_playwright() as p:
        browser  = p.chromium.launch(headless=True)
        list_page = p.chromium.launch(headless=True).new_page()
        desc_page = browser.new_page()

        for page_num in range(1, max_pages + 1):
            url = BASE_URL.format(page_num)
            print(f"\nPage {page_num}: {url}")

            list_page.goto(url, wait_until="networkidle", timeout=60000)
            list_page.wait_for_timeout(2000)
            for _ in range(3):
                list_page.keyboard.press("End")
                list_page.wait_for_timeout(1000)

            job_cards = list_page.query_selector_all('[data-id="job-card"]')
            print(f"  Found {len(job_cards)} job cards")

            if not job_cards:
                print("  No cards found, stopping.")
                break

            new_on_page = 0

            for card in job_cards:
                try:
                    title_el = card.query_selector('[data-id="job-card-title"]')
                    if not title_el:
                        continue

                    title = title_el.inner_text().strip()
                    href  = title_el.get_attribute("href") or ""
                    posting_url = href if href.startswith("http") else "https://builtin.com" + href

                    card_text = card.inner_text().strip()
                    lines     = [l.strip() for l in card_text.split("\n") if l.strip()]
                    company   = lines[0] if lines else "Unknown"

                    location = ""
                    for line in lines:
                        if any(k in line.lower() for k in ["new york", "nyc", "remote", "hybrid", "usa"]):
                            location = line
                            break

                    filtered = passes_filters(title, location)
                    status   = "PASS" if filtered else "skip"
                    print(f"  [{status}] {title} — {company} ({location})")

                    if filtered:
                        print(f"    Fetching full description...")
                        full_text = fetch_full_description(desc_page, posting_url)
                        raw_text  = full_text if full_text else card_text
                        # Re-check location against full description text
                        full_lower = raw_text.lower()
                        # Only check first 600 chars for remote — avoids company boilerplate
                        top_lower = full_lower[:600]
                        has_remote = (
                            "remote" in top_lower or
                            "work from anywhere" in top_lower or
                            "fully remote" in full_lower[:300]
                        )
                        has_non_nyc = any(city in full_lower for city in NON_NYC_CITIES)
                        if has_non_nyc and not has_remote:
                            print(f"    Skipping — non-NYC city found in description")
                            filtered = False
                        else:
                            passed_filter += 1
                    else:
                        raw_text = card_text

                    posting = {
                        "url":         posting_url,
                        "company":     company,
                        "title":       title,
                        "location":    location,
                        "raw_text":    raw_text,
                        "filtered_in": filtered
                    }
                    
                    if filtered and is_duplicate_title(cur, company, title):
                        print(f"  [DEDUP] {title} — {company}")
                        continue
                    
                    is_new = save_posting(cur, posting)
                    if is_new:
                        new_total += 1
                        new_on_page += 1

                except Exception as e:
                    print(f"    Error: {e}")
                    continue

            con.commit()

            if new_on_page == 0:
                print("  No new postings, stopping.")
                break

        browser.close()

    con.close()
    print(f"\nDone. {new_total} new postings saved. {passed_filter} passed filters with full descriptions.")


if __name__ == "__main__":
    max_pages = 10
    for arg in sys.argv[1:]:
        if arg.startswith("--pages="):
            max_pages = int(arg.split("=")[1])
    scrape(max_pages=max_pages)
# This block is intentionally empty - see passes_filters rewrite below
