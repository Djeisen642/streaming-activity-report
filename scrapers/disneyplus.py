"""
Disney+ watch-history scraper.

*** ALL SELECTORS AND URLS BELOW ARE UNVERIFIED PLACEHOLDERS. ***
Disney+'s DOM changes without notice and there's no way to verify these
against a live, authenticated session while writing this file. Run with
SCRAPERS_DEBUG=1, open devtools on the paused page, and update
HISTORY_URL / the selectors below to match what's actually on the page
before trusting this scraper's output. In particular, confirm whether
Disney+ even has a dedicated "history" page as opposed to only
"Continue Watching" — the URL below is a guess.

If a per-item date isn't actually present on the page, HISTORY_DATE_SELECTOR
just won't match and watched_date falls back to None for that item — that's
expected and downstream reporting handles it, no need to make this scraper
error out over it.
"""
from datetime import date
from typing import List, Optional

from playwright.sync_api import Page

from models import PlatformResult, WatchEvent
from scrapers import base

PLATFORM_NAME = "Disney+"

# PLACEHOLDER — verify this is actually Disney+'s watch-history URL.
HISTORY_URL = "https://www.disneyplus.com/account/watch-history"

# --- PLACEHOLDER SELECTORS (unverified) ------------------------------------
LOGGED_IN_SELECTOR = "[data-testid='avatar-button']"
HISTORY_ITEM_SELECTOR = "[data-testid='history-item']"
HISTORY_TITLE_SELECTOR = "[data-testid='item-title']"
HISTORY_DATE_SELECTOR = "[data-testid='item-date']"  # may not exist on the real page
# ---------------------------------------------------------------------------

DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"]


def _parse_date(raw: str) -> Optional[date]:
    return base.parse_date_with_formats(raw, DATE_FORMATS)


def _scrape(page: Page) -> List[WatchEvent]:
    return base.scrape_dated_items(
        page, HISTORY_ITEM_SELECTOR, HISTORY_TITLE_SELECTOR, HISTORY_DATE_SELECTOR, _parse_date
    )


def fetch() -> PlatformResult:
    return base.run_scrape(PLATFORM_NAME, HISTORY_URL, LOGGED_IN_SELECTOR, _scrape)
