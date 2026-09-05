---
name: new-scraper
description: Scaffold a new streaming-platform scraper module for the streaming usage audit tool, matching the Netflix/Prime/Hulu/Disney+ pattern (Playwright via the shared scrapers/base.py lifecycle). Use when the user wants to add a platform to the audit.
---

# Add a new scraped platform

Every scraped platform shares one lifecycle via `scrapers/base.run_scrape()`:
launch persistent context → navigate → manual login on first run → call a
platform-specific `_scrape(page) -> PlatformResult` → on any failure,
`run_scrape` saves HTML + screenshot artifacts and reports the error.

Before scaffolding, confirm with the user and decide two things:

1. **Does this platform actually lack a fast export?** If it has one (even
   slow/manual), a CSV/JSON importer at the repo root (like `netflix.py` /
   `amazon.py`) is the better path — don't default to scraping.
2. **Does the platform publish a dated watch history you can reach from a
   logged-in browser?**
   - **Yes** (like Netflix `viewingactivity`, Prime `watch-history`):
     `_scrape` returns `WatchEvent`s with real `watched_date`s. Nothing
     else needed.
   - **No** (like Hulu, Disney+ — only a "Continue Watching" rail, no
     dates): `_scrape` returns `WatchEvent`s with `watched_date=None`
     carrying the rail's titles. Add the platform name to
     `NO_DATE_PLATFORMS` in `main.py` so `snapshots.record_activity`
     derives an activity date from run-to-run changes in that set.
3. **Data source**: the JSON endpoint the site's own web app calls
   (`base.page_fetch_json(page, url)` — cookie-auth, cleanest when it
   works) or the rendered DOM (`page.query_selector*`). Check the network
   tab / DOM of a logged-in session to pick; note that some sites
   (Disney+) bearer-auth their API, which makes the DOM the sturdier
   choice.

## Steps

1. Create `scrapers/<platform>.py`:
   - `PLATFORM_NAME`, and the URL `run_scrape` should open (the history
     page for a dated platform, the home/app page for a Continue Watching
     one).
   - `LOGGED_IN_SELECTOR` — something present only when authenticated on
     that page, so a stale session triggers manual login.
   - `_scrape(page: Page) -> PlatformResult` — do the extraction; set
     `profile=` from the page if you can get the active profile name;
     `raise RuntimeError(...)` if the data source's *shape* is missing (so
     health.py sees a real failure) but return an empty `events=[]` for a
     genuinely empty list.
   - `fetch()` = one call to
     `base.run_scrape(PLATFORM_NAME, URL, LOGGED_IN_SELECTOR, _scrape)`.
   - Comment every selector / endpoint with the date you verified it
     against a live session; keep the framing honest.
2. Wire into `main.py`: import it, add its `fetch` to `SCRAPED_FETCHERS`
   (this also gets it health-tracked and fix-eligible), and add to
   `NO_DATE_PLATFORMS` if it has no watch dates.
3. Update `README.md`'s platform list and the relevant section.
4. Tell the user directly: the first run needs an interactive terminal so
   they can log in in the visible browser window; the selectors/endpoints
   are only as good as the one session you checked them against and may
   need a `fix-scraper` pass later.
