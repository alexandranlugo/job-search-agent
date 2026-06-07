from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://builtin.com/jobs/nyc/data-analytics", wait_until="networkidle", timeout=60000)
    page.wait_for_timeout(3000)
    for _ in range(3):
        page.keyboard.press("End")
        page.wait_for_timeout(1500)

    result = page.evaluate("""() => {
        const results = [];
        const candidates = document.querySelectorAll('[class*="job"], [class*="Job"], [data-id], li, div');
        for (const el of candidates) {
            const text = el.innerText || '';
            if (text.includes('Digital Service & CX Analyst') && text.length < 500) {
                results.push({
                    tag: el.tagName,
                    className: el.className,
                    dataId: el.getAttribute('data-id'),
                    text: text.substring(0, 200)
                });
            }
        }
        return results.slice(0, 5);
    }""")

    for r in result:
        print(r)

    browser.close()
