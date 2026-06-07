"""
Saves Wellfound session using a stealth browser context.
"""
import json, os
from playwright.sync_api import sync_playwright

COOKIES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "wellfound_cookies.json")

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=False,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        locale="en-US",
        timezone_id="America/New_York"
    )
    page = context.new_page()
    page.goto("https://wellfound.com/login")
    print("Browser opened. Log in to Wellfound, then press Enter here.")
    input("Press Enter once logged in...")
    cookies = context.cookies()
    with open(COOKIES_PATH, "w") as f:
        json.dump(cookies, f)
    print(f"Saved {len(cookies)} cookies to {COOKIES_PATH}")
    browser.close()
