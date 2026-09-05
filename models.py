"""Shared data model returned by every platform fetcher."""
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class WatchEvent:
    title: str
    # Not every platform exposes a per-item watch date (e.g. Hulu's default
    # history view is order-only), so this must stay optional end-to-end.
    watched_date: Optional[date] = None
    raw_source: str = ""


@dataclass
class PlatformResult:
    platform: str
    events: List[WatchEvent] = field(default_factory=list)
    error: Optional[str] = None
    # Set only for platforms that expose no per-item watch date (Hulu,
    # Disney+): the date their "Continue Watching" rail was last seen to
    # change, derived by snapshots.py across runs. When this is set, the
    # events carry titles but no usable watched_date, and the report
    # labels the figure as list-change activity, not a watch date.
    last_activity_date: Optional[date] = None
    # Which account profile the figures reflect, when the scraper only
    # looked at one (the active profile) rather than the whole account.
    profile: Optional[str] = None
