# multi-autoapply-lite

A lightweight, local-only job auto-apply tool built with Playwright + SQLite.

**Purpose:** Personal automation for "quick apply"/"easy apply" jobs on LinkedIn, Indeed, Naukri, and Glassdoor. It attempts autofill for simple application flows, stores applied/skipped jobs in SQLite to avoid duplicates, and uses Playwright persistent profiles so you can stay logged in.

> ⚠️ Use responsibly and for personal use only. Respect each website's Terms of Service.

---

## Features

- Login automation using Playwright persistent sessions (user profile saved under `data/playwright_profiles`)
- Job search automation: LinkedIn, Indeed, Naukri, Glassdoor
- Auto-apply for "quick apply" or "easy apply" flows (LinkedIn & Indeed heuristics implemented)
- SQLite database (`jobs.db`) to store applied/skipped jobs
- CLI: `python main.py apply`
- Config via `.env`

---

## Requirements

- Python 3.10+
- Playwright (browsers)
- python-dotenv
- tqdm (progress printing)

Install:

```bash
pip install -r requirements.txt
python -m playwright install
```

python main.py apply --max 5 --no-headless
