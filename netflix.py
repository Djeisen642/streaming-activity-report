"""
Parses the Netflix "Viewing activity" CSV export.

Get this file from Netflix: Account > Profile & Parental Controls >
Viewing activity > Download all. (Or the full personal-data export at
netflix.com/account/getmyinfo, which includes the same viewing history
under a differently-named file — look for the one with Title/Date columns.)

Netflix's export has stable Title/Date columns, so unlike amazon.py this
one doesn't need per-user column-name configuration.
"""
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import config
from models import PlatformResult, WatchEvent

PLATFORM_NAME = "Netflix"

TITLE_COLUMN = "Title"
DATE_COLUMN = "Date"

# Netflix has used both of these date formats across export vintages/regions.
DATE_FORMATS = ["%m/%d/%y", "%d/%m/%y", "%m/%d/%Y", "%d/%m/%Y"]


def _parse_date(raw: str) -> Optional[date]:
    raw = raw.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def fetch(csv_path: Optional[Path] = None) -> PlatformResult:
    csv_path = csv_path or config.NETFLIX_CSV_PATH

    if not csv_path.exists():
        return PlatformResult(
            platform=PLATFORM_NAME,
            error=(
                f"No export found at {csv_path}. Download it from Netflix "
                "(Account > Viewing activity > Download all) and place it there."
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
                        f"Found columns: {reader.fieldnames}"
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
