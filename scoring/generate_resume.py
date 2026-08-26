"""
scoring/generate_resume.py
Generates a tailored PDF resume for a surfaced posting using the career-ops template.
Usage: python scoring/generate_resume.py <posting_id>
"""

import sqlite3, os
from anthropic import Anthropic
from dotenv import load_dotenv

RESUME_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "resumes")
HTML_DIR   = os.path.join(RESUME_DIR, "html")
os.makedirs(RESUME_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH        = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
CV_PATH        = os.path.join(os.path.dirname(__file__), "..", "config", "cv.md")
PROF_PATH      = os.path.join(os.path.dirname(__file__), "..", "config", "profile.yml")
TEMPLATE_PATH = "/Users/alugo/career-ops/templates/cv-template.html"

client = Anthropic()


def load_file(path):
    with open(path) as f:
        return f.read()


def generate_resume_content(cv, profile, posting):
    prompt = f"""You are generating a tailored, ATS-optimized resume for Alexandra Lugo.
Follow her resume rules exactly — these are non-negotiable.

## Resume Rules (from cv.md — follow exactly)

### Length — hardest constraints, obey these first
- ONE PAGE. No exceptions. Be ruthless.
- TOTAL BODY TEXT MUST NOT EXCEED 520 WORDS. Count before returning.
- Summary: 45 words maximum, three sentences.
- Maximum 3 jobs, 2 bullets each, 28 words per bullet.
- Maximum 2 projects, 2 bullets each, 30 words per bullet.
- Maximum 5 skills lines.

### Content
- STRICT reverse chronological order. Current roles (end date "Present") come FIRST, before any role that has ended; within each group sort by start date descending. Pfizer (Jul 2026–Present) and micro1 (Jun 2026–Present) are current; Sallie Mae ended May 2026 and comes after them.
- Choose the 3 jobs most relevant to this role. NYU Athletics is lowest priority.
- Lead every bullet with a strong action verb.
- Always include dollar figures and percentages where available.
- Skills split into separate labeled lines by category; plain text, comma separated.
- Keep BI & Visualization separate from Data & Cloud / Engineering tools.

### Layout
- Section headers only: Summary, Work Experience, Projects, Education, Skills.
- Job titles and company names on separate lines, not side by side.
- No tables, columns, text boxes, graphics, icons, decorative lines, or keyword grids.
- Never use a two-column layout.
- Black and white only.

## Candidate CV
{cv}

## Candidate Profile
{profile}

## Target Job
Company: {posting['company']}
Title: {posting['title']}
Location: {posting['location']}

Job Description:
{posting['raw_text'][:4000]}

---

Generate a complete, self-contained HTML resume that:
1. Follows ALL the rules above exactly
2. Is tailored to this specific role — mirror keywords from the JD naturally
3. Prioritizes the most relevant experience and projects for THIS role
4. Includes the summary mentioning the company name and role
5. Uses inline CSS only — no external stylesheets or fonts
6. Uses Georgia serif font throughout, 9.8pt body text
7. Has clean, minimal styling: black text on white background, simple layout
8. Contact info at the top in main body (no header/footer)
9. Print-ready US Letter. Do NOT set page margins in CSS — no @page margin rule, no padding or max-width on wrapper divs. Margins are applied by the PDF renderer.
10. Add CSS `page-break-inside: avoid` to each job block and project block
11. CRITICAL — ATS text extraction: put `font-variant-ligatures: none; font-feature-settings: "liga" 0, "clig" 0, "dlig" 0;` on the `*` universal selector AND on `body`. Without this, "Office" extracts as "Of ice" and breaks ATS keyword parsing.
12. Use standard `list-style: disc` for bullets. Never use `::before` with absolute positioning — it scrambles PDF text extraction for ATS parsers.
13. Add `font-variant-ligatures: none; font-feature-settings: "liga" 0, "clig" 0;` to the `*` selector, not just body.

Return ONLY the complete HTML document, no other text, no markdown fences."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


def generate_pdf(posting_id):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    posting = con.execute(
        "SELECT * FROM postings WHERE id = ?", (posting_id,)
    ).fetchone()

    if not posting:
        print(f"Posting {posting_id} not found.")
        con.close()
        return None

    print(f"Generating resume for: {posting['title']} — {posting['company']}")

    cv       = load_file(CV_PATH)
    profile  = load_file(PROF_PATH)

    print("  Calling API to generate tailored content...")
    try:
        values = generate_resume_content(cv, profile, dict(posting))
    except Exception as e:
        print(f"  ERROR generating content: {e}")
        con.close()
        return None

    html = values  # generate_resume_content now returns HTML directly

    company_slug = posting['company'].lower().replace(" ", "-").replace("/", "-")
    title_slug   = posting['title'].lower().replace(" ", "-")[:30]
    filename     = f"{company_slug}_{title_slug}.html"
    html_path    = os.path.join(HTML_DIR, filename)
    pdf_path     = os.path.join(RESUME_DIR, filename.replace(".html", ".pdf"))

    with open(html_path, "w") as f:
        f.write(html)
    print(f"  HTML: {html_path}")

    print("  Rendering PDF...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 710, "height": 970})
            page.goto("file://" + os.path.abspath(html_path))

            # US Letter at 96dpi = 1056px tall
            height = page.evaluate("document.body.scrollHeight")
            scale  = min(1.0, 970 / height) if height else 1.0
            scale  = max(scale, 0.75)          # floor — below this it's unreadable
            if scale < 1.0:
                print(f"  Content {height}px → scaling to {scale:.2f} to fit one page")

            page.pdf(path=pdf_path, format="Letter", scale=scale,
                     margin={"top":"0.45in","bottom":"0.45in",
                             "left":"0.55in","right":"0.55in"},
                     print_background=True)
            browser.close()
    except Exception as e:
        print(f"  PDF generation failed: {e}")
        con.close()
        return None

    print(f"  PDF saved: {pdf_path}")

    con.execute(
        "UPDATE evaluations SET resume_path = ? WHERE posting_id = ?",
        (pdf_path, posting_id)
    )
    con.commit()
    con.close()
    return pdf_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python scoring/generate_resume.py <posting_id>")
        sys.exit(1)
    generate_pdf(int(sys.argv[1]))