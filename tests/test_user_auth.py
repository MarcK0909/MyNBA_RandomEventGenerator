"""Simulate Google's verified callback claims; never automate Google passwords."""

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from streamlit.testing.v1 import AppTest
from user_auth import GOOGLE_METADATA_URL, google_user_id
from firestore_connection import user_notebook_ref
from test_notepad_store import fake_firestore

ROOT = Path(__file__).resolve().parents[1]


def identity(subject, email="player@example.com"):
    return {"is_logged_in": True, "iss": "https://accounts.google.com", "sub": subject,
            "email": email, "name": "Test Player"}


class IdentityTests(unittest.TestCase):
    def test_id_stays_with_account_when_email_changes(self):
        self.assertEqual(google_user_id(identity('alice')), google_user_id(identity('alice', 'new@example.com')))
        self.assertNotEqual(google_user_id(identity('alice')), google_user_id(identity('bob')))
        self.assertEqual(google_user_id(identity('alice')), google_user_id({**identity('alice'), 'iss': 'accounts.google.com'}))

    def test_invalid_or_unsigned_identity_is_rejected(self):
        for user in ({}, {'is_logged_in': False}, {**identity('alice'), 'iss': 'https://evil.example'},
                     {**identity('alice'), 'sub': ''}, {**identity('alice'), 'sub': None}):
            with self.subTest(user=user), self.assertRaises(ValueError):
                google_user_id(user)

    def test_document_path_rejects_arbitrary_ids(self):
        db = Mock()
        for user_id in ('', 'alice', 'users/alice', None):
            with self.subTest(user_id=user_id), self.assertRaises(ValueError):
                user_notebook_ref(db, user_id)
        db.collection.assert_not_called()


class GoogleNotebookFlowTests(unittest.TestCase):
    def setUp(self):
        self.documents = {}
        self.db = Mock()
        self.db.collection.side_effect = self.collection
        client = patch('firestore_connection.get_firestore_client', return_value=self.db)
        self.get_client = client.start()
        self.addCleanup(client.stop)

    def collection(self, name):
        collection = Mock()
        def document(user_id):
            key = (name, user_id)
            if key not in self.documents:
                self.documents[key] = fake_firestore()
            return self.documents[key]
        collection.document.side_effect = document
        return collection

    def new_app(self, user=None):
        app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
        app.user = user or {'is_logged_in': False}
        app.secrets['auth'] = {
            'redirect_uri': 'http://localhost:8501/oauth2callback', 'cookie_secret': 'test-only-cookie-secret',
            'client_id': 'test-only-client-id', 'client_secret': 'test-only-client-secret',
            'server_metadata_url': GOOGLE_METADATA_URL,
        }
        app.run()
        self.assertFalse(app.exception)
        return app

    def document_for(self, subject):
        return self.documents[('user_notebooks', google_user_id(identity(subject)))]

    def test_google_sign_in_draw_save_reload_and_second_user_isolation(self):
        app = self.new_app()
        self.get_client.assert_not_called()
        self.assertNotIn('save_note', [button.key for button in app.button])
        with patch('streamlit.login') as login:
            # Re-render so on_click registers the patched framework method.
            app.run()
            app.button(key='google_sign_in').click().run()
            login.assert_called_once_with()
        self.get_client.assert_not_called()
        # Simulate the verified identity returned by the Google OIDC callback.
        app.user = identity('alice')
        app.run()
        app.text_input(key='filter_Regular Season').set_value('Minutes Restriction').run()
        app.button(key='gen_Regular Season').click().run()
        app.button(key='save_note').click().run()
        self.assertFalse(app.exception)
        saved = deepcopy(self.document_for('alice').document_data)
        self.assertEqual(saved['items'][0]['title'], 'Minutes Restriction')
        self.assertIn('Minutes cap:', saved['items'][0]['details'])
        self.assertEqual(self.new_app(identity('alice')).session_state.notebook, saved)
        bob = self.new_app(identity('bob'))
        self.assertEqual(bob.session_state.notebook['items'], [])
        bob.text_input(key='note_title').set_value("Bob's note")
        bob.button(key='save_note').click().run()
        self.assertEqual(self.document_for('bob').document_data['items'][0]['title'], "Bob's note")
        self.assertEqual(self.document_for('alice').document_data, saved)
        bob.radio(key='workspace').set_value('Notepad').run()
        note_id = self.document_for('bob').document_data['items'][0]['id']
        bob.button(key=f'delete_{note_id}').click().run()
        self.assertEqual(self.document_for('bob').document_data['items'], [])
        self.assertEqual(self.document_for('alice').document_data, saved)

    def test_account_switch_discards_draft_and_rejects_stale_save_callback(self):
        app = self.new_app(identity('alice'))
        app.text_input(key='note_title').set_value('Alice private draft').run()
        app.user = identity('bob')
        app.button(key='save_note').click().run()
        self.assertFalse(app.exception)
        self.document_for('alice').set.assert_not_called()
        self.document_for('bob').set.assert_not_called()
        self.assertEqual(app.text_input(key='note_title').value, '')
        self.assertEqual(app.session_state.notebook_user_id, google_user_id(identity('bob')))

    def test_logout_removes_private_ui_and_prevents_signed_out_save(self):
        app = self.new_app(identity('alice'))
        app.text_input(key='note_title').set_value('Unsaved private note').run()
        with patch('streamlit.logout') as logout:
            app.button(key='sign_out').click().run()
            logout.assert_called_once_with()
        app.user = {'is_logged_in': False}
        self.get_client.reset_mock()
        app.run()
        self.get_client.assert_not_called()
        self.assertNotIn('save_note', [button.key for button in app.button])
        self.assertNotIn('notebook', app.session_state)
        self.document_for('alice').set.assert_not_called()

    def test_signed_out_stale_save_and_forged_query_id_cannot_access_notes(self):
        app = self.new_app(identity('alice'))
        app.text_input(key='note_title').set_value('Should never save').run()
        app.user = {'is_logged_in': False}
        app.query_params['user_id'] = google_user_id(identity('alice'))
        self.get_client.reset_mock()
        app.button(key='save_note').click().run()
        self.assertFalse(app.exception)
        self.get_client.assert_not_called()
        self.document_for('alice').set.assert_not_called()

    def test_missing_configuration_or_invalid_claims_never_access_database(self):
        for user in ({'is_logged_in': False}, {**identity('alice'), 'sub': ''}, {**identity('alice'), 'iss': 'https://evil.example'}):
            app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20)
            app.user = user
            app.secrets['auth'] = {}
            app.run()
            self.assertFalse(app.exception)
            self.assertNotIn('save_note', [button.key for button in app.button])
        self.get_client.assert_not_called()
