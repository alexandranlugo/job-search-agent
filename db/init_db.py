import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), "pipeline.db")

def init():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS postings (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            url         TEXT UNIQUE NOT NULL,
            url_hash    TEXT UNIQUE NOT NULL,
            company     TEXT,
            title       TEXT,
            location    TEXT,
            salary      TEXT,
            source      TEXT,
            raw_text    TEXT,
            posted_at   TEXT,
            seen_at     TEXT DEFAULT (datetime('now')),
            filtered_in INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS evaluations (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            posting_id      INTEGER NOT NULL REFERENCES postings(id),
            score           REAL,
            grade           TEXT,
            match_reasons   TEXT,
            gaps            TEXT,
            mitigation      TEXT,
            resume_path     TEXT,
            outreach_draft  TEXT,
            evaluated_at    TEXT DEFAULT (datetime('now')),
            surfaced        INTEGER DEFAULT 0
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            posting_id      INTEGER NOT NULL REFERENCES postings(id),
            evaluation_id   INTEGER REFERENCES evaluations(id),
            status          TEXT DEFAULT 'to_apply',
            applied_at      TEXT,
            notes           TEXT,
            updated_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    con.commit()
    con.close()
    print("Database initialized at", DB_PATH)
    print("Tables created: postings, evaluations, applications")

if __name__ == "__main__":
    init()
