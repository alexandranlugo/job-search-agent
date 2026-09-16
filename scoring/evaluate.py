"""
scoring/evaluate.py
Scores filtered postings using the career-ops scoring framework.
Usage: python scoring/evaluate.py
"""

import sqlite3, os, json
from anthropic import Anthropic
from dotenv import load_dotenv
import re
from datetime import datetime, timezone
MAX_AGE_DAYS = 21

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DB_PATH   = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
CV_PATH   = os.path.join(os.path.dirname(__file__), "..", "config", "cv.md")
PROF_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "profile.yml")

SENIOR = re.compile(r"\b(senior|sr\.?|staff|lead|principal|director|head of|manager|ii|iii)\b", re.I)

# Candidate has ~2 years of professional analytics experience — hard-skip postings
# that explicitly require 3+ years rather than relying on the LLM's soft scoring
# (red_flags is only 10% of the weighted score, so a real experience gap could
# still surface with a borderline-passing overall score).
EXPERIENCE_REQ = re.compile(
    r"\b([3-9]|1\d)\+?\s*(?:-\s*\d+\s*)?years?\b[^.\n]{0,40}\bexperience\b"
    r"|\bexperience\b[^.\n]{0,25}\b([3-9]|1\d)\+?\s*years?\b"
    r"|\b(?:minimum|min\.?|at least)\s*(?:of\s*)?([3-9]|1\d)\+?\s*years?\b",
    re.I,
)

client = Anthropic()

def load_file(path):
    with open(path, "r") as f:
        return f.read()

