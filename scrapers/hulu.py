"""
Hulu watch-history scraper.

*** ALL SELECTORS BELOW ARE UNVERIFIED PLACEHOLDERS. ***
Hulu's DOM changes without notice and there's no way to verify these
against a live, authenticated session while writing this file. Run with
SCRAPERS_DEBUG=1, open devtools on the paused page, and update
HISTORY_URL / the selectors below to match what's actually on the page
before trusting this scraper's output.

Hulu's default history view is order-only (no per-item date), so
watched_date is always left None here — downstream reporting treats this
platform as having "unknown" recency rather than guessing dates from order.
"""
from models import PlatformResult, WatchEvent
from scrapers import base

PLATFORM_NAME = "Hulu"

# PLACEHOLDER — verify this is actually Hulu's watch-history URL.
HISTORY_URL = "https://www.hulu.com/account/watch-history"

# --- PLACEHOLDER SELECTORS (unverified) ------------------------------------
LOGGED_IN_SELECTOR = "[data-automationid='profile-menu']"
HISTORY_ITEM_SELECTOR = "[data-automationid='history-item']"
HISTORY_TITLE_SELECTOR = "[data-automationid='content-title']"
# ---------------------------------------------------------------------------


def fetch() -> PlatformResult:
    try:
        with base.persistent_browser() as context:
            page = base.get_page(context)
            page.goto(HISTORY_URL)
            base.debug_pause(page, label="Hulu history page load")

            if not base.is_logged_in(page, LOGGED_IN_SELECTOR):
                base.wait_for_manual_login(page, LOGGED_IN_SELECTOR)
                page.goto(HISTORY_URL)
                base.debug_pause(page, label="Hulu history page load (post-login)")

            events = []
            for item in page.query_selector_all(HISTORY_ITEM_SELECTOR):
                title_el = item.query_selector(HISTORY_TITLE_SELECTOR)
                title = title_el.inner_text().strip() if title_el else ""
                if not title:
                    continue
                events.append(
                    WatchEvent(title=title, watched_date=None, raw_source=item.inner_text())
                )

            return PlatformResult(platform=PLATFORM_NAME, events=events)
    except Exception as exc:
        return PlatformResult(platform=PLATFORM_NAME, error=f"Hulu scrape failed: {exc}")
