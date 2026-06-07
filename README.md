# job-search-agent

A personal agentic pipeline that automates job discovery, scoring, and outreach for a targeted job search in data analytics and data science.

## What it does

Instead of manually browsing job boards every day, this pipeline runs automatically each morning at 7AM and delivers a digest of high-match roles directly to your inbox.

- Scrapes Built In NYC (25 pages daily) and 15+ target companies via Greenhouse, Lever, and Ashby APIs
- Filters postings by title, seniority, and location (NYC, remote, or hybrid only)
- Scores every filtered posting against a candidate CV using the Anthropic API with a 5-dimension weighted scoring framework
- Surfaces only roles scoring 4.0/5.0 or above in a daily HTML digest
- Generates a LinkedIn outreach draft for each surfaced role
- One-click handoff to career-ops for full resume generation, STAR interview prep, and application tracking
- Runs on a daily cron schedule with full logging

## Scoring framework

| Dimension | Weight |
|-----------|--------|
| CV match | 40% |
| North star alignment | 25% |
| Compensation | 15% |
| Culture signals | 10% |
| Red flags | 10% |

Only roles scoring 4.0+ are surfaced. Everything else is logged but not shown.

## Stack

- Python 3.12
- Playwright (web scraping)
- Anthropic API (claude-sonnet-4-6)
- SQLite (application tracking)
- cron (scheduling)

## Project structure

```
job-search-agent/
├── ingestion/
│   ├── scrape_builtinnyc.py   # Built In NYC scraper with pagination
│   ├── scrape_greenhouse.py   # Greenhouse, Lever, Ashby API scrapers
│   └── scrape_wellfound.py    # Wellfound scraper (cookie auth)
├── scoring/
│   └── evaluate.py            # Anthropic API scoring engine
├── output/
│   ├── digest.py              # Daily HTML digest generator
│   └── tracker.py             # Application tracker UI
├── db/
│   └── init_db.py             # SQLite schema
├── config/                    # cv.md and profile.yml (not committed)
├── scripts/                   # Debug and setup utilities
├── run_pipeline.sh            # Master pipeline runner
└── requirements.txt
```

## Setup

```bash
git clone https://github.com/alexandranlugo/job-search-agent
cd job-search-agent

pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Add your ANTHROPIC_API_KEY to .env

python db/init_db.py
python scripts/test_api.py
```

## Usage

Run manually:
```bash
bash run_pipeline.sh
```

Or let the cron job run it at 7AM daily:
```bash
(crontab -l; echo "0 7 * * * /path/to/job-search-agent/run_pipeline.sh") | crontab -
```

Open today's digest:
```bash
open output/digests/digest_$(date +%Y-%m-%d).html
```

## Configuration

Target companies, keywords, and filters are configured via `config/profile.yml` and `config/cv.md` (symlinked from [career-ops](https://github.com/santifer/career-ops)).

## Why I built this

The modern job search has two core inefficiencies: discovery is noisy and evaluation is inconsistent. This pipeline eliminates both — every minute spent on the job search is high-value: outreach, interviews, and relationships.

It also demonstrates end-to-end agentic workflow design, multi-source API integration, AI-powered evaluation logic, and full ownership from architecture to deployment.

---

Built by [Alexandra Lugo](https://www.linkedin.com/in/lugoalexandra/) | [alexandralugo.com](https://alexandralugo.com)
