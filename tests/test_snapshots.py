"""snapshots.record_activity — the run-to-run activity-date derivation for
platforms (Hulu, Disney+) that publish no watch dates. Correctness only
shows across runs, so it can't be checked from a single main.py run."""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import config
import snapshots


class RecordActivityTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "snap.json"
        patcher = mock.patch.object(config, "ACTIVITY_SNAPSHOT_PATH", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def rec(self, titles, day):
        return snapshots.record_activity("Hulu", titles, today=day)

    def test_first_record_returns_that_day(self):
        # No prior baseline to diff against -> "last changed" is now.
        self.assertEqual(self.rec(["The Bear", "Shogun"], date(2026, 1, 1)), date(2026, 1, 1))

    def test_unchanged_set_keeps_original_date(self):
        self.rec(["The Bear", "Shogun"], date(2026, 1, 1))
        self.assertEqual(self.rec(["The Bear", "Shogun"], date(2026, 1, 8)), date(2026, 1, 1))

    def test_reshuffle_dupes_whitespace_is_not_a_change(self):
        self.rec(["The Bear", "Shogun"], date(2026, 1, 1))
        self.assertEqual(
            self.rec(["  Shogun ", "The Bear", "The Bear"], date(2026, 1, 15)),
            date(2026, 1, 1),
        )

    def test_changed_set_moves_the_date(self):
        self.rec(["The Bear", "Shogun"], date(2026, 1, 1))
        self.assertEqual(self.rec(["Shogun", "Andor"], date(2026, 1, 22)), date(2026, 1, 22))

    def test_date_sticks_through_a_later_unchanged_run(self):
        self.rec(["The Bear"], date(2026, 1, 1))
        self.rec(["Andor"], date(2026, 1, 22))
        self.assertEqual(self.rec(["Andor"], date(2026, 2, 1)), date(2026, 1, 22))

    def test_emptied_rail_counts_as_a_change_then_settles(self):
        self.rec(["The Bear"], date(2026, 1, 1))
        self.assertEqual(self.rec([], date(2026, 2, 8)), date(2026, 2, 8))
        self.assertEqual(self.rec([], date(2026, 2, 15)), date(2026, 2, 8))

    def test_platforms_are_independent(self):
        snapshots.record_activity("Hulu", ["x"], today=date(2026, 1, 1))
        self.assertEqual(
            snapshots.record_activity("Disney+", ["Loki"], today=date(2026, 3, 1)),
            date(2026, 3, 1),
        )
        self.assertEqual(
            snapshots.record_activity("Hulu", ["x"], today=date(2026, 3, 2)),
            date(2026, 1, 1),
        )

    def test_first_seen_preserved_across_changes(self):
        self.rec(["a"], date(2026, 1, 1))
        self.rec(["b"], date(2026, 2, 1))
        self.assertEqual(json.loads(self.path.read_text())["Hulu"]["first_seen"], "2026-01-01")

    def test_corrupt_state_file_is_ignored(self):
        self.path.write_text("{ not json", encoding="utf-8")
        self.assertEqual(self.rec(["a"], date(2026, 5, 1)), date(2026, 5, 1))


if __name__ == "__main__":
    unittest.main()
