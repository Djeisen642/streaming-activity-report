"""
Prime Video watch-history scraper (live, via the logged-in web session).

Amazon renders a dated watch history at
amazon.com/gp/video/settings/watch-history — items grouped under
"Month D, YYYY" headers, one list per profile (Amazon's wording), for
whichever profile is active in the persistent browser session.

The repo-root amazon.py (CSV importer) is the alternative path: it parses
the Prime Video data-request export. main.py picks one or the other.

DOM shape (verified 2026-09-05): a `[data-testid="activity-history-items"]`
container holding, in document order, `h3[data-testid="wh-date-<Month D,
YYYY>"]` headers followed by `[data-testid="activity-history-item"]`
blocks; each item's title is its poster `img[alt]`.
"""
from datetime import date
from typing import Optional

from playwright.sync_api import Page

from models import PlatformResult, WatchEvent
from scrapers import base

PLATFORM_NAME = "Prime Video"

HISTORY_URL = "https://www.amazon.com/gp/video/settings/watch-history"
# Present once the authed history list renders. Logged out, Amazon
# redirects to /ap/signin and this is absent -> manual login.
LOGGED_IN_SELECTOR = "[data-testid='activity-history-items'], [data-testid='activity-history-item']"

_DATE_FORMATS = ["%B %d, %Y", "%b %d, %Y"]


def _parse_date(raw: str) -> Optional[date]:
    return base.parse_date_with_formats(raw, _DATE_FORMATS)


def _scrape(page: Page) -> PlatformResult:
    data = page.evaluate(
        """() => {
            const container = document.querySelector('[data-testid="activity-history-items"]');
            const out = [];
            if (container) {
                let curDate = null;
                const nodes = container.querySelectorAll(
                    '[data-testid^="wh-date-"], [data-testid="activity-history-item"]'
                );
                for (const el of nodes) {
                    const tid = el.getAttribute('data-testid');
                    if (tid.startsWith('wh-date-')) {
                        curDate = (el.textContent || tid.slice('wh-date-'.length)).trim();
                    } else {
                        const title =
                            el.querySelector('img[alt]')?.getAttribute('alt')?.trim() ||
                            [...el.querySelectorAll('a')].map(a => a.textContent.trim()).find(Boolean) ||
                            '';
                        if (title) out.push({ date: curDate, title });
                    }
                }
            }
            const profile = document.querySelector('[data-testid="pv-nav-profile-name"]')
                ?.textContent?.trim() || null;
            return { rows: out, profile };
        }"""
    )
    events = [
        WatchEvent(
            title=row["title"],
            watched_date=_parse_date(row["date"]) if row["date"] else None,
            raw_source="primevideo:watch-history",
        )
        for row in data["rows"]
        if row["title"]
    ]
    return PlatformResult(platform=PLATFORM_NAME, events=events, profile=data["profile"])


def fetch() -> PlatformResult:
    return base.run_scrape(PLATFORM_NAME, HISTORY_URL, LOGGED_IN_SELECTOR, _scrape)
