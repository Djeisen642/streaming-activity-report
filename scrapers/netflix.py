"""
Netflix viewing-activity scraper (live, via the logged-in web session).

Unlike Hulu/Disney+, Netflix *does* publish a dated per-title history —
the "Viewing activity" page at netflix.com/viewingactivity. This scraper
reads the rows Netflix renders there (title + date), for whichever profile
is currently active in the persistent browser session.

The repo-root netflix.py (CSV importer) is the alternative path: it reads
the official "Download all" export, which is the complete history rather
than just the ~20 most-recent rows this page renders before you page for
more. main.py picks one path or the other; for a "days since last
watched" question the newest row is all that matters, so the scraper is
enough.

Date format caveat: Netflix localizes the date column (US "9/3/26" is
month-first; many other locales are day-first). We read the page's
language and choose the ordering; parsing falls back to the other
ordering if the first fails. Verified against the live page 2026-09-05.
"""
from typing import List

from playwright.sync_api import Page

from models import PlatformResult, WatchEvent
from scrapers import base

PLATFORM_NAME = "Netflix"

HISTORY_URL = "https://www.netflix.com/viewingactivity"
# The activity table (or its empty-state) renders once the page loads
# authenticated; logged out, Netflix redirects to /login and none of these
# appear -> manual login. Passing this check means the rows are on screen.
LOGGED_IN_SELECTOR = ".retable, .retableNoActivity, [data-uia='activity-row']"

_MONTH_FIRST = ["%m/%d/%y", "%m/%d/%Y", "%d/%m/%y", "%d/%m/%Y"]
_DAY_FIRST = ["%d/%m/%y", "%d/%m/%Y", "%m/%d/%y", "%m/%d/%Y"]


def _date_formats(lang: str) -> List[str]:
    lang = (lang or "").lower()
    return _MONTH_FIRST if lang == "en" or lang.startswith("en-us") else _DAY_FIRST


def _scrape(page: Page) -> PlatformResult:
    data = page.evaluate(
        """() => {
            const rows = [...document.querySelectorAll('[data-uia="activity-row"]')].map(r => ({
                date: (r.querySelector('.col.date')?.textContent || '').trim(),
                title: (r.querySelector('.col.title a') || r.querySelector('.col.title'))
                    ?.textContent?.trim() || '',
            }));
            let profile = null;
            try { profile = netflix.reactContext.models.userInfo.data.name; } catch (e) {}
            return { rows, profile, lang: document.documentElement.lang || 'en' };
        }"""
    )
    formats = _date_formats(data["lang"])
    events = [
        WatchEvent(
            title=row["title"],
            watched_date=base.parse_date_with_formats(row["date"], formats),
            raw_source="netflix:viewingactivity",
        )
        for row in data["rows"]
        if row["title"]
    ]
    return PlatformResult(platform=PLATFORM_NAME, events=events, profile=data["profile"])


def fetch() -> PlatformResult:
    return base.run_scrape(PLATFORM_NAME, HISTORY_URL, LOGGED_IN_SELECTOR, _scrape)
