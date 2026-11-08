"""Share the Firestore client, never a user's notebook or document reference."""

import logging
import re
import streamlit as st

logger = logging.getLogger(__name__)


@st.cache_resource
def get_firestore_client():
    try:
        firebase_cfg = st.secrets.get("firebase")
        if not firebase_cfg:
            return None
        import firebase_admin
        from firebase_admin import credentials, firestore
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(credentials.Certificate(dict(firebase_cfg)))
        return firestore.client()
    except Exception as exc:
        logger.warning("Firestore unavailable: %s", type(exc).__name__)
        return None


def user_notebook_ref(db, user_id: str, collection: str = "user_notebooks"):
    """Caller must derive user_id from the authenticated identity server-side."""
    if not isinstance(user_id, str) or not re.fullmatch(r"google_[0-9a-f]{64}", user_id):
        raise ValueError("Invalid notebook owner ID.")
    return db.collection(collection).document(user_id)


def get_firestore_doc_ref(user_id: str):
    db = get_firestore_client()
    if db is None:
        return None
    return user_notebook_ref(db, user_id)
