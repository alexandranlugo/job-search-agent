"""
output/send_email.py
Sends the daily digest as an HTML email via Gmail.
Usage: python output/send_email.py
"""

import os, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

EMAIL_FROM     = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")
EMAIL_TO       = EMAIL_FROM  # send to yourself
DIGESTS_DIR    = os.path.join(os.path.dirname(__file__), "digests")


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
    subject    = f"Job Digest {today} — {role_count} role{'s' if role_count != 1 else ''} scored 4.0+"

    if role_count == 0:
        print("No roles in digest, skipping email.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = EMAIL_FROM
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html_content, "html"))

    print(f"Sending digest email to {EMAIL_TO}...")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

    print(f"Sent: {subject}")
    return True


if __name__ == "__main__":
    send_digest()
