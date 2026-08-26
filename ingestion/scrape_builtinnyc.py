"""
ingestion/scrape_builtinnyc.py
Scrapes Data & Analytics job postings from Built In NYC with full job descriptions.
Usage: python ingestion/scrape_builtinnyc.py [--pages=N]
"""

import sqlite3, hashlib, os, sys
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

import re
from datetime import datetime, timedelta, timezone

def parse_age(card_text):
    m = re.search(r"(\d+)\s+days?\s+ago", card_text, re.I)
    if m:
        return (datetime.now(timezone.utc) - timedelta(days=int(m.group(1)))).isoformat()
    if re.search(r"\byesterday\b", card_text, re.I):
        return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    if re.search(r"(hours?|minutes?)\s+ago|today|just posted", card_text, re.I):
        return datetime.now(timezone.utc).isoformat()
    return ""

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
    "staff", " ii", " iii", " iv", "deal desk", "aml", "compliance", "payroll", "procurement", "purchasing",
    "compensation", "fp&a", "financial planning", "employee lifecycle",
    "sales operations", "order operations", "corporate development", "revenue strategy",
    "pricing","sales revenue"
]

LOCATION_KEYWORDS = ["new york", "nyc", "remote", "hybrid", "usa"]


NON_NYC_CITIES = [
    "boston", "chicago", "san francisco", "seattle", "austin",
    "los angeles", "atlanta", "denver", "dallas", "phoenix",
    "miami", "boise", "stamford", "littleton", "long beach", "denver", "englewood"
]

NYC_TOKENS = ["new york", "nyc", ", ny", "brooklyn", "manhattan"]

# BuiltIn tags each card with an explicit level ("Entry level", "Junior", "Mid
# level", "Senior level", "Expert/Leader") — a more reliable seniority signal
# than scanning the title text alone, since plenty of senior roles have plain
# titles ("Analyst, Advanced Analytics") that the title keyword filter misses.
KNOWN_SENIORITY_TAGS = {"entry level", "junior", "mid level", "senior level", "expert/leader"}
REJECT_SENIORITY_TAGS = {"senior level", "expert/leader"}

def extract_seniority_tag(lines):
    if lines and lines[-1].strip().lower() in KNOWN_SENIORITY_TAGS:
        return lines[-1].strip().lower()
    return ""

def passes_filters(title, location, seniority_tag=""):
    title_lower = title.lower()
    location_lower = location.lower() if location else ""

    if seniority_tag in REJECT_SENIORITY_TAGS:
        return False
    if not any(k in title_lower for k in POSITIVE_KEYWORDS):
        return False
    if any(k in title_lower for k in NEGATIVE_KEYWORDS):
        return False

    if any(k in location_lower for k in NYC_TOKENS):
        return True
    if any(city in location_lower for city in NON_NYC_CITIES):
        return False
    if "remote" in location_lower:
        # Candidate profile is explicitly open to remote-only, regardless of city.
        return True
    # A bare "Hybrid" tag (no city) means hybrid-at-HQ, which usually isn't NYC.
    return False


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
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
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
                (url, url_hash, company, title, location, raw_text, source, posted_at, filtered_in)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            posting["url"],
            url_hash(posting["url"]),
            posting["company"],
            posting["title"],
            posting["location"],
            posting["raw_text"],
            posting["source"],
            posting.get("posted_at", ""),
            1 if posting["filtered_in"] else 0
        ))
        return True
    except sqlite3.IntegrityError:
        if posting["filtered_in"]:
            cur.execute("""
                UPDATE postings SET filtered_in = 1, raw_text = ?, posted_at = ?
                WHERE url = ? AND filtered_in = 0
            """, (posting["raw_text"][:8000], posting.get("posted_at", ""), posting["url"]))
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

            try:
                list_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                list_page.wait_for_selector('[data-id="job-card"]', timeout=15000)
            except Exception as e:
                print(f"  Could not load page {page_num}: {type(e).__name__}: {e}")
                print("  Skipping this page, trying the next one.")
                continue

            list_page.wait_for_timeout(2000)
            for _ in range(3):
                list_page.keyboard.press("End")
                list_page.wait_for_timeout(1000)

            job_cards = list_page.query_selector_all('[data-id="job-card"]')
            print(f"  Found {len(job_cards)} job cards")

            if not job_cards:
                print("  No cards found, stopping.")
                break

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
                    posted_at = parse_age(card_text)
                    seniority_tag = extract_seniority_tag(lines)

                    location = ""
                    for line in lines:
                        if any(k in line.lower() for k in ["new york", "nyc", "remote", "hybrid", "usa"]):
                            location = line
                            break

                    filtered = passes_filters(title, location, seniority_tag)
                    status   = "PASS" if filtered else "skip"
                    tag_note = f" [{seniority_tag}]" if seniority_tag else ""
                    print(f"  [{status}] {title} — {company} ({location}){tag_note}")

                    if filtered:
                        print(f"    Fetching full description...")
                        full_text = fetch_full_description(desc_page, posting_url)
                        raw_text  = full_text if full_text else card_text
                        # Re-check location against full description text
                        passed_filter += 1
                    else:
                        raw_text = card_text

                    posting = {
                        "url":         posting_url,
                        "company":     company,
                        "title":       title,
                        "location":    location,
                        "raw_text":    raw_text,
                        "source":      "builtinnyc",
                        "filtered_in": filtered,
                        "posted_at":   posted_at
                    }
                    
                    if filtered and is_duplicate_title(cur, company, title):
                        print(f"  [DEDUP] {title} — {company}")
                        continue
                    
                    is_new = save_posting(cur, posting)
                    if is_new:
                        new_total += 1

                except Exception as e:
                    print(f"    Error: {type(e).__name__}: {e}")
                    continue

            con.commit()

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
