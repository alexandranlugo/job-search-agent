"""
ingestion/scrape_greenhouse.py
Scrapes job postings from Greenhouse, Ashby, and Lever boards
for companies in portals.yml.
Usage: python ingestion/scrape_greenhouse.py
"""

import sqlite3, hashlib, os, json, time
import urllib.request, urllib.error
import yaml
from dotenv import load_dotenv
from datetime import datetime, timezone

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH      = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
PORTALS_PATH = "/Users/alugo/career-ops/portals.yml"

POSITIVE_KEYWORDS = [
    "data analyst", "product analyst", "insights analyst", "growth analyst",
    "business analyst", "analytics engineer", "bi analyst", "junior data scientist",
    "storytelling analyst", "marketing analyst", "intelligence analyst",
    "analyst", "analytics", "data scientist", "data specialist", "data insights"
]

NEGATIVE_KEYWORDS = [
    "senior", "sr.", "sr ", "principal", "director", "manager", "lead",
    "head of", "vp ", "vice president", "architect", "expert",
    "staff", " ii", " iii", " iv", "deal desk", "aml", "compliance", "payroll", "procurement", "purchasing",
    "compensation", "fp&a", "financial planning", "employee lifecycle",
    "sales operations", "order operations", "corporate development", "revenue strategy",
    "pricing","sales revenue"
]



def passes_title_filter(title):
    title_lower = title.lower()
    if not any(k in title_lower for k in POSITIVE_KEYWORDS):
        return False
    if any(k in title_lower for k in NEGATIVE_KEYWORDS):
        return False
    return True


NYC_TOKENS = ["new york", "nyc", ", ny", "brooklyn", "manhattan"]

def passes_location_filter(location, description=""):
    loc_lower = (location or "").lower()
    desc_lower = (description or "").lower()[:1500]

    if any(k in loc_lower for k in NYC_TOKENS):
        return True
    if any(k in desc_lower for k in NYC_TOKENS):
        return True
    if "remote" in loc_lower:
        # Candidate profile is explicitly open to remote-only, regardless of city.
        return True
    # "Hybrid" alone (or an empty/unrecognized location) doesn't tell us the
    # office city — a bare "Hybrid" tag usually means hybrid-at-HQ, which for
    # most tracked companies isn't NYC. Only pass if NYC was named somewhere.
    return False

def url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()


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


def is_duplicate_title(cur, company, title):
    """Check if a very similar title from the same company already exists."""
    import re
    # Normalize: lowercase, remove punctuation, collapse spaces
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


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def scrape_greenhouse(company_name, api_url, cur):
    count = 0
    passed = 0
    try:
        data = fetch_json(api_url)
        jobs = data.get("jobs", [])
        print(f"  {company_name} (Greenhouse): {len(jobs)} total jobs")

        for job in jobs:
            title    = job.get("title", "")
            location = job.get("location", {}).get("name", "")
            url      = job.get("absolute_url", "")
            raw_text = f"{title}\n{location}\n{job.get('content','')}"
            posted_at = job.get("updated_at", "")

            if not passes_title_filter(title):
                continue
            if not passes_location_filter(location, job.get('content', '')):
                continue

            filtered = True
            status   = "PASS"
            print(f"    [{status}] {title} ({location})")

            posting = {
                "url":         url,
                "company":     company_name,
                "title":       title,
                "location":    location,
                "raw_text":    raw_text[:8000],
                "source":      "greenhouse",
                "posted_at":   posted_at,
                "filtered_in": filtered
            }
            if is_duplicate_title(cur, company_name, title):
                print(f"    [DEDUP] Skipping duplicate title: {title}")
                continue
            if save_posting(cur, posting):
                count += 1
                passed += 1

    except Exception as e:
        print(f"  {company_name} (Greenhouse): ERROR — {e}")

    return count, passed


def fetch_full_page(url):
    try:
        import re as _re
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="ignore")
        text = _re.sub(r"<[^>]+>", " ", html)
        text = _re.sub(r"\s+", " ", text).strip()
        return text[:8000]
    except Exception:
        return ""


def scrape_lever(company_name, careers_url, cur):
    count = 0
    passed = 0
    try:
        slug = careers_url.rstrip("/").split("/")[-1]
        api_url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        jobs = fetch_json(api_url)
        print(f"  {company_name} (Lever): {len(jobs)} total jobs")

        for job in jobs:
            title    = job.get("text", "")
            location = job.get("categories", {}).get("location", "")
            url      = job.get("hostedUrl", "")
            desc     = job.get("descriptionPlain", "") or job.get("description", "")
            ts = job.get("createdAt")
            posted_at = datetime.fromtimestamp(ts/1000, timezone.utc).isoformat() if ts else ""


            if not passes_title_filter(title):
                continue
            if not passes_location_filter(location, desc):
                continue

            print(f"    [PASS] {title} ({location}) — fetching full page...")
            full_text = fetch_full_page(url)
            raw_text  = full_text if len(full_text) > len(desc) else f"{title}\n{location}\n{desc}"

            posting = {
                "url":         url,
                "company":     company_name,
                "title":       title,
                "location":    location,
                "raw_text":    raw_text[:8000],
                "source":      "lever",
                "posted_at":   posted_at,
                "filtered_in": True
            }
            if is_duplicate_title(cur, company_name, title):
                print(f"    [DEDUP] Skipping duplicate title: {title}")
                continue 
            if save_posting(cur, posting):
                count += 1
                passed += 1
            time.sleep(0.5)

    except Exception as e:
        print(f"  {company_name} (Lever): ERROR — {e}")

    return count, passed


