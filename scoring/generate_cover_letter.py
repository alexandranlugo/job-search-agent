"""
scoring/generate_cover_letter.py
Generates a tailored cover letter (HTML + PDF) for a surfaced posting.
Usage: python scoring/generate_cover_letter.py <posting_id>
"""

import sqlite3, os
from anthropic import Anthropic
from dotenv import load_dotenv

LETTER_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "cover_letters")
HTML_DIR   = os.path.join(LETTER_DIR, "html")
os.makedirs(LETTER_DIR, exist_ok=True)
os.makedirs(HTML_DIR, exist_ok=True)

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH   = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
CV_PATH   = os.path.join(os.path.dirname(__file__), "..", "config", "cv.md")
PROF_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "profile.yml")

client = Anthropic()


def load_file(path):
    with open(path) as f:
        return f.read()


def generate_letter_content(cv, profile, posting):
    prompt = f"""You are writing a cover letter for Alexandra Lugo, a May 2026 NYU graduate
(B.A. Data Science + Business Studies). Write it so it sounds like a real person wrote it —
specific, warm, and direct. Not corporate, not breathless.

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

## Required structure

INTRODUCTION
- State the exact position being applied for.
- Give brief context: recent NYU graduate, B.A. Data Science and Business Studies.
- Say briefly why this organization specifically, and what she brings in relevant
  experience and skills. Reference something concrete about the company or role
  drawn from the job description — never generic praise.

BODY PARAGRAPHS (2, maximum 3)
- Order by RELEVANCE to this role, not chronology. Lead with the strongest match.
- Open each paragraph with a clear topic sentence naming a skill set, transferable
  experience, or area of knowledge.
- Walk through ONE project or experience per paragraph, weaving in the skills used
  and qualities demonstrated. Include the real numbers from her CV.
- Close each paragraph by connecting that experience to this role's requirements.

CONCLUSION
- Recap what she brings and restate interest in the position.
- Thank the employer for their consideration. Positive, warm, not grovelling.

## Rules
- Use ONLY experience, projects, employers, tools, and metrics that appear in the CV
  above. Never invent anything.
- 300-380 words in the letter body. One page, comfortably.
- Never apologize for gaps or lack of experience. Focus on what she has done.
- No cliches: avoid "I am writing to express my interest", "perfect fit",
  "passionate about leveraging", "team player", "fast-paced environment".
- Vary sentence length. Contractions are fine. First person, active voice.
- Address to "Dear Hiring Manager" unless the posting names a specific person.
- No em-dash overuse, no bullet points in the body.

## Output
Return ONLY a complete self-contained HTML document, no markdown fences, no commentary.
Styling requirements:
- Georgia serif, 10.5pt body text, black on white, line-height 1.5
- Add font-variant-ligatures: none and font-feature-settings: "liga" 0, "clig" 0
  to the star selector
- Header block at top: her name in 15pt bold, then a single contact line
  (New York City, NY | phone | email | portfolio | LinkedIn) at 9pt
- Then the date, then the company name and location, then the salutation
- Address block: company name only. Omit the location line if the posting location is
  a work-arrangement word like "Hybrid" or "Remote" rather than a city.
- Body paragraphs with 10px spacing between them, no indent
- Sign-off: "Sincerely," then her name
- Do NOT set page margins in CSS. No @page margin rule, no padding or max-width
  on wrapper divs. Margins are applied by the PDF renderer.
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()

def generate_cover_letter(posting_id):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    posting = con.execute(
        "SELECT * FROM postings WHERE id = ?", (posting_id,)
    ).fetchone()

    if not posting:
        print(f"Posting {posting_id} not found.")
        con.close()
        return None

    print(f"Generating cover letter for: {posting['title']} — {posting['company']}")

    cv      = load_file(CV_PATH)
    profile = load_file(PROF_PATH)

    print("  Calling API...")
    try:
        html = generate_letter_content(cv, profile, dict(posting))
    except Exception as e:
        print(f"  ERROR generating content: {e}")
        con.close()
        return None

    company_slug = posting['company'].lower().replace(" ", "-").replace("/", "-")
    title_slug   = posting['title'].lower().replace(" ", "-")[:30]
    filename     = f"{company_slug}_{title_slug}_cover.html"
    html_path    = os.path.join(HTML_DIR, filename)
    pdf_path     = os.path.join(LETTER_DIR, filename.replace(".html", ".pdf"))

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
            page.emulate_media(media="print")

            height = page.evaluate("document.documentElement.scrollHeight")
            scale  = max(min(1.0, 970 / height), 0.80) if height else 1.0
            if scale < 1.0:
                print(f"  Content {height}px -> scaling to {scale:.2f} to fit one page")

            page.pdf(path=pdf_path, format="Letter", scale=scale,
                     margin={"top": "0.75in", "bottom": "0.75in",
                             "left": "0.9in",  "right": "0.9in"},
                     print_background=True)
            browser.close()
    except Exception as e:
        print(f"  PDF generation failed: {e}")
        con.close()
        return None

    print(f"  PDF saved: {pdf_path}")
    con.close()
    return pdf_path


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python scoring/generate_cover_letter.py <posting_id> [more ids...]")
        sys.exit(1)
    for pid in sys.argv[1:]:
        generate_cover_letter(int(pid))
