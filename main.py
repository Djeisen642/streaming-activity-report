"""
Entry point: runs all five platform fetchers and writes report.html.

Netflix and Prime Video read from local CSV exports (see README for how to
get them). Hulu, Disney+, and Paramount+ are scraped via a persistent local
browser session — first run opens a visible browser for manual login;
later runs reuse that session from the profile directory.
"""
import sys

import amazon
import config
import netflix
import report
from scrapers import disneyplus, hulu, paramountplus


def main() -> int:
    results = [
        netflix.fetch(),
        amazon.fetch(),
        hulu.fetch(),
        disneyplus.fetch(),
        paramountplus.fetch(),
    ]

    for result in results:
        if result.error:
            print(f"[{result.platform}] error: {result.error}", file=sys.stderr)
        else:
            print(f"[{result.platform}] {len(result.events)} titles found")

    config.REPORT_OUTPUT_PATH.write_text(report.build_report(results), encoding="utf-8")
    print(f"Report written to {config.REPORT_OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
