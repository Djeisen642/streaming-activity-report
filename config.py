"""Central configuration: paths and settings, overridable via env vars."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# Playwright persistent browser profile directory. Deliberately separate
# from the user's daily Chrome profile so scraper logins/cookies don't mix
# with regular browsing.
BROWSER_PROFILE_DIR = Path(
    os.environ.get("SCRAPERS_PROFILE_DIR", str(BASE_DIR / ".browser_profile"))
)

# CSV import paths for the platforms with official data-export tools.
NETFLIX_CSV_PATH = Path(
    os.environ.get("NETFLIX_CSV_PATH", str(DATA_DIR / "netflix_viewing_history.csv"))
)
AMAZON_CSV_PATH = Path(
    os.environ.get("AMAZON_CSV_PATH", str(DATA_DIR / "amazon_prime_video_history.csv"))
)

REPORT_OUTPUT_PATH = Path(
    os.environ.get("REPORT_OUTPUT_PATH", str(BASE_DIR / "report.html"))
)

# Where a scraper dumps HTML + screenshot on failure, and where
# health.py persists per-platform consecutive-failure counts. Both contain
# your actual viewing history/account UI — never commit these.
DEBUG_ARTIFACTS_DIR = Path(
    os.environ.get("DEBUG_ARTIFACTS_DIR", str(BASE_DIR / "debug_artifacts"))
)
SCRAPER_HEALTH_PATH = Path(
    os.environ.get("SCRAPER_HEALTH_PATH", str(BASE_DIR / ".scraper_health.json"))
)

# A platform idle longer than this is visually flagged in the report.
IDLE_THRESHOLD_DAYS = 30

# SCRAPERS_DEBUG=1 pauses each scraper after page load so selectors can be
# checked/adjusted against the live DOM via devtools before scraping runs.
SCRAPERS_DEBUG = os.environ.get("SCRAPERS_DEBUG") == "1"
