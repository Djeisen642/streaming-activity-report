"""Pure parse helpers inside the scraper modules, checked against strings
captured verbatim from the live sites (2026-09-05). Importing the scraper
modules pulls in playwright, so run these with the project venv."""
import unittest
from datetime import date

from scrapers import base, disneyplus, hulu, netflix, primevideo


class DisneyShowTitleTest(unittest.TestCase):
    CASES = [
        ("Star Wars: A New Hope (Episode IV) 2 hours remaining",
         "Star Wars: A New Hope (Episode IV)"),
        ("Percy Jackson and the Olympians Season 2 Episode 2 Demon Pigeons Attack 12 minutes remaining",
         "Percy Jackson and the Olympians"),
        ("Star Wars: Visions Season 2 Episode 3 In the Stars Watch Next Episode",
         "Star Wars: Visions"),
        ("Zootopia 1 hour 3 minutes remaining", "Zootopia"),
        ("The Little Mermaid 2 hours 22 minutes remaining", "The Little Mermaid"),
        ("Ironheart Season 1 Episode 4 Bad Magic Watch Next Episode", "Ironheart"),
        ("X-Men ’97 Season 1 Episode 3 Fire Made Flesh Watch Next Episode", "X-Men ’97"),
        ("", ""),
    ]

    def test_strips_episode_and_time_tail(self):
        for raw, want in self.CASES:
            with self.subTest(raw=raw[:40]):
                self.assertEqual(disneyplus._show_title(raw), want)


class HuluTitlesTest(unittest.TestCase):
    def test_reads_whichever_title_field_is_present_and_skips_empties(self):
        items = [
            {"metrics_info": {"target_name": "One-Punch Man"}},
            {"visuals": {"title": "The Orville"}},
            {"name": "Paradise"},
            {"metrics_info": {}},                        # nothing usable -> skipped
            {"metrics_info": {"target_name": "  Chad Powers  "}},
        ]
        self.assertEqual(
            hulu._titles_from_items(items),
            ["One-Punch Man", "The Orville", "Paradise", "Chad Powers"],
        )


class NetflixDateFormatsTest(unittest.TestCase):
    def test_locale_selects_day_or_month_first(self):
        self.assertEqual(netflix._date_formats("en")[0], "%m/%d/%y")
        self.assertEqual(netflix._date_formats("en-US")[0], "%m/%d/%y")
        self.assertEqual(netflix._date_formats("fr")[0], "%d/%m/%y")
        self.assertEqual(netflix._date_formats("en-GB")[0], "%d/%m/%y")

    def test_captured_strings_parse_to_the_right_day(self):
        self.assertEqual(
            base.parse_date_with_formats("9/03/26", netflix._date_formats("en")), date(2026, 9, 3))
        self.assertEqual(
            base.parse_date_with_formats("16/5/26", netflix._date_formats("fr")), date(2026, 5, 16))


class PrimeDateHeaderTest(unittest.TestCase):
    def test_parses_the_watch_history_date_headers(self):
        self.assertEqual(primevideo._parse_date("September 2, 2026"), date(2026, 9, 2))
        self.assertEqual(primevideo._parse_date("Aug 26, 2026"), date(2026, 8, 26))
        self.assertIsNone(primevideo._parse_date("not a date"))


if __name__ == "__main__":
    unittest.main()
