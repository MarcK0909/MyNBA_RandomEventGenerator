import unittest
from copy import deepcopy
from unittest.mock import Mock, patch

from notepad_store import NotepadStore, NotepadStorageError
from season_notebook import advance_season, normalize_notebook, save_note, delete_note, set_note_done


def fake_firestore(document=None):
    cloud = Mock()
    cloud.document_data = deepcopy(document)

    def get():
        snapshot = Mock()
        snapshot.exists = cloud.document_data is not None
        snapshot.to_dict.return_value = deepcopy(cloud.document_data)
        return snapshot

    def set_document(value, merge=False):
        cloud.document_data = {**(cloud.document_data or {}), **deepcopy(value)} if merge else deepcopy(value)

    cloud.get.side_effect = get
    cloud.set.side_effect = set_document
    return cloud


class NotepadStoreTests(unittest.TestCase):
    def test_missing_configuration_rejects_reads_and_writes(self):
        store = NotepadStore()
        with self.assertRaisesRegex(NotepadStorageError, 'not configured'):
            store.load()
        with self.assertRaisesRegex(NotepadStorageError, 'not configured'):
            store.save({})

    def test_missing_document_initializes_without_writing(self):
        cloud = fake_firestore()
        state = NotepadStore(cloud, initial_season=2027).load()
        self.assertEqual(state['current_season'], 2027)
        self.assertEqual(state['items'], [])
        cloud.set.assert_not_called()

    def test_complete_note_lifecycle_survives_reload(self):
        cloud = fake_firestore()
        store = NotepadStore(cloud)
        saved = store.save(save_note(store.load(), title='Test', season=2026))
        note_id = saved['items'][0]['id']
        self.assertEqual(NotepadStore(cloud).load(), saved)
        store.save(save_note(saved, title='Edited', note_id=note_id, season=2026))
        self.assertEqual(store.load()['items'][0]['title'], 'Edited')
        store.save(set_note_done(store.load(), note_id, True))
        self.assertTrue(store.load()['items'][0]['done'])
        store.save(set_note_done(store.load(), note_id, False))
        self.assertFalse(store.load()['items'][0]['done'])
        store.save(delete_note(store.load(), note_id))
        self.assertEqual(NotepadStore(cloud).load()['items'], [])

    def test_rollover_writes_season_and_notes_together(self):
        cloud = fake_firestore({'current_season': 2026, 'items': [
            {'id': 'old', 'season': 2026}, {'id': 'next', 'season': 2027}]})
        store = NotepadStore(cloud)
        saved = store.save(advance_season(store.load()))
        cloud.set.assert_called_once_with(saved, merge=True)
        self.assertEqual(NotepadStore(cloud).load()['current_season'], 2027)
        self.assertEqual([n['id'] for n in store.load()['items']], ['next'])

    def test_failed_read_does_not_create_empty_notebook(self):
        cloud = fake_firestore()
        cloud.get.side_effect = PermissionError('denied')
        with self.assertRaises(NotepadStorageError):
            NotepadStore(cloud).load()
        cloud.set.assert_not_called()

    def test_failed_write_preserves_input_and_reports_failure(self):
        cloud = fake_firestore({'current_season': 2026, 'items': []})
        store = NotepadStore(cloud)
        state = store.load()
        before = deepcopy(state)
        cloud.set.side_effect = OSError('offline')
        with self.assertRaises(NotepadStorageError):
            store.save(state)
        self.assertEqual(state, before)
        self.assertEqual(store.load(), before)

    def test_invalid_cloud_data_reports_error_without_overwriting(self):
        cloud = fake_firestore({'items': 'invalid'})
        with self.assertRaises(NotepadStorageError):
            NotepadStore(cloud).load()
        cloud.set.assert_not_called()

    def test_no_filesystem_access_on_load_or_save(self):
        cloud = fake_firestore()
        with patch('builtins.open', side_effect=AssertionError('Local storage used')), patch('pathlib.Path.read_text', side_effect=AssertionError('Local storage used')), patch('pathlib.Path.write_text', side_effect=AssertionError('Local storage used')):
            store = NotepadStore(cloud)
            store.save(store.load())
        self.assertEqual(store.backend, 'Firestore')

    def test_legacy_notes_normalize_without_writing(self):
        cloud = fake_firestore({'items': [{'id': 'legacy', 'title': 'Old note'}]})
        self.assertEqual(NotepadStore(cloud).load()['items'][0]['season'], 2026)
        cloud.set.assert_not_called()


if __name__ == '__main__':
    unittest.main()