def scrape_ashby(company_name, careers_url, cur):
    count = 0
    passed = 0
    try:
        slug = careers_url.rstrip("/").split("/")[-1]
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        data = fetch_json(api_url)
        jobs = data.get("jobs", [])
        if not jobs:
            print(f"  {company_name} (Ashby): 0 jobs — VERIFY SLUG '{slug}'")
        else:
            print(f"  {company_name} (Ashby): {len(jobs)} total jobs")

        for job in jobs:
            title    = job.get("title", "").strip()
            location = job.get("location", "")
            secondary = " ".join(
                s.get("location", "") for s in job.get("secondaryLocations", []) or []
            )
            location = f"{location} {secondary}".strip()
            url      = job.get("jobUrl", "") or job.get("applyUrl", "")
            desc     = job.get("descriptionPlain", "") or job.get("descriptionHtml", "")
            raw_text = f"{title}\n{location}\n{desc}"
            posted_at = job.get("publishedAt", "")

            if not passes_title_filter(title):
                continue
            if not passes_location_filter(location, desc):
                continue

            print(f"    [PASS] {title} ({location})")

            posting = {
                "url":         url,
                "company":     company_name,
                "title":       title,
                "location":    location,
                "raw_text":    raw_text[:8000],
                "source":      "ashby",
                "posted_at":   posted_at,
                "filtered_in": True
            }
            if is_duplicate_title(cur, company_name, title):
                print(f"    [DEDUP] Skipping duplicate title: {title}")
                continue
            if save_posting(cur, posting):
                count += 1
                passed += 1

    except Exception as e:
        print(f"  {company_name} (Ashby): ERROR — {e}")

    return count, passed


def run():
    with open(PORTALS_PATH) as f:
        portals = yaml.safe_load(f)

    companies = [c for c in portals.get("tracked_companies", []) if c.get("enabled", True)]
    print(f"Scanning {len(companies)} companies...\n")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    total_new    = 0
    total_passed = 0

    for company in companies:
        name         = company.get("name", "")
        careers_url  = company.get("careers_url", "")
        api_url      = company.get("api", "")

        if api_url and "greenhouse" in api_url:
            new, passed = scrape_greenhouse(name, api_url, cur)
        elif "lever.co" in careers_url:
            new, passed = scrape_lever(name, careers_url, cur)
        elif "ashbyhq.com" in careers_url:
            new, passed = scrape_ashby(name, careers_url, cur)
        elif "greenhouse.io" in careers_url:
            slug    = careers_url.rstrip("/").split("/")[-1]
            api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
            new, passed = scrape_greenhouse(name, api_url, cur)
        else:
            print(f"  {name}: no supported API URL, skipping")
            new, passed = 0, 0

        total_new    += new
        total_passed += passed
        con.commit()
        time.sleep(0.5)

    con.close()
    print(f"\nDone. {total_new} new postings saved. {total_passed} passed filters.")
    print("Next: python scoring/evaluate.py")

def run_extra():
    """Scrape additional companies with known API slugs not in portals.yml."""

    EXTRA_GREENHOUSE = {
        # Sony Music Entertainment, Luminate now wired directly in portals.yml — scraped via run()
        # anchor bench — verify each token returns 200 before adding
        "Datadog":                  "datadog",
        "MongoDB":                  "mongodb",
        "Squarespace":              "squarespace",
        "Peloton":                  "peloton",
        "Betterment":     "betterment",
        "Justworks":      "justworks",
        "Yext":           "yext",
        "Braze":          "braze",
        "Attentive":      "attentive",
        "DoubleVerify":   "doubleverify",
        "Rent the Runway": "renttherunway",
        "Sisense":        "sisense",
        "Dataiku":        "dataiku",
    }

    EXTRA_ASHBY = {
        # Substack now wired directly in portals.yml — scraped via run()
        "Ramp": "ramp",
    }

    EXTRA_LEVER = {
        # The Athletic (NYT), JustWatch now wired directly in portals.yml — scraped via run()
    }

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    total_new    = 0
    total_passed = 0

    print("\nScanning extra companies with known API slugs...\n")

    for name, slug in EXTRA_GREENHOUSE.items():
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        new, passed = scrape_greenhouse(name, api_url, cur)
        total_new += new; total_passed += passed
        con.commit(); time.sleep(0.5)

    for name, slug in EXTRA_ASHBY.items():
        url = f"https://jobs.ashbyhq.com/{slug}"
        new, passed = scrape_ashby(name, url, cur)
        total_new += new; total_passed += passed
        con.commit(); time.sleep(0.5)

    for name, slug in EXTRA_LEVER.items():
        url = f"https://jobs.lever.co/{slug}"
        new, passed = scrape_lever(name, url, cur)
        total_new += new; total_passed += passed
        con.commit(); time.sleep(0.5)

    con.close()
    print(f"\nExtra scan done. {total_new} new postings. {total_passed} passed filters.")


if __name__ == "__main__":
    run()
    run_extra()
