"""Opt-in integration test: MYNBA_TEST_FIRESTORE=1 python -m unittest discover -s tests -p test_firestore_live.py.

Uses configured credentials and a unique temporary document in the configured
collection. Never writes to the user's notebook. Deletes the test document.
"""
import os
from pathlib import Path
import tomllib
import unittest
from uuid import uuid4

from notepad_store import NotepadStore
from season_notebook import advance_season, delete_note, save_note, set_note_done


@unittest.skipUnless(os.environ.get('MYNBA_TEST_FIRESTORE') == '1', 'Live Firestore test is opt-in')
class FirestoreLiveTests(unittest.TestCase):
    def test_live_notebook_lifecycle(self):
        import firebase_admin
        from firebase_admin import credentials, firestore

        secrets = tomllib.loads((Path(__file__).resolve().parents[1] / '.streamlit/secrets.toml').read_text())
        app = firebase_admin.initialize_app(credentials.Certificate(dict(secrets['firebase'])), name='notebook-test-' + uuid4().hex)
        self.addCleanup(firebase_admin.delete_app, app)
        db = firestore.client(app)
        self.addCleanup(db.close)
        collection = db.collection(secrets.get('firestore_collection', 'mynba'))
        # Read the real document to verify access, without modifying it.
        actual = collection.document(secrets.get('firestore_document', 'event_notepad')).get(timeout=20)
        if actual.exists:
            from season_notebook import normalize_notebook
            normalize_notebook(actual.to_dict())
        ref = collection.document('notebook-integration-test-' + uuid4().hex)
        self.addCleanup(lambda: ref.delete(timeout=20))
        store = NotepadStore(ref)
        self.assertEqual(store.load()['items'], [])
        saved = store.save(save_note(store.load(), title='Integration test', season=2026))
        self.assertEqual(NotepadStore(ref).load(), saved)
        note_id = saved['items'][0]['id']
        store.save(save_note(saved, title='Edited integration test', season=2026, note_id=note_id))
        self.assertEqual(store.load()['items'][0]['title'], 'Edited integration test')
        store.save(set_note_done(store.load(), note_id, True))
        self.assertTrue(store.load()['items'][0]['done'])
        store.save(set_note_done(store.load(), note_id, False))
        self.assertFalse(store.load()['items'][0]['done'])
        store.save(delete_note(store.load(), note_id))
        self.assertEqual(store.load()['items'], [])
        saved = store.save(save_note(store.load(), title='Future note', season=2027))
        store.save(save_note(saved, title='Departing note', season=2026))
        store.save(advance_season(store.load()))
        loaded = NotepadStore(ref).load()
        self.assertEqual(loaded['current_season'], 2027)
        self.assertEqual([item['title'] for item in loaded['items']], ['Future note'])
        ref.delete(timeout=20)
        self.assertFalse(ref.get(timeout=20).exists)
