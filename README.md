# Streaming Usage Audit

Local CLI tool that checks which of your streaming subscriptions you're
actually using, by pulling viewing history from each platform and
generating a dark-themed `report.html` ranked by days since last watched.

Covers Netflix, Prime Video, Hulu, Disney+, and Paramount+ using two
different strategies, because two of these platforms have real export
tools and three don't.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## Netflix and Prime Video: CSV import

These two platforms have official personal-data export tools. Nothing is
scraped for them — download the export and drop the CSV in `data/`.

**Netflix**: Account > Profile & Parental Controls > Viewing activity >
Download all. (Or the full export at `netflix.com/account/getmyinfo`,
which includes the same history under a differently-named file — look for
the one with `Title`/`Date` columns.) Save it to
`data/netflix_viewing_history.csv`, or point `NETFLIX_CSV_PATH` at wherever
you put it.

**Prime Video**: Amazon has no dedicated one-click export for this.
Go to `amazon.com/gp/privacycentral/dsar/preview.html` > Request My Data,
and choose the "Prime Video" data group (Amazon has also called this
"Digital Orders/Subscriptions" — the exact category name has changed over
time). The response arrives by email as a zip of CSVs; find the one with
watch history in it and save it to
`data/amazon_prime_video_history.csv` (or point `AMAZON_CSV_PATH` at it).

Amazon's column names are **not stable** across export requests. Before
running the tool, open your actual CSV, check the header row, and update
`TITLE_COLUMN` / `DATE_COLUMN` at the top of `amazon.py` to match. If dates
fail to parse, add your export's date format to `DATE_FORMATS` in that
file.

## Hulu, Disney+, Paramount+: browser scraping

Neither Disney (which also owns Hulu) nor Paramount offer anything fast
enough to use here — Disney's privacy portal is a formal CCPA/GDPR request
with identity verification and no fixed turnaround, and Paramount+ only
takes export requests by email to `privacy@paramount.com` with up to 45
days to respond. So these three are scraped from a real, authenticated
browser session instead.

A dedicated Chromium profile (`.browser_profile/` by default, or
`SCRAPERS_PROFILE_DIR` if set) is launched **non-headless** — these sites
flag and block headless browsers. The first time you run the tool, log in
manually in the window that opens for each site; the session is saved in
that profile directory and reused on later runs, so you shouldn't need to
log in again unless the session expires.

**These three scrapers ship with placeholder selectors.** Hulu, Disney+,
and Paramount+ change their DOM without notice, and there's no way to
verify selectors against a live authenticated session while writing this
tool. Every selector and history-page URL in `scrapers/hulu.py`,
`scrapers/disneyplus.py`, and `scrapers/paramountplus.py` is marked as an
unverified placeholder and needs to be checked against the real page
before you trust the output.

To do that, set `SCRAPERS_DEBUG=1` before running. Each scraper will open
the history page and then pause (in your terminal, waiting on Enter)
before it tries to read anything, so you can open devtools in the visible
browser window, inspect the actual DOM, and update the selectors in the
corresponding file to match:

```bash
SCRAPERS_DEBUG=1 python main.py
```

Hulu's default history view only exposes watch order, not per-item dates —
`watched_date` is always `None` for Hulu, and the report treats it as
"unknown" recency rather than guessing. Disney+ and Paramount+ may or may
not expose dates depending on what's actually on their history pages;
their `HISTORY_DATE_SELECTOR` placeholders will just fail to match (and
fall back to `None`) if there's no date to find.

## When a scraper breaks: automated fix attempts

Sites change their DOM without notice, so a scraper that worked last month
can silently start returning nothing. `health.py` tracks consecutive
failures per scraped platform in `.scraper_health.json` (local-only,
gitignored — never committed). A "failure" is either:

- the fetch raised an error (timeout, selector never appeared, login never
  detected), or
- the fetch succeeded but found 0 events on a run where a previous run
  found some.

Deliberately **not** a failure signal: unchanged output across runs. This
tool exists to find platforms you've stopped using, so an idle platform
returning the same small/zero result every run is the tool working
correctly, not a broken scraper — treating "no change" as breakage would
make it fire constantly on exactly the accounts it's supposed to flag.

Every scraper failure also gets an HTML snapshot + full-page screenshot
saved to `debug_artifacts/<platform>/<timestamp>/` via
`scrapers/base.run_scrape()` (also gitignored — it's your actual logged-in
account UI). Once a platform crosses `FAILURE_THRESHOLD` (2, in
`health.py`) consecutive failures, `main.py` shells out to the local
Claude Code CLI (`claude -p ...`) telling it to load the `fix-scraper`
skill and patch the broken selectors using those artifacts — no live
browser session required for the fix itself. It opens a PR and never
merges automatically; a selector change guessed from one static snapshot
needs a real successful run before it's trusted. This requires the
`claude` CLI on `PATH` wherever you run `main.py` (e.g. via cron); if it's
missing, `main.py` logs that and moves on rather than failing the run.

Adding a platform that needs scraping (no export tool)? Use the
`new-scraper` skill (`.claude/skills/new-scraper/`) to scaffold it against
the same `run_scrape()` pattern so it's health-tracked and fix-eligible
from day one.

## Running

```bash
python main.py
```

This runs all five fetchers, prints a per-platform summary to the
terminal, and writes `report.html` (or wherever `REPORT_OUTPUT_PATH`
points) — open it in a browser. It's a single self-contained file with no
external dependencies, so it works fine opened directly from disk.

The report has two views of the same data: a card per platform (last
watched, titles found, any fetch error) and a table ranked by idle days
descending, so the most-neglected subscription is easy to spot. Anything
idle more than `IDLE_THRESHOLD_DAYS` (30 by default, in `config.py`) gets
a visual highlight. Platforms with no dated history sort to the bottom as
"unknown" rather than reading as most- or least-idle.

## Configuration

All of this is in `config.py`, overridable via environment variables of
the same name:

| Variable | Purpose |
|---|---|
| `SCRAPERS_PROFILE_DIR` | Persistent Chromium profile directory |
| `NETFLIX_CSV_PATH` | Path to the Netflix export |
| `AMAZON_CSV_PATH` | Path to the Prime Video export |
| `REPORT_OUTPUT_PATH` | Where `report.html` is written |
| `SCRAPERS_DEBUG` | Set to `1` to pause scrapers after each page load |

## What this tool does not do

No scheduling or automation — it's a one-shot CLI run. No cloud deployment
and no credentials stored anywhere: it works by reusing an already
logged-in local browser session, not by storing passwords. No private-API
reverse engineering — only official CSV exports and DOM scraping of pages
you're already logged into.
