"""
Derives an "activity date" for platforms that expose no per-item watch
date at all.

Hulu and Disney+ don't publish a dated watch history anywhere — not in
the page DOM, not in the JSON their web apps fetch (checked directly).
What they do expose is an ordered "Continue Watching" rail. This module
snapshots the set of titles in that rail each run and remembers the last
run on which it changed.

"Activity" here means the Continue Watching set changed between two runs:
someone started something, finished something (it drops off the rail), or
resumed something. An unchanged set across runs is the idle signal — the
same thing health.py already relies on, and the same reason the tool
exists. The resolution of the derived date is therefore however often you
actually run the tool; for a 30-day "have I stopped using this?" question
a weekly cron is plenty.

Order within the rail is not a signal (it reflects recommendation
weighting as much as recency), so the set is sorted before comparison —
a reshuffled-but-identical rail does not count as activity.

State lives in ACTIVITY_SNAPSHOT_PATH (gitignored — it holds titles from
your account).
"""
import json
from datetime import date
from typing import Dict, List, Optional

import config


def _load() -> Dict[str, dict]:
    if not config.ACTIVITY_SNAPSHOT_PATH.exists():
        return {}
    try:
        return json.loads(config.ACTIVITY_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state: Dict[str, dict]) -> None:
    config.ACTIVITY_SNAPSHOT_PATH.write_text(
        json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
    )


def _normalize(titles: List[str]) -> List[str]:
    """Dedup, strip, drop blanks, sort — order and repeats are not signal."""
    return sorted({t.strip() for t in titles if t and t.strip()})


def record_activity(
    platform: str, titles: List[str], today: Optional[date] = None
) -> Optional[date]:
    """
    Update the stored Continue Watching snapshot for `platform` and return
    the date its title set was last observed to change.

    - First time this platform is ever seen: there's no prior baseline to
      compare against, so "last changed" is today. (Self-corrects on later
      runs; on the very first run the platform just reads as freshly
      active, which is the honest default when we know nothing.)
    - Set changed since last run: snapshot is updated, last-changed is
      today, today is returned.
    - Set unchanged: the stored last-changed date is returned.

    An empty rail is a valid state (nobody has anything in progress) and
    is snapshotted like any other; a scrape that breaks and returns
    nothing is health.py's problem, not this module's.
    """
    today = today or date.today()
    key = _normalize(titles)
    state = _load()
    entry = state.get(platform)

    if entry is None or key != entry.get("titles"):
        state[platform] = {
            "titles": key,
            "last_changed": today.isoformat(),
            "first_seen": (entry or {}).get("first_seen", today.isoformat()),
        }
        _save(state)
        return today

    stored = entry.get("last_changed")
    try:
        return date.fromisoformat(stored) if stored else today
    except ValueError:
        return today
