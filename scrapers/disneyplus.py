"""
Disney+ "Continue Watching" scraper.

Like Hulu, Disney+ exposes no dated watch history to a browser — its
explore API returns progress percentages, never a timestamp (checked
directly, 2026-09-05). The usable signal is the ordered "Continue
Watching" rail on the home page; snapshots.py turns run-to-run changes in
that set into an activity date. Every WatchEvent here has
watched_date=None by design.

This one reads the rendered DOM rather than the JSON endpoint: the explore
API needs a bearer token dug out of a versioned localStorage key, which is
more fragile than a CSS selector. The Continue Watching rail is the
`[data-testid="set"]` container holding the `cw-set-item-metadata` links;
its tiles are `a[data-testid="set-item"]` whose aria-label reads like
"<Title> Season 1 Episode 3 ... 28 minutes remaining". We keep just the
show title. Verified against the live DOM 2026-09-05.
"""
import re
from typing import List

from playwright.sync_api import Page

from models import PlatformResult, WatchEvent
from scrapers import base

PLATFORM_NAME = "Disney+"

# Authenticated home. Logged-out this redirects to /identity/login where
# no content rail renders, triggering manual login. `set-item` only exists
# once the rows have rendered, so passing this check means the DOM is ready.
HOME_URL = "https://www.disneyplus.com/home"
LOGGED_IN_SELECTOR = "[data-testid='set-item']"

# The rail: the set container that holds the continue-watching metadata
# links. Its tiles carry the title in an aria-label.
CW_RAIL_SELECTOR = "a[data-testid='cw-set-item-metadata']"
CW_SET_CONTAINER = "[data-testid='set']"
CW_TILE_SELECTOR = "a[data-testid='set-item'][aria-label]"

# Strip the episode / time-remaining tail off a tile's aria-label to get
# the bare show title.
_TAIL = re.compile(
    r"\s+(?:Season\s+\d+\b.*|Watch Next Episode|"
    r"\d+\s+hours?(?:\s+\d+\s+minutes?)?\s+remaining|"
    r"\d+\s+minutes?\s+remaining)\s*$",
    re.IGNORECASE,
)


def _show_title(aria_label: str) -> str:
    label = (aria_label or "").strip()
    prev = None
    while label and label != prev:  # a couple of the patterns can stack
        prev = label
        label = _TAIL.sub("", label).strip()
    return label


def _scrape(page: Page) -> PlatformResult:
    try:
        # Continue Watching is one of the later personalized rails to
        # render — give it real time, especially when this is the last of
        # several scrapers on a warmed-up but busy machine.
        page.wait_for_selector(CW_RAIL_SELECTOR, timeout=25000)
    except Exception:
        # Rail never appeared. If other rails did render, this profile
        # just has nothing in progress; if nothing rendered at all, the
        # markup moved.
        if page.query_selector(CW_SET_CONTAINER) is None:
            raise RuntimeError("no content rails on the home page — markup changed or not loaded")
        return PlatformResult(platform=PLATFORM_NAME, events=[])

    rail = page.query_selector(f"{CW_SET_CONTAINER}:has({CW_RAIL_SELECTOR})")
    tiles = rail.query_selector_all(CW_TILE_SELECTOR) if rail else []
    titles: List[str] = []
    for tile in tiles:
        title = _show_title(tile.get_attribute("aria-label"))
        if title:
            titles.append(title)

    events = [
        WatchEvent(title=t, watched_date=None, raw_source="disneyplus:continue-watching")
        for t in titles
    ]
    return PlatformResult(platform=PLATFORM_NAME, events=events)


def fetch() -> PlatformResult:
    return base.run_scrape(PLATFORM_NAME, HOME_URL, LOGGED_IN_SELECTOR, _scrape)
