"""health.record_and_check — the consecutive-failure state machine that
decides when main.py shells out to `claude -p`. Every threshold crossing
has a real side effect, so this is the only safe way to exercise it."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import config
import health
from models import PlatformResult, WatchEvent


def err(platform="Hulu"):
    return PlatformResult(platform=platform, error="boom")


def ok(platform="Hulu", n=1):
    return PlatformResult(platform=platform, events=[WatchEvent(title=f"t{i}") for i in range(n)])


class RecordAndCheckTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "health.json"
        patcher = mock.patch.object(config, "SCRAPER_HEALTH_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def entry(self, platform="Hulu"):
        return json.loads(self.path.read_text())[platform]

    def test_first_failure_does_not_trigger(self):
        self.assertEqual(health.record_and_check([err()]), [])
        self.assertEqual(self.entry()["consecutive_failures"], 1)

    def test_threshold_crossing_triggers_exactly_once(self):
        health.record_and_check([err()])
        self.assertEqual(health.record_and_check([err()]), ["Hulu"])
        self.assertTrue(self.entry()["fix_triggered"])

    def test_no_retrigger_while_still_broken(self):
        health.record_and_check([err()])
        health.record_and_check([err()])
        self.assertEqual(health.record_and_check([err()]), [])
        self.assertEqual(self.entry()["consecutive_failures"], 3)

    def test_a_successful_nonzero_run_resets(self):
        health.record_and_check([err()])
        health.record_and_check([err()])
        health.record_and_check([ok(n=7)])
        e = self.entry()
        self.assertEqual(e["consecutive_failures"], 0)
        self.assertFalse(e["fix_triggered"])
        self.assertEqual(e["last_count"], 7)

    def test_retriggers_after_recovering_then_failing_again(self):
        for result in [err(), err(), ok(n=3), err()]:
            health.record_and_check([result])
        self.assertEqual(health.record_and_check([err()]), ["Hulu"])

    def test_zero_after_nonzero_with_clean_prior_run_is_a_failure(self):
        health.record_and_check([ok("Disney+", 4)])
        health.record_and_check([ok("Disney+", 0)])
        self.assertEqual(self.entry("Disney+")["consecutive_failures"], 1)

    def test_zero_right_after_an_error_is_not_a_failure(self):
        # last_count freezes at its pre-error value; without the guard a
        # genuinely idle 0 would misread as "dropped from N to 0".
        health.record_and_check([ok("Netflix", 5)])
        health.record_and_check([err("Netflix")])
        health.record_and_check([ok("Netflix", 0)])
        e = self.entry("Netflix")
        self.assertEqual(e["consecutive_failures"], 0)
        self.assertEqual(e["last_count"], 0)

    def test_a_platform_that_is_always_empty_never_triggers(self):
        triggered = []
        for _ in range(4):
            triggered += health.record_and_check([ok("Hulu", 0)])
        self.assertEqual(triggered, [])
        self.assertEqual(self.entry()["consecutive_failures"], 0)


if __name__ == "__main__":
    unittest.main()
