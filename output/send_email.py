"""
output/send_email.py
Sends the daily digest as an HTML email via Gmail, with that day's tailored
resume PDFs attached directly so there's no need to go dig through the
output/resumes/ folder.
Usage: python output/send_email.py
"""

import os, re, sqlite3, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

EMAIL_FROM     = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
EMAIL_TO       = EMAIL_FROM  # send to yourself
DIGESTS_DIR    = os.path.join(os.path.dirname(__file__), "digests")
DB_PATH        = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")


def safe_filename(text):
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or "role"


def todays_resumes():
    """Resume PDFs for roles included in today's digest (set by digest.py)."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT p.company, p.title, e.resume_path
        FROM evaluations e
        JOIN postings p ON p.id = e.posting_id
        WHERE date(e.digested_at) = date('now')
        AND e.resume_path IS NOT NULL AND e.resume_path != ''
    """).fetchall()
    con.close()

    resumes = []
    for r in rows:
        if os.path.exists(r["resume_path"]):
            filename = f"{safe_filename(r['company'])}_{safe_filename(r['title'])}.pdf"
            resumes.append((filename, r["resume_path"]))
        else:
            print(f"  [missing resume] {r['title']} — {r['company']}: {r['resume_path']}")
    return resumes


def send_digest():
    today     = datetime.now().strftime("%Y-%m-%d")
    filename  = f"digest_{today}.html"
    filepath  = os.path.join(DIGESTS_DIR, filename)

    if not os.path.exists(filepath):
        print(f"No digest found for today: {filepath}")
        return False

    with open(filepath) as f:
        html_content = f.read()

    # Count roles in digest
    role_count = html_content.count('class="card"')
    if role_count == 0:
        subject = f"Job Digest {today} — no new matches today"
    else:
        subject = f"Job Digest {today} — {role_count} role{'s' if role_count != 1 else ''} scored 4.0+"

    resumes = todays_resumes()

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO

    body = MIMEMultipart("alternative")
    body.attach(MIMEText(html_content, "html"))
    msg.attach(body)

    for filename, path in resumes:
        with open(path, "rb") as f:
            part = MIMEApplication(f.read(), _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)

    if resumes:
        print(f"Attaching {len(resumes)} resume(s): {', '.join(f for f, _ in resumes)}")

    print(f"Sending digest email to {EMAIL_TO}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    print(f"Sent: {subject}")
    return True


if __name__ == "__main__":
    send_digest()
