---
name: fix-scraper
description: Diagnose and patch a broken platform scraper (Netflix / Prime Video / Hulu / Disney+) in the streaming usage audit tool, using saved failure artifacts (HTML snapshot + screenshot) rather than a live session. Use when main.py's health tracking has flagged a platform as broken and triggered this skill automatically, or when explicitly asked to fix a specific platform's scraper.
---

# Fix a broken scraper

`scrapers/netflix.py`, `scrapers/primevideo.py`, `scrapers/hulu.py`, and
`scrapers/disneyplus.py` share one lifecycle via `scrapers/base.run_scrape()`
(launch persistent browser → navigate → manual login on first run → call
the module's `_scrape(page) -> PlatformResult`). Each `_scrape` does its
**own** extraction — there are no shared selector constants — so a fix is
always local to one module:

| Module | How it reads data | What usually breaks |
|---|---|---|
| `netflix.py` | DOM of `netflix.com/viewingactivity` — `[data-uia="activity-row"]` rows, `.col.date` / `.col.title` | row selectors; date-format/locale |
| `primevideo.py` | DOM of the Amazon watch-history page — `[data-testid="activity-history-items"]`, `wh-date-*` headers, `activity-history-item` blocks | the `data-testid` names |
| `hulu.py` | JSON: `GET discover.hulu.com/content/v5/view_hubs/home` → component named "Continue Watching" → `items[].metrics_info.target_name` | endpoint path/params; the component name; item field names |
| `disneyplus.py` | DOM rail: `[data-testid="set"]:has(a[data-testid="cw-set-item-metadata"])` → `a[data-testid="set-item"][aria-label]`, title parsed off the aria-label | the `data-testid` names; the aria-label format the `_TAIL` regex strips |

`health.py` tracks consecutive failures per platform; once one crosses
`FAILURE_THRESHOLD`, `main.py` shells out to `claude -p` with this skill
named in the prompt.

**You will not have a live authenticated session.** Work only from the
saved failure artifacts — do not launch the scraper yourself to "check".

## Steps

1. Identify the platform (named in the prompt; ask if ambiguous).
2. Find its most recent artifacts under `debug_artifacts/<platform>/<timestamp>/`:
   - `error.txt` — the exception/error message
   - `page.html` — full HTML snapshot at failure time (may be missing)
   - `screenshot.png` — full-page screenshot at failure time (same caveat)
3. **Read `error.txt` first** and classify:
   - "not logged in and no interactive terminal…" / navigation / login-check
     failure → **not DOM/endpoint drift**. The saved session expired or the
     login-check selector is stale. Say so in the PR; don't invent new
     data selectors. If the `LOGGED_IN_SELECTOR` looks wrong against
     `page.html`, fixing that is fair game.
   - "endpoint shape likely changed" / "markup changed" / a `KeyError` /
     "-> HTTP 4xx" → the data source moved. Proceed.
4. For a **DOM** scraper (netflix/primevideo/disneyplus): cross-reference
   `page.html` and `screenshot.png` for the current markup, and update the
   selectors / `data-testid`s / the aria-label-stripping regex in that one
   module. Keep them plain CSS in the existing style.
5. For the **Hulu JSON** scraper: `page.html` is the hub *page*, not the
   API response, so it may not show the fix directly. Check whether the
   endpoint URL, the `"Continue Watching"` component name, or the
   `metrics_info.target_name` field is what moved; note in the PR that
   this needs a real run to confirm since the artifact can't show the API
   body.
6. Update the "verified against … 2026-…" comment in the module to the
   date you matched it against a snapshot; keep the framing honest (you
   matched a static snapshot, you did not run it).
7. `python3 -m py_compile scrapers/<platform>.py` to catch syntax errors.
8. Reset that platform's entry in `.scraper_health.json` (delete the key,
   or set `consecutive_failures` to `0` and `fix_triggered` to `false`).
   If a Hulu/Disney+ title *set* genuinely changed as part of the fix,
   also delete that platform's key from `.activity_snapshots.json` so the
   next run rebaselines instead of reporting a spurious "list changed".
9. Commit on a new branch (`fix/<platform>-scraper-<date>`) and open a PR.
   Never merge it — a change guessed from one static snapshot needs a
   real successful run before anyone should trust it.
