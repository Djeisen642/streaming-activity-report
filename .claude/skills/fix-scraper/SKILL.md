---
name: fix-scraper
description: Diagnose and patch a broken browser scraper (Hulu/Disney+/Paramount+) in the streaming usage audit tool, using saved failure artifacts (HTML snapshot + screenshot) rather than a live session. Use when main.py's health tracking has flagged a platform as broken and triggered this skill automatically, or when explicitly asked to fix a specific platform's scraper.
---

# Fix a broken scraper

`scrapers/hulu.py`, `scrapers/disneyplus.py`, and `scrapers/paramountplus.py`
all share one lifecycle via `scrapers/base.run_scrape()`. Their CSS
selectors are placeholders because these sites' DOM can't be verified
without a live authenticated session. `health.py` tracks consecutive
scrape failures per platform; once one crosses `FAILURE_THRESHOLD`,
`main.py` shells out to `claude -p` with this skill named in the prompt.

**You will not have a live authenticated browser session.** Work only
from the saved failure artifacts — do not attempt to launch the scraper
yourself to "check."

## Steps

1. Identify the platform (named in the prompt that invoked you; ask if
   ambiguous).
2. Find its most recent artifacts under `debug_artifacts/<platform>/<timestamp>/`:
   - `error.txt` — the exception/error message
   - `page.html` — full HTML snapshot at failure time (may be missing if
     the page never loaded)
   - `screenshot.png` — full-page screenshot at failure time (same caveat)
3. Read `error.txt` first. If it's a navigation/login failure rather than
   a selector-not-found problem — the login check itself failed, the page
   never loaded, a network error — this is likely not DOM drift. Say so
   plainly in the PR description instead of guessing at new selectors
   that wouldn't fix a login problem anyway.
4. Otherwise, cross-reference `page.html` and `screenshot.png` to find the
   real, current selectors for whichever of these the platform uses:
   - `LOGGED_IN_SELECTOR`
   - `HISTORY_ITEM_SELECTOR`
   - `HISTORY_TITLE_SELECTOR` (scoped within an item)
   - `HISTORY_DATE_SELECTOR` (scoped within an item, if the platform has one)
5. Update the constants in `scrapers/<platform>.py`. Keep them as plain
   CSS selector strings in the existing style — don't switch to XPath or
   text-matching unless CSS genuinely can't express the match.
6. Keep the "PLACEHOLDER" framing rather than declaring them verified —
   update the comment to note you matched them against a specific
   snapshot on a specific date, since the live DOM can drift again after
   this fix ships.
7. Run `python3 -m py_compile scrapers/<platform>.py` to catch syntax
   errors. You cannot run the scraper live to confirm the fix actually
   works — say that explicitly in the PR description rather than implying
   it's verified.
8. Reset that platform's entry in `.scraper_health.json` (delete the key,
   or set `consecutive_failures` to `0` and `fix_triggered` to `false`) so
   the next real run gives an honest read on whether the fix held.
9. Commit on a new branch (`fix/<platform>-scraper-<date>`) and open a PR.
   Never merge it — a selector change guessed from one static snapshot
   needs a real successful run before anyone should trust it.
