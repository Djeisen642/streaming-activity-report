"""
Parses the Amazon Prime Video watch-history CSV export.

Amazon has no dedicated one-click Prime Video export. Request it via
amazon.com/gp/privacycentral/dsar/preview.html > Request My Data, choosing
the "Prime Video" (or similarly named "Digital Orders/Subscriptions" —
Amazon has renamed these categories over time) data group. The response
arrives by email as a zip of CSVs; find the one containing watch history
and drop it in data/.

IMPORTANT: Amazon's column names and file layout are NOT stable across
export requests. TITLE_COLUMN and DATE_COLUMN below are best-guess
defaults, not verified against a real export. Open your actual CSV's
header row and update these constants to match before relying on this.
"""
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

import config
from models import PlatformResult, WatchEvent

PLATFORM_NAME = "Prime Video"

# Update these two to match your actual export's header row.
TITLE_COLUMN = "Title"
DATE_COLUMN = "Viewing Start Time"

# Amazon exports have used ISO 8601 timestamps and plainer date formats.
# Add more here if parsing fails on your export.
DATE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%m/%d/%Y",
]


def _parse_date(raw: str) -> Optional[datetime]:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def fetch(csv_path: Optional[Path] = None) -> PlatformResult:
    csv_path = csv_path or config.AMAZON_CSV_PATH

    if not csv_path.exists():
        return PlatformResult(
            platform=PLATFORM_NAME,
            error=(
                f"No export found at {csv_path}. Request it from Amazon "
                "(Privacy Central > Request My Data > Prime Video) and place it there."
            ),
        )

    events = []
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or TITLE_COLUMN not in reader.fieldnames:
                return PlatformResult(
                    platform=PLATFORM_NAME,
                    error=(
                        f"Expected column '{TITLE_COLUMN}' not found in {csv_path}. "
                        f"Found columns: {reader.fieldnames}. Amazon's export column "
                        "names vary by request; update TITLE_COLUMN/DATE_COLUMN in "
                        "amazon.py to match your file's header row."
                    ),
                )
            for row in reader:
                title = (row.get(TITLE_COLUMN) or "").strip()
                if not title:
                    continue
                raw_date = (row.get(DATE_COLUMN) or "").strip()
                events.append(
                    WatchEvent(
                        title=title,
                        watched_date=_parse_date(raw_date) if raw_date else None,
                        raw_source=",".join(f"{k}={v}" for k, v in row.items()),
                    )
                )
    except Exception as exc:
        return PlatformResult(platform=PLATFORM_NAME, error=f"Failed to read {csv_path}: {exc}")

    return PlatformResult(platform=PLATFORM_NAME, events=events)
