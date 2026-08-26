"""
output/digest.py
Generates a daily HTML digest of all surfaced postings (score >= 4.0).
Usage: python output/digest.py
"""

import sqlite3, os, json
from datetime import datetime, timezone

def age_tag(posted_at):
    if not posted_at:
        return ""
    try:
        posted = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        days = (datetime.now(timezone.utc) - posted).days
    except Exception:
        return ""
    if days <= 0:
        label, color = "Posted today", "#1a7f4b"
    elif days <= 3:
        label, color = f"{days}d ago", "#1a7f4b"
    elif days <= 10:
        label, color = f"{days}d ago", "#8a6d1f"
    else:
        label, color = f"{days}d ago", "#c0392b"
    return f'<span class="tag" style="color:{color};font-weight:600">🕐 {label}</span>'

import urllib.request

def is_live(url):
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status < 400
    except urllib.error.HTTPError:
        return False
    except Exception:
        return True   # network hiccup — don't drop a good roles

DB_PATH  = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
OUT_DIR  = os.path.join(os.path.dirname(__file__), "digests")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Job Digest — {date}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          max-width: 860px; margin: 40px auto; padding: 0 24px;
          color: #1a1a1a; background: #f9f9f7; }}
  h1   {{ font-size: 22px; font-weight: 600; margin-bottom: 4px; }}
  .sub {{ color: #666; font-size: 14px; margin-bottom: 32px; }}
  .card {{ background: #fff; border: 1px solid #e5e5e2; border-radius: 12px;
           padding: 24px; margin-bottom: 20px; }}
  .card-header {{ display: flex; justify-content: space-between; align-items: flex-start; }}
  .title {{ font-size: 18px; font-weight: 600; margin: 0 0 4px; }}
  .company {{ font-size: 14px; color: #555; margin: 0 0 12px; }}
  .score-badge {{ font-size: 20px; font-weight: 700; color: #1a7f4b;
                  background: #edfaf3; padding: 6px 14px; border-radius: 8px;
                  white-space: nowrap; }}
  .meta {{ display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; }}
  .tag {{ font-size: 12px; background: #f0f0ed; padding: 4px 10px;
          border-radius: 6px; color: #444; }}
  .section-label {{ font-size: 11px; font-weight: 600; text-transform: uppercase;
                    letter-spacing: 0.05em; color: #999; margin: 16px 0 6px; }}
  ul {{ margin: 0; padding-left: 18px; }}
  li {{ font-size: 14px; margin-bottom: 4px; line-height: 1.5; }}
  .gap  {{ color: #c0392b; }}
  .outreach {{ font-size: 14px; background: #f7f7f5; border-left: 3px solid #ccc;
               padding: 12px 16px; border-radius: 0 8px 8px 0;
               line-height: 1.6; margin-top: 8px; }}
  .actions {{ display: flex; gap: 10px; margin-top: 20px; flex-wrap: wrap; align-items: center; }}
  .apply-btn {{ display: inline-block; padding: 10px 20px;
                background: #1a1a1a; color: #fff; border-radius: 8px;
                text-decoration: none; font-size: 14px; font-weight: 500; }}
  .apply-btn:hover {{ background: #333; }}
  .career-ops-btn {{ display: inline-block; padding: 10px 20px;
                     background: #fff; color: #1a1a1a; border-radius: 8px;
                     font-size: 14px; font-weight: 500; border: 1px solid #ccc;
                     cursor: pointer; }}
  .career-ops-btn:hover {{ background: #f5f5f3; }}
  .copy-msg {{ font-size: 12px; color: #1a7f4b; display: none; }}
  .empty {{ text-align: center; padding: 60px 0; color: #999; font-size: 16px; }}
  .career-ops-box {{ display: none; margin-top: 16px; background: #f0f7ff;
                     border: 1px solid #c0d8f0; border-radius: 10px; padding: 16px; }}
  .career-ops-box.open {{ display: block; }}
  .career-ops-box h4 {{ font-size: 13px; font-weight: 600; margin-bottom: 8px; color: #1a5fa5; }}
  .career-ops-box ol {{ font-size: 13px; padding-left: 18px; color: #444; line-height: 1.8; }}
  .cmd-box {{ font-family: monospace; font-size: 12px; background: #1a1a1a; color: #e8e8e8;
              padding: 10px 14px; border-radius: 6px; margin: 10px 0;
              word-break: break-all; }}
  .copy-cmd-btn {{ font-size: 12px; padding: 5px 12px; border-radius: 6px;
                   border: 1px solid #c0d8f0; background: #fff; cursor: pointer;
                   color: #1a5fa5; }}
  .copy-cmd-btn:hover {{ background: #1a5fa5; color: #fff; }}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
  <h1>Daily Job Digest</h1>
  <a href="../tracker.html" style="font-size:13px;color:#1a5fa5;text-decoration:none;padding:8px 16px;border:1px solid #c0d8f0;border-radius:8px;background:#fff">📋 Application Tracker</a>
</div>
<p class="sub">{date} &mdash; {count} role{plural} scored 3.5 or above</p>
{cards}

<script>
function toggleCareerOps(id) {{
  const box = document.getElementById('co-box-' + id);
  box.classList.toggle('open');
}}

function copyCmd(id) {{
  const text = document.getElementById('cmd-' + id).textContent;
  navigator.clipboard.writeText(text).then(() => {{
    const btn = document.getElementById('copybtn-' + id);
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy command', 2000);
  }});
}}

function copyOutreach(id) {{
  const text = document.getElementById('outreach-' + id).textContent;
  navigator.clipboard.writeText(text).then(() => {{
    const msg = document.getElementById('copy-msg-' + id);
    msg.style.display = 'inline';
    setTimeout(() => msg.style.display = 'none', 2000);
  }});
}}

function copyCover(id) {{
  const text = document.getElementById('covercmd-' + id).textContent;
  navigator.clipboard.writeText(text).then(() => {{
    const msg = document.getElementById('cover-msg-' + id);
    msg.style.display = 'inline';
    setTimeout(() => msg.style.display = 'none', 3000);
  }});
}}
</script>
</body>
</html>"""

CARD_TEMPLATE = """<div class="card">
  <div class="card-header">
    <div>
      <p class="title">{title}</p>
      <p class="company">{company}</p>
    </div>
    <span class="score-badge">{score}/5.0 &nbsp;{grade}</span>
  </div>
  <div class="meta">
    <span class="tag">📍 {location}</span>
    <span class="tag">🔗 {source}</span>
    {salary_tag}
    {age_badge}
  </div>
  <p class="section-label">Why it fits</p>
  <ul>{match_items}</ul>
  <p class="section-label">Gaps to address</p>
  <ul class="gap">{gap_items}</ul>
  <p class="section-label">Mitigation</p>
  <p style="font-size:14px;margin:0">{mitigation}</p>
  <p class="section-label">LinkedIn outreach draft</p>
  <div class="outreach" id="outreach-{card_id}">{outreach}</div>
  <div class="actions">
    <a class="apply-btn" href="{url}" target="_blank">View &amp; Apply →</a>
    <button class="career-ops-btn" onclick="toggleCareerOps({card_id})">⚡ Evaluate in career-ops</button>
    <button class="career-ops-btn" onclick="copyOutreach({card_id})">Copy outreach</button>
    <button class="career-ops-btn" onclick="copyCover({card_id})">✉️ Cover letter</button>
    <span class="copy-msg" id="copy-msg-{card_id}">Copied!</span>
    <span class="copy-msg" id="cover-msg-{card_id}">Copied — paste in terminal</span>
    <span id="covercmd-{card_id}" style="display:none">python scoring/generate_cover_letter.py {posting_id}</span>
  </div>
  <div class="career-ops-box" id="co-box-{card_id}">
    <h4>Run full career-ops evaluation for this role</h4>
    <ol>
      <li>Open your terminal and navigate to your career-ops folder</li>
      <li>Run <code>claude</code> to open Claude Code</li>
      <li>Copy and paste this command:</li>
    </ol>
    <div class="cmd-box" id="cmd-{card_id}">/career-ops {url}</div>
    <button class="copy-cmd-btn" id="copybtn-{card_id}" onclick="copyCmd({card_id})">Copy command</button>
    <p style="font-size:12px;color:#888;margin-top:10px;">career-ops will run the full 7-block evaluation, generate a tailored PDF resume, STAR interview stories, and log everything to your tracker.</p>
  </div>
</div>"""


def run():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    rows = con.execute("""
        SELECT p.title, p.company, p.location, p.salary, p.url, p.source,
               p.posted_at,
               e.score, e.grade, e.match_reasons, e.gaps, e.mitigation,
               e.outreach_draft, e.evaluated_at, p.id as posting_id
        FROM evaluations e
        JOIN postings p ON p.id = e.posting_id
        LEFT JOIN applications a ON a.posting_id = p.id
        WHERE e.surfaced = 1
        AND e.digested_at IS NULL
        AND a.id IS NULL
        ORDER BY p.posted_at DESC, e.score DESC
    """).fetchall()

    live_rows = []
    for r in rows:
        if is_live(r["url"]):
            live_rows.append(r)
        else:
            print(f"  [dead link] {r['title']} — {r['company']}")
            con.execute("UPDATE evaluations SET surfaced=0 WHERE posting_id=?", (r["posting_id"],))
    rows = live_rows

    # Each surfaced role should appear in exactly one digest, not resurface every
    # day it stays unapplied — mark everything shown today as sent.
    for r in rows:
        con.execute("UPDATE evaluations SET digested_at = datetime('now') WHERE posting_id=?", (r["posting_id"],))
    con.commit()
    con.close()

    date_str = datetime.now().strftime("%B %d, %Y")
    count    = len(rows)
    plural   = "s" if count != 1 else ""

    if count == 0:
        cards = '<div class="empty">No roles scored 3.5+ today. Check back tomorrow.</div>'
    else:
        cards = ""
        for i, r in enumerate(rows):
            match_reasons = json.loads(r["match_reasons"]) if r["match_reasons"] else []
            gaps          = json.loads(r["gaps"])          if r["gaps"]          else []

            match_items = "".join(f"<li>{m}</li>" for m in match_reasons)
            gap_items   = "".join(f"<li>{g}</li>" for g in gaps)
            salary_tag  = f'<span class="tag">💰 {r["salary"]}</span>' if r["salary"] else ""
            age_badge   = age_tag(r["posted_at"])

            cards += CARD_TEMPLATE.format(
                card_id     = i,
                title       = r["title"],
                company     = r["company"],
                location    = r["location"] or "Not specified",
                source      = r["source"],
                salary_tag  = salary_tag,
                age_badge  = age_badge,
                score       = r["score"],
                grade       = r["grade"],
                match_items = match_items,
                gap_items   = gap_items,
                mitigation  = r["mitigation"] or "",
                outreach    = r["outreach_draft"] or "",
                url         = r["url"],
                posting_id  = r["posting_id"]
            )

    html = HTML_TEMPLATE.format(
        date   = date_str,
        count  = count,
        plural = plural,
        cards  = cards
    )

    os.makedirs(OUT_DIR, exist_ok=True)
    filename = f"digest_{datetime.now().strftime('%Y-%m-%d')}.html"
    out_path = os.path.join(OUT_DIR, filename)

    with open(out_path, "w") as f:
        f.write(html)

    print(f"Digest saved: {out_path}")
    print(f"{count} role{plural} in today's digest.")
    return out_path

if __name__ == "__main__":
    path = run()
    os.system(f"open '{path}'")
