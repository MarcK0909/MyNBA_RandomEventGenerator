"""Exercise note editing and season rollover without touching real user data."""

import json
from copy import deepcopy
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from notepad_store import NotepadStore
from test_notepad_store import fake_firestore
from season_notebook import advance_season, save_note


ROOT = Path(__file__).resolve().parents[1]


class NotebookAppTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        previous = Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(self.directory.name)
        shutil.copy(ROOT / "events.json", "events.json")
        self.cloud = fake_firestore({"current_season": 2026, "items": [
            {"id": "current", "title": "Current storyline", "details": "Rookie minutes", "season": 2026, "done": False},
            {"id": "finished", "title": "Finished storyline", "season": 2026, "done": True},
            {"id": "future", "title": "Next year only", "season": 2027, "done": False},
            {"id": "later", "title": "Much later", "season": 2028, "done": False},
        ]})
        factory = patch("notepad_store.NotepadStore", side_effect=lambda *args, **kwargs: NotepadStore(self.cloud, initial_season=kwargs.get("initial_season", 2026)))
        factory.start()
        self.addCleanup(factory.stop)
        self.app = self.new_app()

    def new_app(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
        app.secrets["firebase"] = {}
        app.run()
        self.assertFalse(app.exception)
        return app

    def open_notebook(self):
        self.app.radio(key="workspace").set_value("Notepad").run()

    def test_startup_read_failure_stops_without_empty_notebook(self):
        with patch.object(self.cloud, "get", side_effect=OSError("offline")):
            app = self.new_app()
        self.assertTrue(app.error)
        self.assertNotIn("save_note", [button.key for button in app.button])
        self.cloud.set.assert_not_called()

    def test_failed_save_keeps_draft_and_saved_notes(self):
        before = deepcopy(self.cloud.document_data)
        self.app.text_input(key="note_title").set_value("Keep this draft")
        with patch.object(self.cloud, "set", side_effect=PermissionError("denied")):
            self.app.button(key="save_note").click().run()
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.text_input(key="note_title").value, "Keep this draft")
        self.assertEqual(self.cloud.document_data, before)
        self.app.button(key="save_note").click().run()
        self.assertEqual(self.cloud.document_data["items"][0]["title"], "Keep this draft")
        self.assertFalse(Path("event_notepad.json").exists())

    def test_match_workspace_keeps_season_event_draft_and_saved_notes(self):
        before = deepcopy(self.cloud.document_data)
        self.app.text_input(key="note_title").set_value("My season draft").run()
        self.app.text_area(key="note_details").set_value("Keep these details").run()
        self.app.selectbox(key="note_season").set_value(2027).run()
        self.app.session_state.last_event = {"title": "Season event", "effect": "Keep me", "phase": "Playoffs"}
        self.app.button(key="phase_btn_Playoffs").click().run()
        self.app.radio(key="workspace").set_value("Match Events").run()
        self.assertNotIn("prepare_next_season", [button.key for button in self.app.button])
        with patch("match_events.random.choice", side_effect=lambda pool: pool[0]), patch("match_events.random.randint", return_value=15):
            self.app.button(key="draw_match_event").click().run()
            event = self.app.session_state.last_match_event
            self.assertEqual(event["mode"], "Player Lock")
            self.assertEqual(event["player"], "#15 (rank by overall)")
            self.app.button(key="draw_match_event").click().run()
        self.assertNotEqual(self.app.session_state.last_match_event["id"], event["id"])
        self.app.radio(key="workspace").set_value("Event Generator").run()
        self.assertEqual(self.app.text_input(key="note_title").value, "My season draft")
        self.assertEqual(self.app.text_area(key="note_details").value, "Keep these details")
        self.assertEqual(self.app.selectbox(key="note_season").value, 2027)
        self.assertEqual(self.app.session_state.last_event["title"], "Season event")
        self.app.radio(key="workspace").set_value("Match Events").run()
        self.app.button(key="clear_match_event").click().run()
        self.assertIsNone(self.app.session_state.last_match_event)
        self.assertFalse(self.app.exception)
        self.assertEqual(deepcopy(self.cloud.document_data), before)

    def test_match_workspace_draws_without_setup_and_keeps_result_on_rerun(self):
        self.app.radio(key="workspace").set_value("Match Events").run()
        keys = [widget.key for kind in (self.app.radio, self.app.selectbox, self.app.text_input) for widget in kind]
        for removed in ("match_mode", "match_team", "match_player"):
            self.assertNotIn(removed, keys)
        with patch("match_events.random.choice", side_effect=lambda pool: "Full Team" if isinstance(pool[0], str) else pool[0]), patch("match_events.random.randint", return_value=12):
            self.app.button(key="draw_match_event").click().run()
        event = dict(self.app.session_state.last_match_event)
        self.assertEqual(event["mode"], "Full Team")
        self.assertEqual(event["player_rank"], 12)
        self.assertTrue(any("**Control:** Full team" in item.value for item in self.app.markdown))
        self.assertTrue(any("**Affected player:** #12" in item.value for item in self.app.markdown))
        self.app.run()
        self.assertEqual(dict(self.app.session_state.last_match_event), event)
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.warning)

    def add_review_fixture(self):
        # Review behavior must remain testable after the user approves or
        # removes every flagged event in the real catalog.
        path = Path("events.json")
        catalog = json.loads(path.read_text())
        catalog["Free Agency"].append({
            "id": "test--review-fixture", "title": "Review fixture",
            "effect": "Check the selected player next season.", "impact": "Medium Impact",
            "target": "An eligible player", "duration": "Next season",
            "tracking": "Check the player when the next season starts.",
            "requires_team": False, "requires_player": False,
            "needs_review": True, "review_notes": ["Choose an eligible player."],
            "note_season_offset": 1,
        })
        path.write_text(json.dumps(catalog))

    def test_schedule_note_is_hidden_until_its_season(self):
        self.open_notebook()
        self.assertEqual(self.app.selectbox(key="note_season").value, 2026)
        self.app.text_input(key="note_title").set_value("A scheduled note")
        self.app.selectbox(key="note_season").set_value(2027)
        self.app.button(key="save_note").click().run()
        saved = deepcopy(self.cloud.document_data)
        note = saved["items"][0]
        self.assertEqual(note["season"], 2027)
        self.assertNotIn(f"edit_{note['id']}", [button.key for button in self.app.button])
        self.assertEqual(self.app.selectbox(key="note_season").value, 2026)
        self.assertEqual(self.app.radio(key="workspace").value, "Notepad")

    def test_edit_complete_reopen_and_delete_without_losing_view(self):
        self.open_notebook()
        self.app.button(key="edit_current").click().run()
        self.assertEqual(self.app.text_input(key="note_title").value, "Current storyline")
        self.app.text_input(key="note_title").set_value("Updated storyline")
        self.app.button(key="save_note").click().run()
        self.app.button(key="done_current").click().run()
        self.assertEqual(self.app.radio(key="workspace").value, "Notepad")
        self.app.selectbox(key="note_status").set_value("Completed").run()
        self.app.button(key="done_current").click().run()
        self.app.selectbox(key="note_status").set_value("Open notes").run()
        self.app.button(key="delete_current").click().run()
        self.assertFalse(self.app.exception)
        self.assertNotIn("current", [note["id"] for note in deepcopy(self.cloud.document_data)["items"]])

    def test_confirmed_rollover_deletes_departing_notes_and_survives_reload(self):
        self.app.button(key="phase_btn_Playoffs").click().run()
        self.app.button(key="prepare_next_season").click().run()
        self.assertEqual(deepcopy(self.cloud.document_data)["current_season"], 2026)
        self.app.button(key="confirm_next_season_button").click().run()
        self.assertFalse(self.app.exception)
        saved = deepcopy(self.cloud.document_data)
        self.assertEqual(saved["current_season"], 2027)
        self.assertEqual([note["id"] for note in saved["items"]], ["future", "later"])
        self.assertEqual(self.app.session_state.selected_phase, "Coaching Carousel")
        self.app = self.new_app()
        self.open_notebook()
        self.assertIn("edit_future", [button.key for button in self.app.button])
        self.assertNotIn("edit_later", [button.key for button in self.app.button])
        self.assertEqual(self.app.selectbox(key="note_season").value, 2027)

    def test_failed_rollover_keeps_season_and_notes(self):
        self.app.button(key="phase_btn_Playoffs").click().run()
        self.app.button(key="prepare_next_season").click().run()
        before = deepcopy(self.cloud.document_data)
        with patch.object(self.cloud, "set", side_effect=OSError("offline")):
            self.app.button(key="confirm_next_season_button").click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.session_state.notebook["current_season"], 2026)
        self.assertEqual(deepcopy(self.cloud.document_data), before)

    def test_event_draw_does_not_replace_draft(self):
        before = deepcopy(self.cloud.document_data)
        self.app.text_input(key="note_title").set_value("My unsaved idea").run()
        self.app.text_area(key="note_details").set_value("Keep the rookie in the rotation.").run()
        self.assertEqual(self.app.text_input(key="note_title").value, "My unsaved idea")

        event = {"title": "Test rotation change", "effect": "Give the bench extra minutes.",
                 "resolve_before_rollover": True}
        with patch("event_engine.weighted_random_event", return_value=event):
            self.app.button(key="gen_Regular Season").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state.last_event["title"], event["title"])
        self.assertEqual(self.app.text_input(key="note_title").value, "My unsaved idea")
        self.assertEqual(self.app.text_area(key="note_details").value, "Keep the rookie in the rotation.")
        self.assertEqual(deepcopy(self.cloud.document_data), before)

        self.app.button(key="use_event_in_note").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.text_input(key="note_title").value, event["title"])
        self.assertIn(event["effect"], self.app.text_area(key="note_details").value)
        self.assertEqual(deepcopy(self.cloud.document_data), before)

    def test_stale_browser_cannot_restore_notes_after_another_session_advances(self):
        self.open_notebook()
        store = NotepadStore(self.cloud)
        store.save(advance_season(store.load()))
        self.app.button(key="done_current").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state.notebook["current_season"], 2027)
        self.assertFalse(self.app.session_state.confirm_next_season)
        saved = deepcopy(self.cloud.document_data)
        self.assertNotIn("current", [note["id"] for note in saved["items"]])

    def test_tracking_event_suggests_note_without_saving_and_can_be_dismissed(self):
        before = deepcopy(self.cloud.document_data)
        self.app.text_input(key="filter_Regular Season").set_value("Minutes Restriction").run()
        self.app.button(key="gen_Regular Season").click().run()
        self.assertEqual(self.app.text_input(key="note_title").value, "Minutes Restriction")
        self.assertIn("Minutes cap:", self.app.text_area(key="note_details").value)
        self.assertTrue(any("not saved yet" in info.value for info in self.app.info))
        self.assertEqual(deepcopy(self.cloud.document_data), before)
        self.app.button(key="reset_note_editor").click().run()
        self.app.run()
        self.assertEqual(self.app.text_input(key="note_title").value, "")
        self.assertEqual(deepcopy(self.cloud.document_data), before)
        self.app.button(key="gen_Regular Season").click().run()
        self.app.button(key="save_note").click().run()
        self.assertEqual(deepcopy(self.cloud.document_data)["items"][0]["title"], "Minutes Restriction")

    def test_draw_keeps_existing_suggestion_until_saved_or_cleared(self):
        self.app.text_input(key="filter_Regular Season").set_value("Minutes Restriction").run()
        self.app.button(key="gen_Regular Season").click().run()
        details = self.app.text_area(key="note_details").value
        self.app.text_input(key="filter_Regular Season").set_value("Game-Time Decision").run()
        with patch("event_engine.weighted_random_event", return_value={
            "title": "Another follow-up", "effect": "Wait for next year.", "note_season_offset": 1,
        }):
            self.app.text_input(key="filter_Regular Season").set_value("").run()
            self.app.button(key="gen_Regular Season").click().run()
        self.assertEqual(self.app.text_input(key="note_title").value, "Minutes Restriction")
        self.assertEqual(self.app.text_area(key="note_details").value, details)

    def test_tracking_draw_preserves_note_being_edited(self):
        before = deepcopy(self.cloud.document_data)
        self.open_notebook()
        self.app.button(key="edit_current").click().run()
        self.app.radio(key="workspace").set_value("Event Generator").run()
        self.app.text_input(key="filter_Regular Season").set_value("Minutes Restriction").run()
        self.app.button(key="gen_Regular Season").click().run()
        self.assertEqual(self.app.session_state.editing_note_id, "current")
        self.assertEqual(self.app.text_input(key="note_title").value, "Current storyline")
        self.assertEqual(deepcopy(self.cloud.document_data), before)

    def test_tracking_draw_preserves_draft_season_selection(self):
        self.app.selectbox(key="note_season").set_value(2028).run()
        self.app.text_input(key="filter_Regular Season").set_value("Minutes Restriction").run()
        self.app.button(key="gen_Regular Season").click().run()
        self.assertEqual(self.app.selectbox(key="note_season").value, 2028)
        self.assertEqual(self.app.text_input(key="note_title").value, "")

    def test_external_note_changes_are_not_overwritten_by_stale_draft(self):
        store = NotepadStore(self.cloud)
        store.save(save_note(store.load(), title="Another session's note", season=2026))
        self.app.text_input(key="note_title").set_value("My draft")
        self.app.button(key="save_note").click().run()
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.text_input(key="note_title").value, "My draft")
        self.app.button(key="save_note").click().run()
        titles = [note["title"] for note in deepcopy(self.cloud.document_data)["items"]]
        self.assertIn("Another session's note", titles)
        self.assertIn("My draft", titles)

    def test_flagged_events_are_opt_in_and_next_season_note_is_prefilled(self):
        self.add_review_fixture()
        self.app.button(key="phase_btn_Free Agency").click().run()
        self.app.text_input(key="filter_Free Agency").set_value("Review fixture").run()
        self.app.button(key="gen_Free Agency").click().run()
        self.assertIsNone(self.app.session_state.last_event)
        self.app.toggle(key="include_review_events").set_value(True).run()
        self.app.button(key="gen_Free Agency").click().run()
        self.assertTrue(self.app.session_state.last_event["needs_review"])
        self.app.button(key="use_event_in_note").click().run()
        self.assertEqual(self.app.selectbox(key="note_season").value, 2027)
        self.assertIn("Effect: Check the selected player next season.", self.app.text_area(key="note_details").value)

    def test_review_workspace_lists_questions_and_does_not_change_notes(self):
        self.add_review_fixture()
        before = deepcopy(self.cloud.document_data)
        self.app.radio(key="workspace").set_value("Event Review").run()
        self.app.text_input(key="review_search").set_value("Review fixture").run()
        self.assertTrue(any("Choose an eligible player." in warning.value for warning in self.app.warning))
        self.assertFalse(self.app.exception)
        self.assertEqual(deepcopy(self.cloud.document_data), before)

    def test_requested_rolls_are_saved_in_the_correct_season(self):
        for phase, title, value, bounds, season, outcome in (
            ("Summer League", "Hustle Guy", 1, (1, 10), 2026, None),
            ("Summer League", "Hustle Guy", 10, (1, 10), 2026, None),
            ("Free Agency", "Trip to Europe", 1, (1, 2), 2027, "+3 OVR"),
            ("Free Agency", "Trip to Europe", 2, (1, 2), 2027, "−3 OVR"),
        ):
            with self.subTest(title=title, value=value):
                self.app.button(key=f"phase_btn_{phase}").click().run()
                self.app.text_input(key=f"filter_{phase}").set_value(title).run()
                with patch("event_engine.random.randint", return_value=value) as draw:
                    self.app.button(key=f"gen_{phase}").click().run()
                draw.assert_called_once_with(*bounds)
                self.assertFalse(self.app.exception)
                event = self.app.session_state.last_event
                self.assertEqual(event["title"], title)
                self.assertIsNone(event["player"], "Do not add a second, conflicting roster roll")
                if title == "Hustle Guy":
                    self.assertEqual(self.app.text_input(key="note_title").value, "")
                    self.app.button(key="use_event_in_note").click().run()
                else:
                    self.assertEqual(self.app.text_input(key="note_title").value, title)
                self.assertEqual(self.app.selectbox(key="note_season").value, season)
                self.app.button(key="save_note").click().run()
                note = deepcopy(self.cloud.document_data)["items"][0]
                self.assertEqual(note["season"], season)
                self.assertIn(f'Team: {event["team"]}', note["details"])
                if outcome:
                    self.assertIn(outcome, event["event_roll"]["outcome"])
                    self.assertIn(outcome, note["details"])
                    self.assertIn("Player: [enter player name]", note["details"])
                    self.assertNotIn(event["effect"], note["details"])
                else:
                    self.assertIn(f"Player: #{value} (summer league player rank)", note["details"])
                    self.assertIn("by 5", note["details"])

    def test_event_note_keeps_roll_and_warns_at_rollover(self):
        self.app.text_input(key="filter_Regular Season").set_value("Minutes Restriction").run()
        self.app.button(key="gen_Regular Season").click().run()
        self.app.button(key="use_event_in_note").click().run()
        self.assertIn("Minutes cap:", self.app.text_area(key="note_details").value)
        self.app.button(key="save_note").click().run()
        saved = deepcopy(self.cloud.document_data)["items"][0]
        self.assertTrue(saved["resolve_before_rollover"])
        self.assertEqual(saved["source_event_id"], "regular-season--minutes-restriction")
        self.app.button(key="phase_btn_Playoffs").click().run()
        self.app.button(key="prepare_next_season").click().run()
        self.assertTrue(any("restore" in info.value.lower() for info in self.app.info))


if __name__ == "__main__":
    unittest.main()
