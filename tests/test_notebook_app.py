"""Exercise note editing and season rollover without touching real user data."""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from notepad_store import NotepadStore
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
        self.path = Path("event_notepad.json")
        self.path.write_text(json.dumps({"current_season": 2026, "items": [
            {"id": "current", "title": "Current storyline", "details": "Rookie minutes", "season": 2026, "done": False},
            {"id": "finished", "title": "Finished storyline", "season": 2026, "done": True},
            {"id": "future", "title": "Next year only", "season": 2027, "done": False},
            {"id": "later", "title": "Much later", "season": 2028, "done": False},
        ]}))
        self.app = self.new_app()

    def new_app(self):
        app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)
        app.secrets["firebase"] = {}
        app.run()
        self.assertFalse(app.exception)
        return app

    def open_notebook(self):
        self.app.radio(key="workspace").set_value("Notepad").run()

    def test_schedule_note_is_hidden_until_its_season(self):
        self.open_notebook()
        self.assertEqual(self.app.selectbox(key="note_season").value, 2026)
        self.app.text_input(key="note_title").set_value("A scheduled note")
        self.app.selectbox(key="note_season").set_value(2027)
        self.app.button(key="FormSubmitter:note_editor-Save note").click().run()
        saved = json.loads(self.path.read_text())
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
        self.app.button(key="FormSubmitter:note_editor-Save changes").click().run()
        self.app.button(key="done_current").click().run()
        self.assertEqual(self.app.radio(key="workspace").value, "Notepad")
        self.app.selectbox(key="note_status").set_value("Completed").run()
        self.app.button(key="done_current").click().run()
        self.app.selectbox(key="note_status").set_value("Open notes").run()
        self.app.button(key="delete_current").click().run()
        self.assertFalse(self.app.exception)
        self.assertNotIn("current", [note["id"] for note in json.loads(self.path.read_text())["items"]])

    def test_confirmed_rollover_deletes_departing_notes_and_survives_reload(self):
        self.app.button(key="phase_btn_Playoffs").click().run()
        self.app.button(key="prepare_next_season").click().run()
        self.assertEqual(json.loads(self.path.read_text())["current_season"], 2026)
        self.app.button(key="confirm_next_season_button").click().run()
        self.assertFalse(self.app.exception)
        saved = json.loads(self.path.read_text())
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
        before = self.path.read_bytes()
        with patch("notepad_store.NotepadStore._write_local", side_effect=OSError("disk full")):
            self.app.button(key="confirm_next_season_button").click().run()
        self.assertFalse(self.app.exception)
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.session_state.notebook["current_season"], 2026)
        self.assertEqual(self.path.read_bytes(), before)

    def test_event_draw_does_not_replace_draft(self):
        self.app.text_input(key="note_title").set_value("My unsaved idea").run()
        self.app.button(key="gen_Regular Season").click().run()
        self.assertEqual(self.app.text_input(key="note_title").value, "My unsaved idea")
        self.app.button(key="use_event_in_note").click().run()
        self.assertEqual(self.app.text_input(key="note_title").value, self.app.session_state.last_event["title"])

    def test_stale_browser_cannot_restore_notes_after_another_session_advances(self):
        self.open_notebook()
        store = NotepadStore(self.path)
        store.save(advance_season(store.load()))
        self.app.button(key="done_current").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.session_state.notebook["current_season"], 2027)
        self.assertFalse(self.app.session_state.confirm_next_season)
        saved = json.loads(self.path.read_text())
        self.assertNotIn("current", [note["id"] for note in saved["items"]])

    def test_external_note_changes_are_not_overwritten_by_stale_draft(self):
        store = NotepadStore(self.path)
        store.save(save_note(store.load(), title="Another session's note", season=2026))
        self.app.text_input(key="note_title").set_value("My draft")
        self.app.button(key="FormSubmitter:note_editor-Save note").click().run()
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.text_input(key="note_title").value, "My draft")
        self.app.button(key="FormSubmitter:note_editor-Save note").click().run()
        titles = [note["title"] for note in json.loads(self.path.read_text())["items"]]
        self.assertIn("Another session's note", titles)
        self.assertIn("My draft", titles)


if __name__ == "__main__":
    unittest.main()
