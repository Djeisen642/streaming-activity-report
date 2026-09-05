"""
Shared Playwright plumbing for the browser-scraped platforms (Hulu,
Disney+, Paramount+). None of these expose an export tool, so we drive a
real, persistent, non-headless Chromium profile that the user logs into
manually once; Playwright reuses that profile's cookies/session on later
runs, so no credentials are ever stored by this tool.

Headless mode is intentionally not offered here — these sites actively
fingerprint and block headless Chromium, so a headless run is likely to
just get blocked rather than save time.
"""
import time
from pathlib import Path
from typing import Optional, Tuple

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

import config


def launch_persistent_context(
    profile_dir: Optional[Path] = None,
) -> Tuple[Playwright, BrowserContext]:
    """
    Launches (or reuses) a persistent Chromium profile directory.

    Caller owns the returned objects' lifecycle (context.close() then
    pw.stop()) — prefer the `persistent_browser` context manager below
    unless you need them held open across multiple calls.
    """
    profile_dir = profile_dir or config.BROWSER_PROFILE_DIR
    profile_dir.mkdir(parents=True, exist_ok=True)

    pw = sync_playwright().start()
    context = pw.chromium.launch_persistent_context(
        user_data_dir=str(profile_dir),
        headless=False,
        viewport={"width": 1280, "height": 900},
    )
    return pw, context


class persistent_browser:
    """`with persistent_browser() as context:` wrapper around launch_persistent_context."""

    def __init__(self, profile_dir: Optional[Path] = None):
        self.profile_dir = profile_dir
        self._pw: Optional[Playwright] = None
        self._context: Optional[BrowserContext] = None

    def __enter__(self) -> BrowserContext:
        self._pw, self._context = launch_persistent_context(self.profile_dir)
        return self._context

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._context is not None:
            self._context.close()
        if self._pw is not None:
            self._pw.stop()


def get_page(context: BrowserContext) -> Page:
    """Returns the persistent context's already-open page, or opens a new one."""
    if context.pages:
        return context.pages[0]
    return context.new_page()


def debug_pause(page: Page, label: str = "") -> None:
    """
    When SCRAPERS_DEBUG=1, pause after a page load so selectors can be
    checked/adjusted against the live DOM via devtools before the scraping
    logic (which uses unverified placeholder selectors) runs against it.
    """
    if not config.SCRAPERS_DEBUG:
        return
    print(f"[SCRAPERS_DEBUG] Paused on: {label or page.url}")
    print("Inspect the page/devtools in the opened browser window.")
    input("Press Enter here to continue...")


def is_logged_in(page: Page, logged_in_selector: str, timeout_ms: int = 5000) -> bool:
    """
    Best-effort login check: waits briefly for a selector that should only
    render when authenticated (e.g. an account/profile menu element).

    PLACEHOLDER CAVEAT: `logged_in_selector` is supplied by each scraper
    module and has NOT been verified against a live, authenticated page.
    """
    try:
        page.wait_for_selector(logged_in_selector, timeout=timeout_ms)
        return True
    except Exception:
        return False


def wait_for_manual_login(page: Page, logged_in_selector: str, poll_seconds: int = 5) -> None:
    """
    Blocks until `logged_in_selector` appears, for first-run manual login
    in the visible browser window. The persistent profile directory
    remembers the resulting session for subsequent runs.
    """
    print("Log in manually in the opened browser window.")
    while not is_logged_in(page, logged_in_selector, timeout_ms=poll_seconds * 1000):
        print("Still waiting for login...")
        time.sleep(1)
    print("Login detected, continuing.")
