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
from datetime import datetime
from typing import Optional

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


def _parse_date(raw: str) -> Optional[datetime]:
    raw = (raw or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def fetch() -> PlatformResult:
    try:
        with base.persistent_browser() as context:
            page = base.get_page(context)
            page.goto(HISTORY_URL)
            base.debug_pause(page, label="Disney+ history page load")

            if not base.is_logged_in(page, LOGGED_IN_SELECTOR):
                base.wait_for_manual_login(page, LOGGED_IN_SELECTOR)
                page.goto(HISTORY_URL)
                base.debug_pause(page, label="Disney+ history page load (post-login)")

            events = []
            for item in page.query_selector_all(HISTORY_ITEM_SELECTOR):
                title_el = item.query_selector(HISTORY_TITLE_SELECTOR)
                title = title_el.inner_text().strip() if title_el else ""
                if not title:
                    continue
                date_el = item.query_selector(HISTORY_DATE_SELECTOR)
                raw_date = date_el.inner_text() if date_el else ""
                events.append(
                    WatchEvent(
                        title=title,
                        watched_date=_parse_date(raw_date) if raw_date else None,
                        raw_source=item.inner_text(),
                    )
                )

            return PlatformResult(platform=PLATFORM_NAME, events=events)
    except Exception as exc:
        return PlatformResult(platform=PLATFORM_NAME, error=f"Disney+ scrape failed: {exc}")
