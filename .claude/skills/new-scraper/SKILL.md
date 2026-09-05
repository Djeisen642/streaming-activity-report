---
name: new-scraper
description: Scaffold a new browser-scraped streaming platform module (matching Hulu/Disney+/Paramount+'s pattern) for the streaming usage audit tool. Use when the user wants to add a new platform to the audit that has no official CSV/data export, so it needs Playwright scraping via the shared scrapers/base.py lifecycle.
---

# Add a new scraped platform

The browser-scraped platforms all share one lifecycle via
`scrapers/base.run_scrape()`: launch persistent context → navigate →
manual login on first run → call a platform-specific
`_scrape(page) -> list[WatchEvent]` → on any failure, `run_scrape`
automatically saves HTML + screenshot artifacts and reports the error.

Before scaffolding, confirm with the user:

- **Does this platform actually lack an export tool?** If it has one
  (even a slow/manual one), it belongs as a CSV importer like
  `netflix.py`/`amazon.py`, not a scraper. Don't default to scraping just
  because it's the more generically applicable path — check first.
- The platform's watch-history page URL. A best guess is fine; it goes in
  as an explicitly-marked placeholder either way.

## Steps

1. Create `scrapers/<platform>.py` modeled on `scrapers/hulu.py`:
   - `PLATFORM_NAME`, `HISTORY_URL` (comment: unverified, needs checking
     against the live site)
   - `LOGGED_IN_SELECTOR`, `HISTORY_ITEM_SELECTOR`, `HISTORY_TITLE_SELECTOR`,
     and `HISTORY_DATE_SELECTOR` if the platform is expected to expose
     per-item dates — all as unverified placeholders. Don't present any of
     them as "probably right"; a plausible-looking guess is still a guess.
   - `_scrape(page: Page) -> List[WatchEvent]`
   - `fetch()` that only calls
     `base.run_scrape(PLATFORM_NAME, HISTORY_URL, LOGGED_IN_SELECTOR, _scrape)`
2. Wire it into `main.py`: import the module and add its `fetch` to the
   `SCRAPED_FETCHERS` list (this also gets it health-tracked and eligible
   for the automated fix-scraper trigger for free).
3. Update `README.md`'s platform list and the scraping section to mention
   it, including whatever's true about its per-item date availability.
4. Tell the user directly (don't let this pass silently): first run needs
   `SCRAPERS_DEBUG=1` so they can pause after page load, open devtools,
   and correct every selector against the live DOM before trusting any
   output — this scaffold produces placeholders, not working selectors.
