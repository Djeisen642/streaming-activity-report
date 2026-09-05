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
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

import config
from models import PlatformResult, WatchEvent


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
        # Best-effort cleanup: an exception raised here (e.g. the browser
        # process already died) would otherwise propagate out of the
        # `with` block and silently replace/discard whatever the caller
        # was already returning from inside it — including a correctly
        # captured scrape failure and its saved debug artifacts.
        if self._context is not None:
            try:
                self._context.close()
            except Exception as exc:
                print(f"[persistent_browser] context.close() failed: {exc}", file=sys.stderr)
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception as exc:
                print(f"[persistent_browser] playwright.stop() failed: {exc}", file=sys.stderr)


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


def save_failure_artifacts(page: Optional[Page], platform: str, error: str) -> Optional[Path]:
    """
    On scrape failure, dumps the page's HTML and a full-page screenshot to
    debug_artifacts/<platform>/<timestamp>/, so a break can be diagnosed
    (by you, or by the fix-scraper skill) from that snapshot instead of
    requiring a live reproduction.

    Must be called with `page` still attached to an open context/browser —
    callers close the context before this returns, so a Playwright call
    made afterward would just fail. Best-effort beyond that: a page that
    never loaded won't have content to dump, and a filesystem problem
    writing the artifacts is logged rather than allowed to crash the run
    that's already in an error path.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    slug = platform.lower().replace("+", "plus").replace(" ", "_")
    out_dir = config.DEBUG_ARTIFACTS_DIR / slug / timestamp

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "error.txt").write_text(error, encoding="utf-8")
    except OSError as exc:
        print(f"[{platform}] could not write failure artifacts to {out_dir}: {exc}", file=sys.stderr)
        return None

    if page is not None:
        try:
            (out_dir / "page.html").write_text(page.content(), encoding="utf-8")
        except Exception:
            pass
        try:
            page.screenshot(path=str(out_dir / "screenshot.png"), full_page=True)
        except Exception:
            pass

    return out_dir


def parse_date_with_formats(raw: str, formats: List[str]) -> Optional[date]:
    """Tries each strptime format in order, returning the first that parses."""
    raw = (raw or "").strip()
    for fmt in formats:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def scrape_dated_items(
    page: Page,
    item_selector: str,
    title_selector: str,
    date_selector: str,
    parse_date: Callable[[str], Optional[date]],
) -> List[WatchEvent]:
    """
    Shared item/title/date extraction for scrapers whose history items may
    carry a per-item date (Disney+, Paramount+). Hulu's history has no
    per-item date at all, so it builds its WatchEvents directly instead of
    using this helper.
    """
    events = []
    for item in page.query_selector_all(item_selector):
        title_el = item.query_selector(title_selector)
        title = title_el.inner_text().strip() if title_el else ""
        if not title:
            continue
        date_el = item.query_selector(date_selector)
        raw_date = date_el.inner_text() if date_el else ""
        events.append(
            WatchEvent(
                title=title,
                watched_date=parse_date(raw_date) if raw_date else None,
                raw_source=item.inner_text(),
            )
        )
    return events


def run_scrape(
    platform: str,
    history_url: str,
    logged_in_selector: str,
    scrape_fn: Callable[[Page], List[WatchEvent]],
) -> PlatformResult:
    """
    Shared lifecycle for the browser-scraped platforms: launch the
    persistent context, navigate to `history_url`, handle first-run manual
    login, then hand the page to `scrape_fn` to pull events. Any failure
    (navigation, login, or inside scrape_fn) is caught and saved via
    save_failure_artifacts *before* the context closes — artifacts need a
    still-open page to capture anything — so every scraper gets the same
    failure-capture behavior for free.
    """
    try:
        with persistent_browser() as context:
            page = get_page(context)
            try:
                page.goto(history_url)
                debug_pause(page, label=f"{platform} history page load")

                if not is_logged_in(page, logged_in_selector):
                    wait_for_manual_login(page, logged_in_selector)
                    page.goto(history_url)
                    debug_pause(page, label=f"{platform} history page load (post-login)")

                events = scrape_fn(page)
                return PlatformResult(platform=platform, events=events)
            except Exception as exc:
                save_failure_artifacts(page, platform, str(exc))
                return PlatformResult(platform=platform, error=f"{platform} scrape failed: {exc}")
    except Exception as exc:
        # Context/browser launch itself failed — no page was ever opened.
        save_failure_artifacts(None, platform, str(exc))
        return PlatformResult(platform=platform, error=f"{platform} scrape failed: {exc}")