def score_posting(cv, profile, posting):
    prompt = f"""You are a job-fit evaluation engine. Evaluate this job posting against the candidate below.

Everything you need about the candidate is in the CV and profile sections — do not
assume any background, target role, location, or salary expectation that isn't stated there.

## Candidate CV
{cv}

## Candidate Profile & Preferences
{profile}

## Job Posting
Company: {posting['company']}
Title: {posting['title']}
Location: {posting['location']}

Full posting text:
{posting['raw_text']}

---

## Scoring Framework

Score each dimension 1-5, then compute a weighted global score:

| Dimension | Weight | What to measure |
|-----------|--------|-----------------|
| cv_match | 40% | Skills, experience, and proof-point alignment against the CV above. Does the candidate have 70%+ of what the posting actually requires? Judge against the tools and methods that appear in their CV, not a fixed list. |
| north_star | 25% | Fit against the target roles/archetypes in the profile above. Score 4.5+ if the title is one of their stated targets AND the core skills line up. Score 3.5-4.0 if adjacent (e.g. Business Analyst, Operations Analyst, Reporting Analyst) with a strong component of their core discipline. Score 2.0-3.0 if it's a stretch or a different function entirely. Apply any `scoring_adjustments.boost_if` signals from the profile as up to a +0.5 boost, and any `flag_if` signals as a deduction. |
| comp | 15% | Salary vs the `compensation` block in the profile (target_range and minimum). If no salary is listed score 3.0 — unknown comp is neutral, not a penalty. Listed at or above target score 4.5-5. Listed slightly under target score 3.5. Below their stated minimum score 1.5. Well above target score 3.0 — may signal a more senior hire, not an automatic penalty. |
| culture | 10% | Remote/hybrid policy vs the profile's location preferences, cross-functional and stakeholder-facing work, company type. |
| red_flags | 10% | Title rules: \"Senior\", \"Staff\", \"Lead\", \"II\", \"III\", \"Principal\" in title = score 1.0. \"Junior\", \"Associate\", \"Entry\" in title = score 4.5. Plain title with no seniority qualifier at all (e.g. just \"Data Analyst\") = score 3.5 — absence of a junior qualifier is not itself a seniority signal, most entry-level postings don't say \"Junior.\" Only deduct further for explicit hard signals: required years of experience well above what the CV shows, purely backend work with no stakeholder component, on-site only outside the candidate's stated locations, or missing core tools the posting lists as required rather than preferred. |

## Archetype Detection

If the profile lists target archetypes, classify into one of those. Otherwise fall
back to this general analytics taxonomy (use for match_reasons framing):
- Storytelling/Insights Analyst: narrative, communicate insights, stakeholder-facing
- Product Analyst: A/B testing, funnels, product metrics, experimentation
- Data Analyst Media/Culture: media, music, entertainment, culture, streaming
- Growth Analyst: growth metrics, acquisition, retention, revenue analytics
- BI Analyst: dashboards, reporting, stakeholder reporting
- Junior Data Scientist: ML pipeline, NLP, statistical modeling
- AI/ML Product Analyst: LLM evaluation, agentic workflows, model quality, AI product metrics

## Score interpretation
- 4.5+ = Strong match, apply immediately
- 4.0-4.4 = Good match, worth applying
- 3.5-3.9 = Decent but not ideal
- Below 3.5 = Do not surface

Return ONLY a JSON object with exactly these fields, no other text:
{{
  "archetype": "<detected archetype>",
  "cv_match": <float 1-5>,
  "north_star": <float 1-5>,
  "comp": <float 1-5>,
  "culture": <float 1-5>,
  "red_flags": <float 1-5>,
  "score": <weighted global score: cv_match*0.4 + north_star*0.25 + comp*0.15 + culture*0.1 + red_flags*0.1>,
  "grade": <"A" if score>=4.5, "B" if >=4.0, "C" if >=3.5, "D" if >=3.0, "F" otherwise>,
  "match_reasons": [<top 3 specific reasons this role fits the candidate, citing their actual proof points from the CV>],
  "gaps": [<top 2 genuine gaps or hard blockers>],
  "mitigation": "<one sentence on how the candidate addresses the gaps>",
  "outreach_draft": "<3-sentence LinkedIn message from the candidate to a recruiter at this company, written in first person. Mention the specific role title, reference one specific proof point from their CV that maps to this role, and express genuine interest. Warm and direct, not generic. Never include a phone number or home address.>"
}}"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    if response.stop_reason == "max_tokens":
        raise ValueError(f"Response truncated (hit max_tokens). Tail: ...{raw[-200:]}")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Bad JSON ({e}). Raw response: {raw[:400]}")


def run():
    cv      = load_file(CV_PATH)
    profile = load_file(PROF_PATH)

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    cur.execute("""
        SELECT p.* FROM postings p
        LEFT JOIN evaluations e ON e.posting_id = p.id
        WHERE p.filtered_in = 1 AND e.id IS NULL
    """)
    postings = cur.fetchall()

    if not postings:
        print("No new filtered postings to evaluate.")
        return

    print(f"Evaluating {len(postings)} postings...\n")
    surfaced = 0

    for p in postings:
        if SENIOR.search(p["title"]):
            print(f"  [skip senior] {p['title']} — {p['company']}")
            continue
        if not p["raw_text"] or len(p["raw_text"]) < 200:
            print(f"  [skip no description] {p['title']} — {p['company']}")
            continue
        exp_match = EXPERIENCE_REQ.search(p["raw_text"])
        if exp_match:
            print(f"  [skip experience-gap] {p['title']} — {p['company']} ({exp_match.group(0).strip()})")
            continue
        if p["posted_at"]:
            try:
                posted = datetime.fromisoformat(p["posted_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - posted).days
                if age > MAX_AGE_DAYS:
                    print(f"  [skip stale {age}d] {p['title']} — {p['company']}")
                    continue
            except Exception:
                pass

        print(f"Scoring: {p['title']} — {p['company']}")
        try:
            result = score_posting(cv, profile, dict(p))

            score         = round(result["score"], 2)
            grade         = result["grade"]
            surfaced_flag = 1 if score >= 3.5 else 0
            if surfaced_flag:
                surfaced += 1

            cur.execute("""
                INSERT INTO evaluations
                    (posting_id, score, grade, match_reasons, gaps, mitigation, outreach_draft, surfaced)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                p["id"],
                score,
                grade,
                json.dumps(result["match_reasons"]),
                json.dumps(result["gaps"]),
                result["mitigation"],
                result["outreach_draft"],
                surfaced_flag
            ))
            con.commit()

            if surfaced_flag:
                try:
                    from generate_resume import generate_pdf
                    pdf_path = generate_pdf(p["id"])
                    if pdf_path:
                        cur.execute("UPDATE evaluations SET resume_path = ? WHERE posting_id = ?",
                                    (pdf_path, p["id"]))
                        con.commit()
                        print(f"  Resume: {pdf_path}")
                except Exception as e:
                    print(f"  Resume generation skipped: {e}")
                

            flag = "SURFACE" if surfaced_flag else "below threshold"
            dims = f"cv={result['cv_match']} ns={result['north_star']} comp={result['comp']} cult={result['culture']} rf={result['red_flags']}"
            print(f"  Score: {score}/5.0 ({grade}) [{flag}]")
            print(f"  Archetype: {result['archetype']}")
            print(f"  Dimensions: {dims}")
            if surfaced_flag:
                print(f"  Match: {result['match_reasons'][0]}")
            print()

        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}\n")
            continue

    con.close()
    print(f"Done. {surfaced} postings scored 3.5+ and ready for your digest.")
    print("Next: python output/digest.py")

if __name__ == "__main__":
    run()
