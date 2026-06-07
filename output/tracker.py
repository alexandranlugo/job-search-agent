"""
output/tracker.py
Generates an interactive HTML tracker for all evaluated postings.
Usage: python output/tracker.py
"""

import sqlite3, os, json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "pipeline.db")
OUT_PATH = os.path.join(os.path.dirname(__file__), "tracker.html")

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Application Tracker</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f9f9f7; color: #1a1a1a; padding: 32px 24px; }
  h1 { font-size: 22px; font-weight: 600; margin-bottom: 4px; }
  .sub { color: #666; font-size: 14px; margin-bottom: 24px; }
  .filters { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px; }
  .filter-btn { font-size: 12px; padding: 6px 14px; border-radius: 20px;
                border: 1px solid #ddd; background: #fff; cursor: pointer;
                transition: all 0.15s; }
  .filter-btn.active { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }
  table { width: 100%; border-collapse: collapse; background: #fff;
          border-radius: 12px; overflow: hidden;
          border: 1px solid #e5e5e2; font-size: 13px; }
  th { background: #f5f5f3; padding: 12px 16px; text-align: left;
       font-weight: 500; color: #666; font-size: 11px;
       text-transform: uppercase; letter-spacing: 0.04em;
       border-bottom: 1px solid #e5e5e2; }
  td { padding: 12px 16px; border-bottom: 1px solid #f0f0ed;
       vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: #fafaf8; }
  .score { font-weight: 600; color: #1a7f4b; }
  .score.low { color: #999; }
  .company { font-weight: 500; }
  .title { color: #444; }
  .date { color: #999; white-space: nowrap; }
  .status-select { font-size: 12px; padding: 4px 8px; border-radius: 6px;
                   border: 1px solid #ddd; background: #fff; cursor: pointer;
                   outline: none; }
  .status-select:focus { border-color: #1a1a1a; }
  .s-to_apply   { background: #fff8e6; color: #92600a; border-color: #f0d080; }
  .s-applied    { background: #e8f4fd; color: #1a5fa5; border-color: #90c4f0; }
  .s-phone_screen { background: #f0eaff; color: #5b3fa5; border-color: #c4aaf0; }
  .s-interview  { background: #e6f9f0; color: #0f6e46; border-color: #80ddb0; }
  .s-offer      { background: #e6ffe6; color: #0a6b0a; border-color: #80d080; }
  .s-rejected   { background: #fff0f0; color: #a51a1a; border-color: #f0a0a0; }
  .s-withdrawn  { background: #f5f5f5; color: #888; border-color: #ccc; }
  .notes-input { font-size: 12px; padding: 4px 8px; border-radius: 6px;
                 border: 1px solid transparent; background: transparent;
                 width: 180px; outline: none; color: #444; }
  .notes-input:hover { border-color: #ddd; background: #fff; }
  .notes-input:focus { border-color: #1a1a1a; background: #fff; }
  .apply-link { font-size: 12px; color: #1a5fa5; text-decoration: none; }
  .apply-link:hover { text-decoration: underline; }
  .save-btn { font-size: 11px; padding: 3px 8px; border-radius: 4px;
              border: 1px solid #ddd; background: #fff; cursor: pointer;
              color: #666; display: none; margin-left: 6px; }
  .save-btn:hover { background: #1a1a1a; color: #fff; border-color: #1a1a1a; }
  .saved-msg { font-size: 11px; color: #1a7f4b; margin-left: 6px; display: none; }
  .stats { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
  .stat { background: #fff; border: 1px solid #e5e5e2; border-radius: 10px;
          padding: 12px 18px; min-width: 100px; }
  .stat-num { font-size: 22px; font-weight: 600; }
  .stat-label { font-size: 11px; color: #999; margin-top: 2px; }
  .hidden { display: none; }
  .outreach-btn { font-size: 11px; padding: 3px 8px; border-radius: 4px;
                  border: 1px solid #ddd; background: #fff; cursor: pointer;
                  color: #666; }
  .outreach-btn:hover { background: #f0f0ed; }
  .modal { display: none; position: fixed; top: 0; left: 0; width: 100%;
           height: 100%; background: rgba(0,0,0,0.4); z-index: 100;
           align-items: center; justify-content: center; }
  .modal.open { display: flex; }
  .modal-box { background: #fff; border-radius: 12px; padding: 24px;
               max-width: 560px; width: 90%; position: relative; }
  .modal-title { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
  .modal-sub { font-size: 12px; color: #999; margin-bottom: 16px; }
  .modal-text { font-size: 13px; line-height: 1.6; background: #f9f9f7;
                border-radius: 8px; padding: 14px; white-space: pre-wrap; }
  .modal-close { position: absolute; top: 16px; right: 16px; background: none;
                 border: none; font-size: 18px; cursor: pointer; color: #999; }
  .copy-btn { margin-top: 12px; font-size: 12px; padding: 6px 14px;
              border-radius: 6px; border: 1px solid #ddd; background: #fff;
              cursor: pointer; }
  .copy-btn:hover { background: #1a1a1a; color: #fff; }
</style>
</head>
<body>

<h1>Application Tracker</h1>
<p class="sub" id="sub">Loading...</p>

<div class="stats" id="stats"></div>

<div class="filters">
  <button class="filter-btn active" onclick="filterBy('all')">All</button>
  <button class="filter-btn" onclick="filterBy('to_apply')">To Apply</button>
  <button class="filter-btn" onclick="filterBy('applied')">Applied</button>
  <button class="filter-btn" onclick="filterBy('phone_screen')">Phone Screen</button>
  <button class="filter-btn" onclick="filterBy('interview')">Interview</button>
  <button class="filter-btn" onclick="filterBy('offer')">Offer</button>
  <button class="filter-btn" onclick="filterBy('rejected')">Rejected</button>
</div>

<table id="tracker-table">
  <thead>
    <tr>
      <th>Score</th>
      <th>Company</th>
      <th>Role</th>
      <th>Source</th>
      <th>Date</th>
      <th>Status</th>
      <th>Notes</th>
      <th>Outreach</th>
      <th>Apply</th>
    </tr>
  </thead>
  <tbody id="tbody"></tbody>
</table>

<div class="modal" id="modal">
  <div class="modal-box">
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title" id="modal-title"></div>
    <div class="modal-sub" id="modal-sub"></div>
    <div class="modal-text" id="modal-text"></div>
    <button class="copy-btn" onclick="copyOutreach()">Copy to clipboard</button>
  </div>
</div>

<script>
const DATA = __DATA__;

let currentFilter = 'all';
const statuses = ['to_apply','applied','phone_screen','interview','offer','rejected','withdrawn'];
const statusLabels = {
  to_apply: 'To Apply', applied: 'Applied', phone_screen: 'Phone Screen',
  interview: 'Interview', offer: 'Offer', rejected: 'Rejected', withdrawn: 'Withdrawn'
};

function renderStats(rows) {
  const counts = {};
  statuses.forEach(s => counts[s] = 0);
  rows.forEach(r => { if (counts[r.status] !== undefined) counts[r.status]++; });
  const el = document.getElementById('stats');
  el.innerHTML = `
    <div class="stat"><div class="stat-num">${rows.length}</div><div class="stat-label">Total</div></div>
    <div class="stat"><div class="stat-num">${counts.to_apply}</div><div class="stat-label">To Apply</div></div>
    <div class="stat"><div class="stat-num">${counts.applied}</div><div class="stat-label">Applied</div></div>
    <div class="stat"><div class="stat-num">${counts.interview + counts.phone_screen}</div><div class="stat-label">In Process</div></div>
    <div class="stat"><div class="stat-num">${counts.offer}</div><div class="stat-label">Offers</div></div>
  `;
}

function renderTable(filter) {
  const rows = filter === 'all' ? DATA : DATA.filter(r => r.status === filter);
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = rows.map(r => `
    <tr class="row-${r.status}" data-id="${r.id}">
      <td><span class="score ${r.score < 4 ? 'low' : ''}">${r.score}/5</span></td>
      <td class="company">${r.company}</td>
      <td class="title">${r.title}</td>
      <td>${r.source}</td>
      <td class="date">${r.date}</td>
      <td>
        <select class="status-select s-${r.status}" onchange="updateStatus(${r.id}, this)">
          ${statuses.map(s => `<option value="${s}" ${s===r.status?'selected':''}>${statusLabels[s]}</option>`).join('')}
        </select>
      </td>
      <td>
        <input class="notes-input" value="${r.notes||''}" placeholder="Add note..."
               onInput="showSave(${r.id}, this)"
               onBlur="autoSaveNotes(${r.id}, this)">
        <button class="save-btn" id="save-${r.id}" onclick="saveNotes(${r.id})">Save</button>
        <span class="saved-msg" id="saved-${r.id}">Saved</span>
      </td>
      <td>${r.outreach ? `<button class="outreach-btn" onclick="showOutreach(${r.id})">View</button>` : ''}</td>
      <td><a class="apply-link" href="${r.url}" target="_blank">Apply →</a></td>
    </tr>
  `).join('');
  document.getElementById('sub').textContent =
    `${rows.length} role${rows.length !== 1 ? 's' : ''} ${filter === 'all' ? 'total' : '— ' + statusLabels[filter]}`;
}

function filterBy(status) {
  currentFilter = status;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  renderTable(status);
}

function updateStatus(id, select) {
  const newStatus = select.value;
  select.className = 'status-select s-' + newStatus;
  const row = DATA.find(r => r.id === id);
  if (row) row.status = newStatus;
  fetch('/__update_status__', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({id, status: newStatus})
  }).catch(() => {});
  renderStats(DATA);
}

function showSave(id, input) {
  document.getElementById('save-' + id).style.display = 'inline';
  document.getElementById('saved-' + id).style.display = 'none';
}

function saveNotes(id) {
  const input = document.querySelector(`tr[data-id="${id}"] .notes-input`);
  const notes = input.value;
  const row = DATA.find(r => r.id === id);
  if (row) row.notes = notes;
  document.getElementById('save-' + id).style.display = 'none';
  document.getElementById('saved-' + id).style.display = 'inline';
  setTimeout(() => document.getElementById('saved-' + id).style.display = 'none', 2000);
}

function autoSaveNotes(id, input) {
  saveNotes(id);
}

function showOutreach(id) {
  const row = DATA.find(r => r.id === id);
  if (!row) return;
  document.getElementById('modal-title').textContent = row.title + ' — ' + row.company;
  document.getElementById('modal-sub').textContent = 'LinkedIn outreach draft';
  document.getElementById('modal-text').textContent = row.outreach;
  document.getElementById('modal').classList.add('open');
}

function closeModal() {
  document.getElementById('modal').classList.remove('open');
}

function copyOutreach() {
  const text = document.getElementById('modal-text').textContent;
  navigator.clipboard.writeText(text).then(() => {
    const btn = document.querySelector('.copy-btn');
    btn.textContent = 'Copied!';
    setTimeout(() => btn.textContent = 'Copy to clipboard', 2000);
  });
}

window.onclick = e => { if (e.target === document.getElementById('modal')) closeModal(); };

renderStats(DATA);
renderTable('all');
</script>
</body>
</html>"""


def run():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row

    rows = con.execute("""
        SELECT
            a.id as app_id,
            p.id as posting_id,
            p.title, p.company, p.url, p.source,
            e.score, e.grade, e.outreach_draft,
            a.status, a.notes,
            date(e.evaluated_at) as date
        FROM evaluations e
        JOIN postings p ON p.id = e.posting_id
        LEFT JOIN applications a ON a.posting_id = p.id
        WHERE e.surfaced = 1
        ORDER BY e.score DESC
    """).fetchall()

    # Auto-create application records for surfaced postings that don't have one
    cur = con.cursor()
    for row in rows:
        if row["app_id"] is None:
            cur.execute("""
                INSERT OR IGNORE INTO applications (posting_id, evaluation_id, status)
                SELECT p.id, e.id, 'to_apply'
                FROM evaluations e
                JOIN postings p ON p.id = e.posting_id
                WHERE p.id = ?
            """, (row["posting_id"],))
    con.commit()

    # Re-fetch with app records
    rows = con.execute("""
        SELECT
            a.id as app_id,
            p.id as posting_id,
            p.title, p.company, p.url, p.source,
            e.score, e.grade, e.outreach_draft,
            a.status, a.notes,
            date(e.evaluated_at) as date
        FROM evaluations e
        JOIN postings p ON p.id = e.posting_id
        JOIN applications a ON a.posting_id = p.id
        WHERE e.surfaced = 1
        ORDER BY e.score DESC
    """).fetchall()

    con.close()

    data = []
    for r in rows:
        data.append({
            "id":       r["app_id"],
            "title":    r["title"],
            "company":  r["company"],
            "url":      r["url"],
            "source":   r["source"],
            "score":    r["score"],
            "grade":    r["grade"],
            "status":   r["status"] or "to_apply",
            "notes":    r["notes"] or "",
            "outreach": r["outreach_draft"] or "",
            "date":     r["date"] or "",
        })

    html = HTML.replace("__DATA__", json.dumps(data))

    with open(OUT_PATH, "w") as f:
        f.write(html)

    print(f"Tracker saved: {OUT_PATH}")
    print(f"{len(data)} surfaced roles in tracker.")
    return OUT_PATH


if __name__ == "__main__":
    path = run()
    os.system(f"open '{path}'")
