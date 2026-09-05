"""
Tracks per-platform scrape health across runs and decides when a scraper
(Netflix, Prime Video, Hulu, Disney+) has failed enough consecutive times
to be worth an automated fix attempt.

Only two things count as a failure signal here — deliberately not "the
scraper returned the same data as last run":

  1. The fetch errored (timeout, missing selector, login never detected,
     an endpoint whose shape changed — the scrapers raise for that rather
     than return an empty list).
  2. The fetch succeeded but found 0 items on a run where a previous run
     found some — usually a broken selector/endpoint. (For Hulu/Disney+
     this can also be a genuinely emptied "Continue Watching" rail; that's
     the same rare false positive the tool already tolerates for idle
     dated platforms, and a triggered fix run will just report nothing
     wrong.)

Unchanged output across runs is excluded on purpose: this tool's entire
point is finding platforms you've stopped watching, so an idle platform
returning the same (correct) small/zero result run after run is expected
behavior, not evidence of a broken scraper.

The zero-after-nonzero check also skips straight over a run that
immediately followed an unrelated error. Without that, a transient error
(last_count frozen at its pre-error value) followed by a genuinely idle
0-event run would misread as "dropped from N to 0" and falsely flag a
scraper that isn't actually broken.
"""
import json
from typing import Dict, List, Optional

import config
from models import PlatformResult

# Consecutive failures before a platform is considered break-worthy.
FAILURE_THRESHOLD = 2


def _load() -> Dict[str, dict]:
    if not config.SCRAPER_HEALTH_PATH.exists():
        return {}
    try:
        return json.loads(config.SCRAPER_HEALTH_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state: Dict[str, dict]) -> None:
    config.SCRAPER_HEALTH_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _is_failure(
    result: PlatformResult, prior_last_count: Optional[int], prior_run_was_error: bool
) -> bool:
    if result.error:
        return True
    if (
        len(result.events) == 0
        and prior_last_count is not None
        and prior_last_count > 0
        and not prior_run_was_error
    ):
        return True
    return False


def record_and_check(results: List[PlatformResult]) -> List[str]:
    """
    Updates health state from this run's results and returns platform
    names that just crossed FAILURE_THRESHOLD — i.e. are newly
    break-worthy, not still-broken-from-before. A platform only reappears
    in this list after it recovers (a successful, non-zero run) and then
    fails again, so a persistently broken scraper doesn't retrigger a fix
    attempt on every single run.
    """
    state = _load()
    newly_broken = []

    for result in results:
        entry = state.get(
            result.platform,
            {
                "consecutive_failures": 0,
                "last_count": None,
                "last_run_was_error": False,
                "fix_triggered": False,
            },
        )
        prior_last_count = entry.get("last_count")
        prior_run_was_error = entry.get("last_run_was_error", False)
        failed = _is_failure(result, prior_last_count, prior_run_was_error)

        if failed:
            entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
        else:
            entry["consecutive_failures"] = 0
            entry["last_count"] = len(result.events)
            entry["fix_triggered"] = False

        entry["last_run_was_error"] = bool(result.error)

        if (
            failed
            and entry["consecutive_failures"] >= FAILURE_THRESHOLD
            and not entry.get("fix_triggered")
        ):
            entry["fix_triggered"] = True
            newly_broken.append(result.platform)

        state[result.platform] = entry

    _save(state)
    return newly_broken
