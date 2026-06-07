"""
scoring/generate_resume.py
Generates a tailored PDF resume for a surfaced posting using the career-ops template.
Usage: python scoring/generate_resume.py <posting_id>
"""

import sqlite3, os, json, subprocess
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH        = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
CV_PATH        = os.path.join(os.path.dirname(__file__), "..", "config", "cv.md")
PROF_PATH      = os.path.join(os.path.dirname(__file__), "..", "config", "profile.yml")
CAREER_OPS_DIR = "/Users/alugo/career-ops"
TEMPLATE_PATH  = os.path.join(CAREER_OPS_DIR, "templates", "cv-template.html")
PDF_OUT_DIR    = os.path.join(os.path.dirname(__file__), "..", "output", "resumes")

client = Anthropic()


def load_file(path):
    with open(path) as f:
        return f.read()


def generate_resume_content(cv, profile, posting):
    prompt = f"""You are generating a tailored, ATS-optimized resume for Alexandra Lugo.
Follow her resume rules exactly — these are non-negotiable.

## Resume Rules (from cv.md — follow exactly)
- ONE PAGE resume. No exceptions. Be ruthless with brevity.
- Tight, punchy bullets (1 line each where possible, 2 lines maximum)
- Maximum 3 bullets per job
- Maximum 2 bullets per project
- Lead every bullet with a strong action verb
- Always include dollar figures and percentages where available
- No Core Competencies bar, keyword grid, or table of any kind
- Summary: 3-4 lines maximum
- Black and white only. No color anywhere.
- Skills section: split into separate labeled lines by category
- Keep BI & Visualization separate from Data & Cloud / Engineering tools
- Standard section headers only: Summary, Work Experience, Projects, Education, Skills
- No tables, columns, text boxes, or graphics
- No icons, lines, or decorative elements
- Standard fonts only (Arial, Calibri, or similar)
- Job titles and company names on separate lines, not side by side
- Skills listed as plain text, comma separated
- Never use a two-column layout

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
6. Uses Arial or Calibri font throughout
7. Has clean, minimal styling: black text on white background, simple layout
8. Contact info at the top in main body (no header/footer)
9. Is print-ready at US Letter size

Return ONLY the complete HTML document, no other text, no markdown fences."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text.strip()


def fill_template(template, values):
    result = template
    for key, value in values.items():
        result = result.replace("{{" + key + "}}", str(value) if value else "")
    return result


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
    html_path    = os.path.join(CAREER_OPS_DIR, "output", filename)
    pdf_filename = filename.replace(".html", ".pdf")
    pdf_path     = os.path.join(PDF_OUT_DIR, pdf_filename)

    os.makedirs(os.path.join(CAREER_OPS_DIR, "output"), exist_ok=True)
    os.makedirs(PDF_OUT_DIR, exist_ok=True)

    with open(html_path, "w") as f:
        f.write(html)
    print(f"  HTML written: {html_path}")

    print("  Running generate-pdf.mjs...")
    result = subprocess.run(
        ["node", "generate-pdf.mjs", html_path, pdf_path],
        cwd=CAREER_OPS_DIR,
        capture_output=True,
        text=True,
        timeout=60
    )

    if result.returncode != 0:
        print(f"  PDF generation failed:\n{result.stderr}")
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