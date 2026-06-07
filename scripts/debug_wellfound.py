from playwright.sync_api import sync_playwright
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://wellfound.com/login", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)

    print("URL:", page.url)
    print("Title:", page.title())
    print()

    inputs = page.query_selector_all("input")
    print(f"Found {len(inputs)} input fields:")
    for i in inputs:
        print(f"  type={i.get_attribute('type')} name={i.get_attribute('name')} placeholder={i.get_attribute('placeholder')} id={i.get_attribute('id')}")

    with open("logs/wellfound_login.html", "w") as f:
        f.write(page.content())
    print("\nPage dumped to logs/wellfound_login.html")
    browser.close()
