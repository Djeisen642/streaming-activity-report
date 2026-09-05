"""
Shared Playwright plumbing for the browser-scraped platforms (Hulu,
Disney+, Netflix, Prime Video). None of these are read here via an official
export; we drive a real, persistent, non-headless Chromium profile that the
user logs into manually once, and Playwright reuses that profile's
cookies/session on later runs, so no credentials are ever stored by this
tool. (netflix.py / amazon.py at the repo root remain as a CSV-import
alternative for Netflix and Prime Video; main.py chooses which path runs.)

Each scraper's `_scrape(page)` does its own extraction — some hit the JSON
endpoint the site's own web app calls (`page_fetch_json`), some read the
rendered DOM — and returns a PlatformResult. `run_scrape` owns the shared
lifecycle around that: launch, navigate, first-run manual login, and
failure-artifact capture.

Headless mode is intentionally not offered here — these sites actively
fingerprint and block headless Chromium, so a headless run is likely to
just get blocked rather than save time.
"""
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

import config
from models import PlatformResult


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
    if not sys.stdin.isatty():
        print(
            "[SCRAPERS_DEBUG] set but stdin is not a TTY (nothing to read an Enter "
            "from) — not pausing.",
            file=sys.stderr,
        )
        return
    print(f"[SCRAPERS_DEBUG] Paused on: {label or page.url}")
    print("Inspect the page/devtools in the opened browser window.")
    input("Press Enter here to continue...")


def is_logged_in(page: Page, logged_in_selector: str, timeout_ms: int = 15000) -> bool:
    """
    Login check: waits for a selector that should only render when
    authenticated. Each scraper points this at something that appears once
    its *content* is on screen (the activity table, a content rail), not
    just the nav — so a scrape that runs right after this passes can
    assume the data it wants has rendered. The timeout is generous because
    these are heavy SPAs on a cold profile; a logged-out page redirects to
    a login screen fast, so waiting doesn't slow that case much.
    """
    try:
        page.wait_for_selector(logged_in_selector, timeout=timeout_ms)
        return True
    except Exception:
        return False


# How long to wait for a human to complete the first-run manual login
# before giving up. Long enough for a real login (including 2FA), short
# enough that a stale-session run doesn't sit open for hours.
MANUAL_LOGIN_TIMEOUT_SECONDS = 300


def wait_for_manual_login(
    page: Page,
    logged_in_selector: str,
    poll_seconds: int = 5,
    timeout_seconds: int = MANUAL_LOGIN_TIMEOUT_SECONDS,
) -> None:
    """
    Blocks until `logged_in_selector` appears, for first-run manual login
    in the visible browser window. The persistent profile directory
    remembers the resulting session for subsequent runs.

    Raises rather than blocking forever in the two cases where no one can
    ever complete the login:

      - stdin isn't a TTY (e.g. the cron run the README describes): there's
        no interactive session to log in from, so fail fast.
      - the human didn't finish within `timeout_seconds`.

    Either way `run_scrape`'s handler catches it, saves failure artifacts,
    and returns an error PlatformResult like any other scrape failure.
    """
    if not sys.stdin.isatty():
        raise RuntimeError(
            "not logged in and no interactive terminal to log in from — the saved "
            "browser session is missing or expired; run once interactively to "
            "refresh it"
        )

    print("Log in manually in the opened browser window.")
    deadline = time.monotonic() + timeout_seconds
    while not is_logged_in(page, logged_in_selector, timeout_ms=poll_seconds * 1000):
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"manual login not completed within {timeout_seconds}s"
            )
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


def page_fetch_json(page: Page, url: str, timeout_ms: int = 20000) -> dict:
    """
    Run `fetch(url)` from inside the logged-in page and return the parsed
    JSON. Used by scrapers that read the same private endpoint the site's
    own web app calls (cookie-authenticated — the request inherits the
    page's session). Raises on a non-2xx status or a non-JSON body so
    run_scrape turns it into a normal scrape failure with artifacts.
    """
    result = page.evaluate(
        """async ({ url, timeoutMs }) => {
            const ctl = new AbortController();
            const t = setTimeout(() => ctl.abort(), timeoutMs);
            try {
                const r = await fetch(url, {
                    credentials: 'include',
                    headers: { 'Accept': 'application/json' },
                    signal: ctl.signal,
                });
                return { status: r.status, body: await r.text() };
            } finally {
                clearTimeout(t);
            }
        }""",
        {"url": url, "timeoutMs": timeout_ms},
    )
    if not (200 <= result["status"] < 300):
        raise RuntimeError(f"GET {url} -> HTTP {result['status']}")
    try:
        return json.loads(result["body"])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GET {url} -> non-JSON response ({exc})")


def run_scrape(
    platform: str,
    history_url: str,
    logged_in_selector: str,
    scrape_fn: Callable[[Page], PlatformResult],
) -> PlatformResult:
    """
    Shared lifecycle for the browser-scraped platforms: launch the
    persistent context, navigate to `history_url`, handle first-run manual
    login, then hand the page to `scrape_fn`, which pulls the data and
    returns its own PlatformResult (so a scraper can set `profile` or
    other fields, not just events) — including its own `platform` name;
    the `platform` arg here is only for the failure paths. Any failure
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

                return scrape_fn(page)
            except Exception as exc:
                save_failure_artifacts(page, platform, str(exc))
                return PlatformResult(platform=platform, error=f"{platform} scrape failed: {exc}")
    except Exception as exc:
        # Context/browser launch itself failed — no page was ever opened.
        save_failure_artifacts(None, platform, str(exc))
        return PlatformResult(platform=platform, error=f"{platform} scrape failed: {exc}")
