import json, os
from playwright.sync_api import sync_playwright

COOKIES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "wellfound_cookies.json")

with open(COOKIES_PATH) as f:
    raw_cookies = json.load(f)

# Convert EditThisCookie format to Playwright format
cookies = []
for c in raw_cookies:
    cookie = {
        "name":   c["name"],
        "value":  c["value"],
        "domain": c["domain"],
        "path":   c.get("path", "/"),
        "secure": c.get("secure", False),
        "httpOnly": c.get("httpOnly", False),
    }
    if "expirationDate" in c:
        cookie["expires"] = int(c["expirationDate"])
    cookies.append(cookie)

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    context.add_cookies(cookies)
    page = context.new_page()
    page.goto("https://wellfound.com/jobs?role=Data+Analyst&location=New+York+City",
              wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)
    print("URL:", page.url)
    print("Title:", page.title())
    print("Blocked:", "restricted" in page.content().lower())
    print("Logged in:", "logout" in page.content().lower() or "sign-out" in page.content().lower())
    browser.close()
