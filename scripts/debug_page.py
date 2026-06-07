from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://builtin.com/jobs/nyc/data-analytics", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    for _ in range(3):
        page.keyboard.press("End")
        page.wait_for_timeout(1500)
    html = page.content()
    with open("logs/page_dump.html", "w") as f:
        f.write(html)
    print(f"Page dumped. Total length: {len(html)} characters")
    browser.close()
