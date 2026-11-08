"""Opt-in integration test: MYNBA_TEST_FIRESTORE=1 python -m unittest discover -s tests -p test_firestore_live.py.

Uses configured credentials and temporary legacy/per-user documents.
Never writes to an existing user's notebook. Deletes all test documents.
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
    def setUp(self):
        import firebase_admin
        from firebase_admin import credentials, firestore

        secrets = tomllib.loads((Path(__file__).resolve().parents[1] / '.streamlit/secrets.toml').read_text())
        app = firebase_admin.initialize_app(credentials.Certificate(dict(secrets['firebase'])), name='notebook-test-' + uuid4().hex)
        self.addCleanup(firebase_admin.delete_app, app)
        db = firestore.client(app)
        self.addCleanup(db.close)
        self.db = db

    def test_live_notebook_lifecycle(self):
        db = self.db
        secrets = tomllib.loads((Path(__file__).resolve().parents[1] / ".streamlit/secrets.toml").read_text())
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

    def test_simulated_google_callback_saves_to_real_isolated_notebooks(self):
        from unittest.mock import patch
        from streamlit.testing.v1 import AppTest
        from user_auth import google_user_id
        from firestore_connection import user_notebook_ref

        root = Path(__file__).resolve().parents[1]
        def claims():
            return {"is_logged_in": True, "iss": "https://accounts.google.com",
                    "sub": "integration-test-" + uuid4().hex, "name": "Integration test"}
        alice, bob = claims(), claims()
        alice_ref = user_notebook_ref(self.db, google_user_id(alice))
        bob_ref = user_notebook_ref(self.db, google_user_id(bob))
        for ref in (alice_ref, bob_ref):
            self.addCleanup(lambda ref=ref: ref.delete(timeout=20))
        with patch("firestore_connection.get_firestore_client", return_value=self.db):
            app = AppTest.from_file(str(root / "app.py"), default_timeout=30)
            app.user = alice
            app.run()
            self.assertFalse(app.exception)
            app.text_input(key="filter_Regular Season").set_value("Minutes Restriction").run()
            app.button(key="gen_Regular Season").click().run()
            app.button(key="save_note").click().run()
            self.assertFalse(app.exception)
            saved = alice_ref.get(timeout=20).to_dict()
            self.assertEqual(saved["items"][0]["title"], "Minutes Restriction")
            app.user = bob
            app.run()
            self.assertEqual(app.session_state.notebook["items"], [])
            app.text_input(key="note_title").set_value("Second user integration test")
            app.button(key="save_note").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(bob_ref.get(timeout=20).to_dict()["items"][0]["title"], "Second user integration test")
            self.assertEqual(alice_ref.get(timeout=20).to_dict(), saved)
            reloaded = AppTest.from_file(str(root / "app.py"), default_timeout=30)
            reloaded.user = alice
            reloaded.run()
            self.assertFalse(reloaded.exception)
            self.assertEqual(reloaded.session_state.notebook, saved)
        for ref in (alice_ref, bob_ref):
            ref.delete(timeout=20)
            self.assertFalse(ref.get(timeout=20).exists)
