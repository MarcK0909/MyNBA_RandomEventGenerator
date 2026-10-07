import unittest
from copy import deepcopy

from season_notebook import (active_notes, advance_season, delete_note,
                             normalize_notebook, save_note, scheduled_notes,
                             season_label, set_note_done)


class SeasonNotebookTests(unittest.TestCase):
    def setUp(self):
        self.notebook = normalize_notebook({"current_season": 2026, "items": [
            {"id": "current", "title": "Current note", "season": 2026, "done": False},
            {"id": "done", "title": "Completed note", "season": 2026, "done": True},
            {"id": "next", "title": "Next season", "season": 2027},
            {"id": "later", "title": "Much later", "season": 2029},
        ]})

    def test_legacy_notes_migrate_without_losing_fields(self):
        legacy = [{"id": 123, "title": "Legacy", "due": "2026-11-01", "done": True}]
        state = normalize_notebook(legacy, 2026)
        self.assertEqual(state["current_season"], 2026)
        self.assertEqual(state["items"][0], {**legacy[0], "id": "123", "season": 2026})
        self.assertNotIn("season", legacy[0])
        self.assertEqual(normalize_notebook({"items": legacy}, 2026)["items"], state["items"])

    def test_future_notes_are_hidden_before_assigned_season(self):
        self.assertEqual([n["id"] for n in active_notes(self.notebook)], ["current", "done"])
        self.assertEqual([n["id"] for n in scheduled_notes(self.notebook)], ["next", "later"])

    def test_rollover_deletes_open_and_completed_departing_notes_only(self):
        original = deepcopy(self.notebook)
        updated = advance_season(self.notebook)
        self.assertEqual(updated["current_season"], 2027)
        self.assertEqual([n["id"] for n in updated["items"]], ["next", "later"])
        self.assertEqual([n["id"] for n in active_notes(updated)], ["next"])
        self.assertEqual(self.notebook, original)

    def test_multiple_rollovers_do_not_reveal_later_notes_early(self):
        updated = advance_season(advance_season(self.notebook))
        self.assertEqual([n["id"] for n in active_notes(updated)], [])
        self.assertEqual([n["id"] for n in active_notes(advance_season(updated))], ["later"])

    def test_save_edit_complete_delete(self):
        state = save_note(self.notebook, title="  A rookie story  ", details=" Details ", season=2026)
        note = state["items"][0]
        self.assertEqual(note["title"], "A rookie story")
        self.assertEqual(note["details"], "Details")
        state = set_note_done(state, note["id"], True)
        state = save_note(state, title="Move to next season", season=2027, note_id=note["id"])
        self.assertTrue(state["items"][0]["done"])
        self.assertEqual(state["items"][0]["created_at"], note["created_at"])
        self.assertNotIn(note["id"], [n["id"] for n in active_notes(state)])
        state = delete_note(state, note["id"])
        self.assertNotIn(note["id"], [n["id"] for n in state["items"]])

    def test_reject_empty_title_past_season_and_missing_edit_target(self):
        for values in ({"title": " ", "season": 2026}, {"title": "X", "season": 2025},
                       {"title": "X", "season": 2026, "note_id": "missing"}):
            with self.assertRaises(ValueError):
                save_note(self.notebook, **values)

    def test_review_date_is_optional_and_validated(self):
        self.assertEqual(save_note(self.notebook, title="X", season=2026)["items"][0]["due"], "")
        with self.assertRaises(ValueError):
            save_note(self.notebook, title="X", season=2026, due="not-a-date")

    def test_invalid_saved_data_is_not_silently_discarded(self):
        for payload in ("bad", {"items": {}}, {"items": [None]}, {"current_season": True},
                        {"items": [{"season": "future"}]}):
            with self.assertRaises(ValueError):
                normalize_notebook(payload)

    def test_labels_support_numbered_and_calendar_seasons(self):
        self.assertEqual(season_label(1), "Season 1")
        self.assertEqual(season_label(2026), "2026–27")


if __name__ == "__main__":
    unittest.main()
