"""report.build_report — the three activity bases (real watch date /
Continue-Watching list-change / unknown), ranking across them, the
list-change labelling and marker, profile notes, idle flagging."""
import re
import unittest
from datetime import date

import report
from models import PlatformResult, WatchEvent

TODAY = date(2026, 9, 5)


class BuildReportTest(unittest.TestCase):
    def setUp(self):
        self.results = [
            PlatformResult("Netflix", [                       # real dates -> "watched"
                WatchEvent("Recent", date(2026, 8, 20)),      # 16d idle
                WatchEvent("Old", date(2026, 1, 1)),
                WatchEvent("No date", None),
            ], profile="Jason"),
            PlatformResult("Hulu", [WatchEvent("A", None), WatchEvent("B", None)],
                           last_activity_date=date(2026, 3, 1), profile="Jason"),   # ~188d
            PlatformResult("Disney+", [WatchEvent("X", None)],
                           last_activity_date=date(2026, 9, 2)),                    # 3d
            PlatformResult("Prime Video", [], error="scrape failed: login not detected"),
        ]
        self.html = report.build_report(self.results, today=TODAY)
        self.body = self.html.split("<tbody>")[1].split("</tbody>")[0]

    def _order(self):
        return re.findall(r"<tr[^>]*><td>([A-Za-z+ ]+)</td>", self.body)

    def test_ranked_by_idle_descending_across_bases(self):
        order = self._order()
        self.assertLess(order.index("Hulu"), order.index("Netflix"))     # 188d > 16d
        self.assertLess(order.index("Netflix"), order.index("Disney+"))  # 16d > 3d

    def test_errored_platform_sorts_into_the_unknown_block(self):
        self.assertEqual(self._order()[-1], "Prime Video")

    def test_list_change_row_carries_the_marker(self):
        self.assertIn("<td>2026-03-01 ↻</td>", self.body)

    def test_real_watch_date_row_has_no_marker(self):
        self.assertIn("<td>2026-08-20</td>", self.body)

    def test_idle_flag_uses_the_threshold_regardless_of_basis(self):
        self.assertIn('class="row-idle"><td>Hulu', self.body)
        self.assertNotIn('class="row-idle"><td>Disney+', self.body)  # only 3d

    def test_footnote_explains_the_marker(self):
        self.assertIn("&#8635;", self.html)
        self.assertIn("Continue Watching", self.html)

    def test_cards_word_the_two_bases_differently(self):
        self.assertIn("Continue Watching last changed:", self.html)  # Hulu
        self.assertIn("Last watched:", self.html)                    # Netflix

    def test_profile_note_shown_only_when_profile_set(self):
        self.assertIn("Profile checked: Jason", self.html)
        self.assertEqual(self.html.count("Profile checked:"), 2)     # Netflix + Hulu, not Disney+

    def test_error_is_surfaced_in_card_and_table(self):
        self.assertIn("login not detected", self.html)
        self.assertIn("card-error", self.html)

    def test_empty_result_list_still_renders(self):
        self.assertIn("<table>", report.build_report([], today=TODAY))


class ActivityBasisTest(unittest.TestCase):
    def test_a_real_watch_date_wins_over_last_activity_date(self):
        r = PlatformResult("X", [WatchEvent("t", date(2026, 6, 1))],
                           last_activity_date=date(2026, 8, 1))
        self.assertEqual(report._activity(r), ("watched", date(2026, 6, 1)))

    def test_list_change_when_events_carry_no_dates(self):
        r = PlatformResult("X", [WatchEvent("t", None)], last_activity_date=date(2026, 8, 1))
        self.assertEqual(report._activity(r), ("list-change", date(2026, 8, 1)))

    def test_unknown_when_there_is_no_signal(self):
        self.assertEqual(report._activity(PlatformResult("X", [], error="boom")), ("unknown", None))


if __name__ == "__main__":
    unittest.main()
