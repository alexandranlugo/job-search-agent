# job-search-agent

A personal agentic pipeline that automates job discovery, scoring, and outreach for a targeted job search in data analytics and data science.

## What it does

Instead of manually browsing job boards every day, this pipeline runs automatically each morning at 7AM and delivers a digest of high-match roles directly to your inbox — with tailored resumes already attached.

- Scrapes Built In NYC (25 pages daily) and 26 companies via Greenhouse, Lever, and Ashby APIs
- Filters postings by title, seniority, location, and required years of experience:
  - NYC-verified location filter — a bare "Hybrid" or "Remote" tag no longer passes on faith; it has to actually name New York (or be genuinely remote-anywhere) to get through
  - Built In's explicit seniority tag ("Junior," "Mid level," "Senior level," "Expert/Leader") backs up title-keyword filtering, catching senior roles with deceptively plain titles
  - Hard-skips postings that explicitly require 3+ years of experience, rather than relying on soft LLM scoring alone
- Scores every filtered posting against a candidate CV using the Anthropic API with a 5-dimension weighted scoring framework
- Surfaces roles scoring 3.5/5.0 or above in a daily HTML digest
- Tracks which roles have already been shown, so the digest only ever contains genuinely new matches — nothing resurfaces indefinitely
- Always sends the digest email, even on 0-match days, so a missing email reliably means something broke rather than "no news"
- Auto-generates a tailored one-page resume PDF (and optional cover letter) for every surfaced role, rendered directly via Playwright — no external dependencies — and attaches them to the digest email
- Generates a LinkedIn outreach draft for each surfaced role
- One-click handoff to [career-ops](https://github.com/santifer/career-ops) for the full 7-block evaluation, STAR interview prep, and application tracking
- Runs on a daily cron schedule with full logging

## Scoring framework

| Dimension | Weight |
|-----------|--------|
| CV match | 40% |
| North star alignment | 25% |
| Compensation | 15% |
| Culture signals | 10% |
| Red flags | 10% |

Roles scoring 3.5+ are surfaced in the digest with a resume attached. Everything else is logged but not shown.

## Stack

- Python 3.12
- Playwright (web scraping + PDF rendering)
- Anthropic API (claude-sonnet-4-6)
- SQLite (posting/evaluation/application tracking)
- cron (scheduling)

## Project structure

```
job-search-agent/
├── ingestion/
│   ├── filters.py             # Shared title/location filter config loading
│   ├── scrape_builtinnyc.py   # Built In NYC scraper (pagination, location/seniority filtering)
│   ├── scrape_greenhouse.py   # Greenhouse, Lever, Ashby API scrapers
│   ├── scrape_wellfound.py    # Wellfound scraper (cookie auth)
│   └── add_job.py             # Manually add any job URL for scoring
├── scoring/
│   ├── evaluate.py            # Anthropic API scoring engine
│   ├── generate_resume.py     # Tailored PDF resume generation (self-contained, via Playwright)
│   └── generate_cover_letter.py
├── output/
│   ├── digest.py              # Daily HTML digest generator (tracks already-sent roles)
│   ├── send_email.py          # Sends the digest, with resume PDFs attached
│   └── tracker.py             # Application tracker UI
├── db/
│   └── init_db.py             # SQLite schema
├── config/                    # your cv.md, profile.yml, portals.yml (gitignored)
│   └── *.example.*            # copy these to get started
├── scripts/
│   ├── html2pdf.py            # Batch-render saved resume HTML to PDF
│   └── ...                    # Debug and one-off setup utilities
├── run_pipeline.sh            # Master pipeline runner
└── requirements.txt
```

## Setup

```bash
git clone https://github.com/alexandranlugo/job-search-agent
cd job-search-agent

pip install -r requirements.txt
playwright install chromium

python db/init_db.py
```

### Make it yours

Nothing about the candidate is hardcoded — the scorer, resume writer, and cover
letter writer all read the three config files below. Copy each example and edit it:

```bash
cp .env.example                  .env
cp config/cv.example.md          config/cv.md
cp config/profile.example.yml    config/profile.yml
cp config/portals.example.yml    config/portals.yml
```

| File | What it controls |
|------|------------------|
| `.env` | `ANTHROPIC_API_KEY` (required), Gmail address + [App Password](https://myaccount.google.com/apppasswords) to email yourself the digest |
| `config/cv.md` | Your resume in plain markdown. Injected verbatim into every prompt — the generator never invents experience, so anything missing here won't appear |
| `config/profile.yml` | Target roles, salary range and floor, location preferences, scoring nudges. This is what postings are actually judged against |
| `config/portals.yml` | Which companies to scrape, and the title/location keywords that gate everything before scoring |

All four are gitignored, so your details never end up in a commit.

Retargeting to a different field is a config change, not a code change — swap the
keywords in `portals.yml` (`title_filter.positive`) and the target roles in
`profile.yml`, and the pipeline follows.

**Adding companies.** Find a company's board slug from its careers URL, verify it
returns HTTP 200, then add it to `portals.yml`:

```
Greenhouse   https://boards-api.greenhouse.io/v1/boards/<slug>/jobs
Lever        https://api.lever.co/v0/postings/<slug>?mode=json
Ashby        https://api.ashbyhq.com/posting-api/job-board/<slug>
```

Then confirm the whole thing runs:

```bash
bash run_pipeline.sh
```

## Usage

Run manually:
```bash
bash run_pipeline.sh
```

Open today's digest:
```bash
open output/digests/digest_$(date +%Y-%m-%d).html
```

Add a specific job posting manually:
```bash
python ingestion/add_job.py <job-url>
```

## Running it daily

The whole point is not having to remember to run it. Pick one of the two below —
you only need one.

First, confirm which interpreter to use. Schedulers run with a minimal `PATH` and
won't find a conda or venv Python, which is the most common reason a scheduled run
fails while a manual run works:

```bash
which python3      # use this full path below
```

### macOS — launchd (recommended)

cron still exists on macOS but silently fails for a lot of people, because modern
macOS requires Full Disk Access for `/usr/sbin/cron` before it can read your files.
launchd is the supported path and reports errors properly.

Create `~/Library/LaunchAgents/com.yourname.job-search-digest.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.yourname.job-search-digest</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/absolute/path/to/job-search-agent/run_pipeline.sh</string>
    </array>
    <!-- Runs at 7:00 AM daily. If the machine is asleep at 7, launchd runs it
         at the next wake rather than skipping the day. -->
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>7</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <!-- Schedulers don't inherit your shell PATH — point at a real interpreter. -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHON</key><string>/absolute/path/to/python3</string>
    </dict>
    <key>StandardOutPath</key>
    <string>/absolute/path/to/job-search-agent/logs/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>/absolute/path/to/job-search-agent/logs/launchd.err.log</string>
</dict>
</plist>
```

Then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.yourname.job-search-digest.plist
launchctl list | grep job-search-digest      # confirm it's registered
```

To turn it off later:

```bash
launchctl unload ~/Library/LaunchAgents/com.yourname.job-search-digest.plist
```

Unloading stops it now, but anything left in `~/Library/LaunchAgents` reloads at
your next login — rename or delete the plist to disable it for good.

### Linux — cron

```bash
(crontab -l 2>/dev/null; \
 echo "0 7 * * * PYTHON=/usr/bin/python3 /absolute/path/to/job-search-agent/run_pipeline.sh") \
 | crontab -
```

Use absolute paths throughout; cron does not run from your repo directory.

### Checking it actually ran

Every run appends to a dated log, so a missing log means it never fired:

```bash
tail -40 logs/pipeline_$(date +%Y-%m-%d).log
```

The pipeline emails you every day it runs, including days with zero matches
("no new matches today"). That's deliberate — a silent inbox means something
broke, rather than leaving you guessing whether it was just a quiet day.

## Why I built this

The modern job search has two core inefficiencies: discovery is noisy and evaluation is inconsistent. This pipeline eliminates both — every minute spent on the job search is high-value: outreach, interviews, and relationships.

It also demonstrates end-to-end agentic workflow design, multi-source API integration, AI-powered evaluation logic, and full ownership from architecture to deployment — including diagnosing and fixing real production issues (a scraper that silently crashed on timeout, a location filter that let non-NYC roles through, a digest that never stopped resurfacing the same postings) rather than just shipping a first version and walking away.

---

Built by [Alexandra Lugo](https://www.linkedin.com/in/lugoalexandra/) | [alexandralugo.com](https://alexandralugo.com)
