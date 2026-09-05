"""
Hulu "Continue Watching" scraper.

Hulu publishes no dated watch history anywhere a browser can reach it —
not in the page DOM, not in the JSON its web app fetches (both checked
directly, 2026-09-05). The one usable signal is the ordered "Continue
Watching" rail on the home hub. This scraper pulls the titles in that
rail; snapshots.py turns "this set changed between runs" into an activity
date. So every WatchEvent here has watched_date=None by design.

Data source: the same endpoint hulu.com's web app calls for the home hub,
fetched from the logged-in page so it inherits the session cookies:

    GET https://discover.hulu.com/content/v5/view_hubs/home?schema=3

The response has a `components` list; the one named "Continue Watching"
carries the rail items, each with `metrics_info.target_name` (the series
or movie name). Verified against the live response 2026-09-05 — the shape
can drift; a failure here is most likely that, not a login problem.
"""
from typing import List

from playwright.sync_api import Page

from models import PlatformResult, WatchEvent
from scrapers import base

PLATFORM_NAME = "Hulu"

# Authenticated home hub. Logged-out, this redirects to a marketing page
# and the selector below won't be found, which triggers manual login.
HOME_URL = "https://www.hulu.com/hub/home"
LOGGED_IN_SELECTOR = "[aria-label='Account Menu'], a[href='/account']"

HUB_ENDPOINT = "https://discover.hulu.com/content/v5/view_hubs/home?schema=3&limit=32"
COLLECTION_ENDPOINT = "https://discover.hulu.com/content/v5/view_hubs/home/collections/{id}?schema=3&limit=32"
CONTINUE_WATCHING_NAME = "Continue Watching"


def _titles_from_items(items: List[dict]) -> List[str]:
    titles = []
    for item in items:
        name = (item.get("metrics_info") or {}).get("target_name")
        if not name:
            visuals = item.get("visuals") or {}
            name = visuals.get("title") or item.get("name")
        if name and name.strip():
            titles.append(name.strip())
    return titles


def _scrape(page: Page) -> PlatformResult:
    hub = base.page_fetch_json(page, HUB_ENDPOINT)
    components = hub.get("components") or []
    rail = next(
        (c for c in components if (c.get("name") or "").strip().lower() == CONTINUE_WATCHING_NAME.lower()),
        None,
    )
    if rail is None:
        # No rail at all is a real state (nothing in progress on this
        # profile) only if the hub itself looks sane; otherwise the shape
        # changed. Distinguish so a break doesn't read as "you stopped
        # using Hulu".
        if not components:
            raise RuntimeError("home hub returned no components — endpoint shape likely changed")
        return PlatformResult(platform=PLATFORM_NAME, events=[])

    items = rail.get("items") or []
    if not items and rail.get("id"):
        rail = base.page_fetch_json(page, COLLECTION_ENDPOINT.format(id=rail["id"]))
        items = rail.get("items") or []

    titles = _titles_from_items(items)
    events = [WatchEvent(title=t, watched_date=None, raw_source="hulu:continue-watching") for t in titles]
    return PlatformResult(platform=PLATFORM_NAME, events=events)


def fetch() -> PlatformResult:
    return base.run_scrape(PLATFORM_NAME, HOME_URL, LOGGED_IN_SELECTOR, _scrape)
