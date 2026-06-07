"""
scripts/import_career_ops_tracker.py
Imports applications from career-ops data/applications.md into the pipeline database.
Usage: python scripts/import_career_ops_tracker.py
"""

import sqlite3, os, re, hashlib

DB_PATH     = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
TRACKER_PATH = "/Users/alugo/career-ops/data/applications.md"

STATUS_MAP = {
    "evaluated": "to_apply",
    "applied":   "applied",
    "rejected":  "rejected",
    "discarded": "withdrawn",
    "interview": "interview",
    "offer":     "offer",
    "withdrawn": "withdrawn",
}

def url_hash(url):
    return hashlib.md5(url.encode()).hexdigest()

def parse_score(score_str):
    try:
        return float(score_str.split("/")[0])
    except:
        return 0.0

def run():
    with open(TRACKER_PATH) as f:
        lines = f.readlines()

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    imported = 0
    skipped  = 0

    for line in lines:
        line = line.strip()
        if not line.startswith("|") or line.startswith("| #") or line.startswith("|---"):
            continue

        parts = [p.strip() for p in line.split("|")]
        parts = [p for p in parts if p]

        if len(parts) < 6:
            continue

        try:
            num      = parts[0]
            date     = parts[1]
            company  = parts[2]
            role     = parts[3]
            score    = parse_score(parts[4])
            status   = parts[5].lower().strip()
            notes    = parts[8] if len(parts) > 8 else ""
        except Exception as e:
            continue

        mapped_status = STATUS_MAP.get(status, "to_apply")
        fake_url      = f"https://career-ops-import/{num}-{company.lower().replace(' ','-')}"
        fake_hash     = url_hash(fake_url)

        # Check if already imported
        existing = cur.execute(
            "SELECT id FROM postings WHERE url_hash = ?", (fake_hash,)
        ).fetchone()

        if existing:
            skipped += 1
            continue

        # Insert posting
        cur.execute("""
            INSERT INTO postings (url, url_hash, company, title, location, raw_text, source, filtered_in)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fake_url, fake_hash, company, role,
            "New York, NY", f"{company} — {role}", "career-ops",
            1 if score >= 4.0 else 0
        ))
        posting_id = cur.lastrowid

        # Insert evaluation
        grade = "A" if score >= 4.5 else "B" if score >= 4.0 else "C" if score >= 3.5 else "D" if score >= 3.0 else "F"
        cur.execute("""
            INSERT INTO evaluations (posting_id, score, grade, match_reasons, gaps, mitigation, outreach_draft, surfaced)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            posting_id, score, grade,
            "[]", "[]", notes, "",
            1 if score >= 4.0 else 0
        ))

        # Insert application
        cur.execute("""
            INSERT INTO applications (posting_id, status, notes, applied_at)
            VALUES (?, ?, ?, ?)
        """, (posting_id, mapped_status, notes, date))

        imported += 1
        print(f"  Imported: [{score}/5 {mapped_status}] {company} — {role}")

    con.commit()
    con.close()
    print(f"\nDone. {imported} applications imported, {skipped} skipped (already existed).")

if __name__ == "__main__":
    run()
