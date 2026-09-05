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
