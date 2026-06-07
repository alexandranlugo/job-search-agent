"""
ingestion/scrape_wellfound.py
Scrapes job postings from Wellfound (formerly AngelList) with login.
Usage: python ingestion/scrape_wellfound.py [--pages=N]
"""

import sqlite3, hashlib, os, sys
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH  = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
EMAIL    = os.getenv("WELLFOUND_EMAIL")
PASSWORD = os.getenv("WELLFOUND_PASSWORD")

SEARCH_URLS = [
    "https://wellfound.com/jobs?role=Data+Analyst&location=New+York+City",
    "https://wellfound.com/jobs?role=Product+Analyst&location=New+York+City",
    "https://wellfound.com/jobs?role=Data+Analyst&location=Remote",
    "https://wellfound.com/jobs?role=Product+Analyst&location=Remote",
]

POSITIVE_KEYWORDS = [
    "data analyst", "product analyst", "insights analyst", "growth analyst",
    "business analyst", "analytics engineer", "bi analyst", "junior data scientist",
    "storytelling analyst", "marketing analyst", "intelligence analyst",
    "analyst", "analytics", "data scientist", "data specialist"
]

NEGATIVE_KEYWORDS = [
    "senior", "sr.", "sr ", "principal", "director", "manager", "lead",
    "head of", "vp ", "vice president", "architect", "expert",
    "staff engineer", "staff data engineer", "staff software"
]

NON_NYC_CITIES = [
    "boston", "chicago", "san francisco", "seattle", "austin",
    "los angeles", "atlanta", "denver", "dallas", "phoenix",
    "miami", "boise", "stamford", "littleton", "long beach", "englewood"
]


def passes_filters(title, location, raw_text=""):
    title_lower  = title.lower()
    location_lower = location.lower() if location else ""
    top_lower    = raw_text.lower()[:600]

    if not any(k in title_lower for k in POSITIVE_KEYWORDS):
        return False
    if any(k in title_lower for k in NEGATIVE_KEYWORDS):
        return False

    has_remote  = "remote" in top_lower or "remote" in location_lower
    has_non_nyc = any(city in raw_text.lower() for city in NON_NYC_CITIES)
    has_nyc     = any(k in location_lower or k in raw_text.lower()[:300]
                      for k in ["new york", "nyc", "remote"])

    if has_non_nyc and not has_remote:
        return False
    if not has_nyc and not has_remote:
        return False

    return True


def url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()


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
            "wellfound",
            1 if posting["filtered_in"] else 0
        ))
        return True
    except sqlite3.IntegrityError:
        return False


def login(page):
    print("Logging in to Wellfound...")
    page.goto("https://wellfound.com/login", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    page.fill('input[name="user[email]"], input[type="email"]', EMAIL)
    page.fill('input[name="user[password]"], input[type="password"]', PASSWORD)
    page.keyboard.press("Enter")
    page.wait_for_timeout(4000)

    if "login" in page.url:
        print("  WARNING: Login may have failed. Check credentials.")
        return False
    print("  Logged in successfully.")
    return True


def scrape_search(page, desc_page, url, cur):
    print(f"\nSearching: {url}")
    page.goto(url, wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    for _ in range(5):
        page.keyboard.press("End")
        page.wait_for_timeout(1500)

    new_total     = 0
    passed_filter = 0

    job_cards = page.query_selector_all('[data-test="StartupResult"], .styles_component__Pf3, [class*="JobListing"], [class*="job-listing"]')

    if not job_cards:
        job_cards = page.query_selector_all("a[href*='/jobs/']")

    print(f"  Found {len(job_cards)} job cards")

    seen_urls = set()

    for card in job_cards:
        try:
            href = card.get_attribute("href") or ""
            if not href or "/jobs/" not in href:
                link = card.query_selector("a[href*='/jobs/']")
                href = link.get_attribute("href") if link else ""

            if not href:
                continue

            posting_url = href if href.startswith("http") else "https://wellfound.com" + href
            if posting_url in seen_urls:
                continue
            seen_urls.add(posting_url)

            card_text = card.inner_text().strip()
            lines     = [l.strip() for l in card_text.split("\n") if l.strip()]

            title   = lines[0] if lines else ""
            company = lines[1] if len(lines) > 1 else "Unknown"

            location = ""
            for line in lines:
                if any(k in line.lower() for k in ["new york", "nyc", "remote", "hybrid", "usa"]):
                    location = line
                    break

            if not title or len(title) < 3:
                continue

            filtered = passes_filters(title, location)
            status   = "PASS" if filtered else "skip"
            print(f"  [{status}] {title} — {company} ({location})")

            if filtered:
                print(f"    Fetching full description...")
                try:
                    desc_page.goto(posting_url, wait_until="networkidle", timeout=30000)
                    desc_page.wait_for_timeout(2000)
                    raw_text = desc_page.inner_text("main, article, body") or card_text
                    raw_text = raw_text[:8000]
                except Exception:
                    raw_text = card_text

                full_lower  = raw_text.lower()
                top_lower   = full_lower[:600]
                has_remote  = "remote" in top_lower
                has_non_nyc = any(city in full_lower for city in NON_NYC_CITIES)
                if has_non_nyc and not has_remote:
                    print(f"    Skipping — non-NYC city in description")
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

            if save_posting(cur, posting):
                new_total += 1

        except Exception as e:
            print(f"    Error: {e}")
            continue

    return new_total, passed_filter


def scrape():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    total_new     = 0
    total_passed  = 0

    with sync_playwright() as p:
        browser   = p.chromium.launch(headless=True)
        list_page = browser.new_page()
        desc_page = browser.new_page()

        if not login(list_page):
            browser.close()
            con.close()
            return

        for url in SEARCH_URLS:
            new, passed = scrape_search(list_page, desc_page, url, cur)
            con.commit()
            total_new    += new
            total_passed += passed

        browser.close()

    con.close()
    print(f"\nDone. {total_new} new postings saved. {total_passed} passed filters.")
    print("Next: python scoring/evaluate.py")


if __name__ == "__main__":
    scrape()
