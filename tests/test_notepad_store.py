import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from notepad_store import NotepadStore, NotepadStorageError
from season_notebook import advance_season, normalize_notebook


class NotepadStoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "notes.json"

    def test_legacy_file_is_not_written_until_user_saves(self):
        legacy = '[{"id": 1, "title": "Old note"}]'
        self.path.write_text(legacy)
        store = NotepadStore(self.path, initial_season=2026)
        state = store.load()
        self.assertEqual(self.path.read_text(), legacy)
        store.save(state)
        self.assertEqual(store.load()["items"][0]["season"], 2026)

    def test_rollover_survives_a_new_store_and_never_revives_deleted_notes(self):
        state = normalize_notebook({"current_season": 1, "items": [
            {"id": "old", "season": 1}, {"id": "next", "season": 2}]})
        NotepadStore(self.path).save(advance_season(state))
        loaded = NotepadStore(self.path).load()
        self.assertEqual(loaded["current_season"], 2)
        self.assertEqual([n["id"] for n in loaded["items"]], ["next"])

    def test_failed_atomic_write_preserves_original_file(self):
        store = NotepadStore(self.path)
        saved = store.save(normalize_notebook([]))
        before = self.path.read_bytes()
        with patch("pathlib.Path.replace", side_effect=OSError("disk full")):
            with self.assertRaises(NotepadStorageError):
                store.save(advance_season(saved))
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_cloud_fallback_is_not_replaced_by_stale_cloud_on_recovery(self):
        cloud = Mock()
        cloud.get.return_value.exists = True
        cloud.get.return_value.to_dict.return_value = {"items": [], "current_season": 1, "updated_at": "2026-01-01T00:00:00+00:00"}
        cloud.set.side_effect = OSError("offline")
        store = NotepadStore(self.path, cloud)
        store.save(advance_season(store.load()))
        self.assertEqual(store.backend, "Local JSON")
        loaded = NotepadStore(self.path, cloud).load()
        self.assertEqual(loaded["current_season"], 2)
        cloud.set.side_effect = None
        store.save(loaded)
        self.assertEqual(cloud.set.call_args.args[0]["current_season"], 2)

    def test_cloud_receives_season_and_notes_in_one_write(self):
        cloud = Mock()
        store = NotepadStore(self.path, cloud)
        state = normalize_notebook({"current_season": 3, "items": [{"id": "X", "season": 4}]})
        store.save(state)
        self.assertEqual(cloud.set.call_count, 1)
        document = cloud.set.call_args.args[0]
        self.assertEqual(document["current_season"], 3)
        self.assertEqual(document["items"][0]["season"], 4)

    def test_invalid_local_data_reports_error_without_overwriting(self):
        self.path.write_text("broken json")
        with self.assertRaises(NotepadStorageError):
            NotepadStore(self.path).load()
        self.assertEqual(self.path.read_text(), "broken json")

    def test_newer_cloud_copy_wins_over_local_cache(self):
        self.path.write_text(json.dumps({"items": [], "current_season": 1, "updated_at": "2026-01-01T00:00:00Z"}))
        cloud = Mock()
        cloud.get.return_value.exists = True
        cloud.get.return_value.to_dict.return_value = {"items": [], "current_season": 2, "updated_at": "2026-02-01T00:00:00Z"}
        self.assertEqual(NotepadStore(self.path, cloud).load()["current_season"], 2)


if __name__ == "__main__":
    unittest.main()
