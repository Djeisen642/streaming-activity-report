# Streaming Usage Audit

Local CLI tool that checks which of your streaming subscriptions you're
actually using, by reading your activity from each platform's own
logged-in website and generating a dark-themed `report.html` ranked by
days since last watched.

Covers Netflix, Prime Video, Hulu, and Disney+. All four are read from a
real, authenticated browser session — none of them offers an export fast
enough to be worth waiting on. What the tool can get differs by platform:

| Platform | Source | Watch dates? |
|---|---|---|
| Netflix | the `viewingactivity` page | **yes** — real per-title dates |
| Prime Video | the account "Watch History" page | **yes** — real per-title dates |
| Hulu | the home hub's "Continue Watching" rail (JSON) | **no** — see below |
| Disney+ | the home page's "Continue Watching" rail (DOM) | **no** — see below |

Hulu and Disney+ publish no dated watch history anywhere a browser can
reach — not the page DOM, not the JSON their web apps fetch. For those two
the tool snapshots the set of titles in "Continue Watching" each run and
reports **when that set last changed** as the activity date. It's a
coarser signal (its precision is only as fine as how often you run the
tool), and the report labels it with a `↻` and its own wording so it's
never confused with a real watch date.

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

## The browser session

A dedicated Chromium profile (`.browser_profile/` by default, or
`SCRAPERS_PROFILE_DIR` if set) is launched **non-headless** — these sites
flag and block headless browsers. The first time you run the tool, log in
manually in the window that opens for each site; the session is saved in
that profile directory and reused on later runs, so you shouldn't need to
log in again unless it expires. No passwords are ever stored by the tool —
it only reuses the cookies in that profile.

Manual login only happens when the run has an interactive terminal (stdin
is a TTY) to prompt at, and it gives up after 5 minutes. A non-interactive
run (cron, `nohup`, some editor terminals) with a missing or expired
session doesn't hang waiting for a login that can't happen — it fails that
platform fast with a "no interactive terminal to log in from" error,
records it like any other scrape failure, and moves on. Refresh the
session by running the tool once interactively.

**One profile per platform.** The figures reflect whichever account
profile is active in the browser session — the tool doesn't switch between
profiles. If your household shares accounts, the "last watched" is for the
profile you were on, not the whole account; the report notes which one.

### CSV alternative for Netflix / Prime Video

`netflix.py` and `amazon.py` at the repo root parse the official data
exports instead (the complete history rather than the most-recent rows the
web pages render). They're not wired into `main.py` by default — swap them
into `SCRAPED_FETCHERS` if you'd rather feed an export than run a browser.
Get the exports from Netflix (Account → Viewing activity → Download all →
`data/netflix_viewing_history.csv`) and Amazon (Privacy Central → Request
My Data → Prime Video → `data/amazon_prime_video_history.csv`); Amazon's
column names vary by request, so check `TITLE_COLUMN` / `DATE_COLUMN` in
`amazon.py` against your file.

### Inspecting a page while it loads

Set `SCRAPERS_DEBUG=1` and each scraper pauses (waiting on Enter in your
terminal) right after the page loads, so you can open devtools in the
visible window before it reads anything. Run it straight from a real
terminal — with no TTY the pause is skipped with a note on stderr.

## When a scraper breaks: automated fix attempts

Sites change without notice, so a scraper that worked last month can start
returning nothing. `health.py` tracks consecutive failures per platform in
`.scraper_health.json` (local-only, gitignored). A "failure" is either the
fetch raising an error (a scraper `raise`s when its data source's *shape*
is gone, rather than returning an empty list), or a fetch that found 0
items on a run where a previous run found some.

Deliberately **not** a failure signal: unchanged output across runs. This
tool exists to find platforms you've stopped using, so an idle platform
returning the same small/zero result every run is the tool working
correctly, not a break.

Every failure also saves an HTML snapshot + full-page screenshot to
`debug_artifacts/<platform>/<timestamp>/` (gitignored — it's your actual
account UI). Once a platform crosses `FAILURE_THRESHOLD` (2, in
`health.py`) consecutive failures, `main.py` shells out to the local
Claude Code CLI (`claude -p ...`) to load the `fix-scraper` skill and
patch that module from those artifacts — no live session needed for the
fix. It opens a PR and never merges automatically. Needs the `claude` CLI
on `PATH` wherever `main.py` runs; if it's missing, the run logs that and
moves on.

Adding a platform? Use the `new-scraper` skill
(`.claude/skills/new-scraper/`).

## Running

```bash
python main.py
```

Runs all four fetchers, prints a per-platform summary, and writes
`report.html` (or `REPORT_OUTPUT_PATH`) — a single self-contained file,
fine to open directly from disk.

The report has two views of the same data: a card per platform (last
activity, titles found, any fetch error) and a table ranked by idle days
descending, so the most-neglected subscription is easy to spot. Anything
idle more than `IDLE_THRESHOLD_DAYS` (30 by default, in `config.py`) gets
a visual highlight. Platforms with no signal at all — a fetch that
errored, or a first-ever run for Hulu/Disney+ with no snapshot baseline
yet — sort to the bottom as "unknown".

## Tests

```bash
.venv/bin/python -m unittest
```

stdlib `unittest`, no browser or network. Covers the logic a live
`main.py` run can't safely exercise: the `health.py` failure state machine
(every threshold crossing shells out to `claude -p`), `snapshots.py`'s
run-to-run activity-date derivation, the report's three activity bases and
ranking, and the scraper parse helpers (against strings captured from the
real sites). The scraper *fetch* paths need a logged-in browser and aren't
covered here.

## Configuration

All in `config.py`, overridable via environment variables of the same name:

| Variable | Purpose |
|---|---|
| `SCRAPERS_PROFILE_DIR` | Persistent Chromium profile directory |
| `REPORT_OUTPUT_PATH` | Where `report.html` is written |
| `DEBUG_ARTIFACTS_DIR` | Where failure HTML/screenshots are saved |
| `SCRAPER_HEALTH_PATH` | Consecutive-failure state file |
| `ACTIVITY_SNAPSHOT_PATH` | Continue Watching title snapshots (Hulu/Disney+) |
| `NETFLIX_CSV_PATH` / `AMAZON_CSV_PATH` | Export paths for the CSV alternative |
| `SCRAPERS_DEBUG` | `1` to pause each scraper after page load |

## What this tool does not do

No scheduling — it's a one-shot CLI run. No cloud deployment, no stored
credentials. No private-API reverse engineering beyond reading the same
endpoints and pages the sites' own web apps use, from a session you're
already logged into. It does not switch account profiles.
