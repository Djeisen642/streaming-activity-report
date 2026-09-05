"""
Entry point: runs every platform fetcher and writes report.html.

All four platforms are read live from a persistent, logged-in browser
session (first run opens a visible browser for manual login; later runs
reuse that session):

  - Netflix, Prime Video  — real dated history pages, scraped for the
    active profile. (netflix.py / amazon.py at the repo root are the
    CSV-import alternative — swap them in here if you'd rather feed an
    official export than run a browser.)
  - Hulu, Disney+         — publish no watch dates anywhere, so these read
    the "Continue Watching" rail instead; snapshots.py turns run-to-run
    changes in that list into an activity date.

All four feed health.py's failure tracking and are eligible for the
automated fix-scraper trigger below.
"""
import subprocess
import sys

import config
import health
import report
import snapshots
from scrapers import disneyplus, hulu, netflix, primevideo

SCRAPED_FETCHERS = [netflix.fetch, primevideo.fetch, hulu.fetch, disneyplus.fetch]

# Platforms with no per-item watch date: their PlatformResult carries
# "Continue Watching" titles, and snapshots.py derives an activity date
# from how that set changes between runs. Derived from the modules so a
# PLATFORM_NAME rename can't half-apply (the name is also the health.py
# and snapshots.py state-file key).
NO_DATE_PLATFORMS = {hulu.PLATFORM_NAME, disneyplus.PLATFORM_NAME}

# How long to let a triggered fix run go before giving up on it. This runs
# from cron with nobody watching, so it must not hang indefinitely.
FIX_RUN_TIMEOUT_SECONDS = 900


def trigger_fix_run(platform: str) -> None:
    """
    Shells out to the local Claude Code CLI to diagnose and patch a
    scraper that has failed FAILURE_THRESHOLD consecutive runs, using the
    fix-scraper skill and the failure artifacts saved under
    debug_artifacts/. Requires `claude` on PATH; opens a PR, never merges.
    """
    prompt = (
        f"Use the fix-scraper skill to diagnose and fix the {platform} scraper "
        f"in this repo. It has failed {health.FAILURE_THRESHOLD} consecutive runs. "
        "Debug artifacts (HTML snapshot + screenshot) are under debug_artifacts/. "
        "Open a PR with the fix; do not merge it."
    )
    print(
        f"[{platform}] flagged as broken after {health.FAILURE_THRESHOLD} consecutive "
        "failures; triggering local Claude Code fix run..."
    )
    try:
        subprocess.run(
            ["claude", "-p", prompt, "--permission-mode", "acceptEdits"],
            cwd=str(config.BASE_DIR),
            timeout=FIX_RUN_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        print(
            "claude CLI not found on PATH — install it, or run the fix-scraper "
            "skill manually to address this.",
            file=sys.stderr,
        )
    except subprocess.TimeoutExpired:
        print(f"[{platform}] fix run did not finish within {FIX_RUN_TIMEOUT_SECONDS}s; "
              "check on it manually.", file=sys.stderr)


def main() -> int:
    results = [fetch() for fetch in SCRAPED_FETCHERS]

    # For the no-date platforms, fold in the activity date derived from
    # the Continue Watching snapshot. Skip a result that errored — a
    # broken scrape returning nothing must not be snapshotted as "the
    # list changed".
    for result in results:
        if result.platform in NO_DATE_PLATFORMS and not result.error:
            result.last_activity_date = snapshots.record_activity(
                result.platform, [e.title for e in result.events]
            )

    for result in results:
        if result.error:
            print(f"[{result.platform}] error: {result.error}", file=sys.stderr)
        else:
            print(f"[{result.platform}] {len(result.events)} titles found")

    # Write the report before any fix-run trigger: all data needed for it
    # is already computed, and a triggered `claude -p` call can take up to
    # FIX_RUN_TIMEOUT_SECONDS — the report shouldn't wait behind that.
    config.REPORT_OUTPUT_PATH.write_text(report.build_report(results), encoding="utf-8")
    print(f"Report written to {config.REPORT_OUTPUT_PATH}")

    for platform in health.record_and_check(results):
        trigger_fix_run(platform)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
