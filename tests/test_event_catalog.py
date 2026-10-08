import unittest
from pathlib import Path

from event_engine import build_event_note, load_events


class EventCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_events(str(Path(__file__).resolve().parents[1] / "events.json"))

    def find(self, phase, title):
        return next(event for event in self.catalog[phase] if event["title"] == title)

    def test_every_event_has_explicit_play_and_review_metadata(self):
        for phase, pool in self.catalog.items():
            for event in pool:
                with self.subTest(phase=phase, title=event["title"]):
                    for field in ("id", "impact", "duration", "target", "tracking"):
                        self.assertTrue(event.get(field), field)
                    self.assertIn("needs_review", event)
                    self.assertIsInstance(event["requires_team"], bool)
                    self.assertIsInstance(event["requires_player"], bool)
                    if event["needs_review"]:
                        self.assertTrue(event["review_notes"])
                        self.assertTrue(event["original_effect"])

    def test_known_severity_errors_and_outsized_boosts_are_fixed(self):
        self.assertEqual(self.find("Training Camp", "New Free Throw Routine - Decline")["impact"], "Low Impact")
        self.assertEqual(self.find("Summer League", "Tough Luck")["impact"], "High Impact")
        self.assertEqual(self.find("Regular Season", "Player Needs Surgery (Severe)")["impact"], "High Impact")
        self.assertNotIn("by 30", self.find("Training Camp", "Summer 3")["effect"])
        self.assertEqual(self.find("Training Camp", "Small Setback")["roll_max"], 14)
        for phase in ("Regular Season", "Regular Season Post-Deadline"):
            for title in ("Team Argument", "Chemistry Builds Wins"):
                self.assertNotIn("force win", self.find(phase, title)["effect"])
                self.assertNotIn("force loss", self.find(phase, title)["effect"])

    def test_post_deadline_events_use_approved_regular_season_fixes(self):
        for title in ("G-League Scoring Intake", "G-League Passing Intake", "G-League Rebounding Intake",
                      "Falling Down", "Two-Way Impact", "My Last Rodeo"):
            with self.subTest(title=title):
                approved = self.find("Regular Season", title)
                updated = self.find("Regular Season Post-Deadline", title)
                expected = approved["effect"]
                if title == "Falling Down":
                    expected = expected.replace("Top-15", "Top-10")
                self.assertEqual(updated["effect"], expected)
                self.assertFalse(updated["needs_review"])
                self.assertNotIn("review_notes", updated)
                self.assertNotIn("review_suggestion", updated)
                self.assertTrue(updated["original_effect"])

    def test_playoffs_have_more_variety_and_similar_events_differ(self):
        self.assertGreaterEqual(len(self.catalog["Playoffs"]), 18)
        self.assertNotEqual(self.find("Draft Combine", "Switchability Pop")["effect"],
                            self.find("Draft Combine", "Clamp Session")["effect"])
        self.assertNotEqual(self.find("Regular Season Post-Deadline", "Play-In Push")["effect"],
                            self.find("Regular Season Post-Deadline", "Play-In Pressure")["effect"])

    def test_future_return_and_end_of_season_tracking(self):
        future = self.find("Free Agency", "Trip to Europe")
        self.assertEqual(build_event_note(future, 2026)["season"], 2027)
        self.assertEqual((future["roll_min"], future["roll_max"]), (1, 2))
        self.assertIn("only at the start of the next season", future["effect"])
        for phase in ("Regular Season", "Regular Season Post-Deadline"):
            retirement = self.find(phase, "My Last Rodeo")
            self.assertTrue(retirement["resolve_before_rollover"])
            self.assertEqual(retirement["note_season_offset"], 0)

    def test_rolls_cover_injuries_caps_and_playoff_availability(self):
        for phase, title, bounds in (
            ("Regular Season", "Minutes Restriction", (20, 24)),
            ("Regular Season", "Player Needs Surgery (Moderate)", (45, 90)),
            ("Playoffs", "Game-Time Decision", (1, 6)),
            ("Regular Season Post-Deadline", "Emotional Game", (1, 2)),
        ):
            event = self.find(phase, title)
            self.assertEqual((event["roll_min"], event["roll_max"]), bounds)
            self.assertTrue(event["roll_purpose"])


if __name__ == "__main__":
    unittest.main()
