import sys, glob, os
from playwright.sync_api import sync_playwright

BASE       = os.path.dirname(__file__)
RESUME_DIR = os.path.join(BASE, "..", "output", "resumes")
HTML_DIR   = os.path.join(RESUME_DIR, "html")

files = sys.argv[1:] or glob.glob(os.path.join(HTML_DIR, "*.html"))
if not files:
    print(f"No HTML files found in {HTML_DIR}")
    raise SystemExit

MARGIN = {"top": "0.45in", "bottom": "0.45in", "left": "0.55in", "right": "0.55in"}

with sync_playwright() as p:
    browser = p.chromium.launch()
    # printable area: 8.5in - 1.1in = 7.4in = 710px @96dpi
    page = browser.new_page(viewport={"width": 710, "height": 970})
    for f in files:
        name = os.path.basename(f).rsplit(".", 1)[0] + ".pdf"
        out  = os.path.join(RESUME_DIR, name)
        page.goto("file://" + os.path.abspath(f))
        page.emulate_media(media="print")

        height = page.evaluate("document.documentElement.scrollHeight")
        scale  = max(min(1.0, 970 / height), 0.75) if height else 1.0
        if scale < 1.0:
            print(f"  {name}: {height}px → scale {scale:.2f}")

        page.pdf(path=out, format="Letter", scale=scale,
                 margin=MARGIN, print_background=True)
        print("→", out)
    browser.close()