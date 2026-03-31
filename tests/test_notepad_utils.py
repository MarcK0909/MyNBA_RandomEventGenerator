from datetime import date, datetime
import unittest

from notepad_utils import (
    build_auto_notepad_item,
    estimate_due_date,
    is_temporary_effect,
)


class NotepadUtilsTests(unittest.TestCase):
    def test_is_temporary_effect_true_false(self):
        self.assertTrue(is_temporary_effect("The player drawn is out 7-14 days."))
        self.assertTrue(is_temporary_effect("Suspend for the next 5 games."))
        self.assertFalse(is_temporary_effect("Increase 3PT permanently by 2."))

    def test_estimate_due_date_parses_range_days(self):
        base = date(2026, 3, 31)
        due = estimate_due_date("Out 7-14 days with ankle sprain.", today=base)
        self.assertEqual(due, date(2026, 4, 14))

    def test_estimate_due_date_parses_games(self):
        base = date(2026, 3, 31)
        due = estimate_due_date("Decrease 3PT for the next 12 games.", today=base)
        self.assertEqual(due, date(2026, 4, 24))

    def test_estimate_due_date_defaults(self):
        base = date(2026, 3, 31)
        due = estimate_due_date("Temporary dip in form.", today=base)
        self.assertEqual(due, date(2026, 4, 10))

    def test_build_auto_notepad_item_with_player_and_team(self):
        now = datetime(2026, 3, 31, 12, 0, 0)
        payload = {
            "title": "Shooting Slump Spiral",
            "effect": "The player drawn is out for the next 12 games with a shooting slump.",
            "phase": "Regular Season",
            "player": "#4 (Highest Overall)",
            "team": "Denver Nuggets",
        }

        item = build_auto_notepad_item(payload, now=now, today=date(2026, 3, 31))
        self.assertIsNotNone(item)
        if item is None:
            return

        self.assertEqual(item["title"], "Temporary Event Tracker: Shooting Slump Spiral")
        self.assertIn("Player #4 (Highest Overall) on Denver Nuggets", item["details"])
        self.assertEqual(item["phase"], "Regular Season")
        self.assertEqual(item["due"], "2026-04-24")
        self.assertFalse(item["done"])

    def test_build_auto_notepad_item_returns_none_for_permanent(self):
        payload = {
            "title": "Permanent Boost",
            "effect": "Increase Free Throw permanently by 2.",
        }
        item = build_auto_notepad_item(payload, now=datetime(2026, 3, 31, 12, 0, 0), today=date(2026, 3, 31))
        self.assertIsNone(item)


if __name__ == "__main__":
    unittest.main()
