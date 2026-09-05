"""
Entry point: runs all five platform fetchers and writes report.html.

Netflix and Prime Video read from local CSV exports (see README for how to
get them). Hulu, Disney+, and Paramount+ are scraped via a persistent local
browser session — first run opens a visible browser for manual login;
later runs reuse that session from the profile directory.

Only the three scraped platforms feed health.py's failure tracking: a
broken CSV import needs a fresh export from the user, not a code fix, so
it's not a candidate for the automated fix-scraper trigger below.
"""
import subprocess
import sys

import amazon
import config
import health
import netflix
import report
from scrapers import disneyplus, hulu, paramountplus

SCRAPED_FETCHERS = [hulu.fetch, disneyplus.fetch, paramountplus.fetch]

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
    csv_results = [netflix.fetch(), amazon.fetch()]
    scraped_results = [fetch() for fetch in SCRAPED_FETCHERS]
    results = csv_results + scraped_results

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

    for platform in health.record_and_check(scraped_results):
        trigger_fix_run(platform)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
