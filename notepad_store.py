"""Persist the season and its notes exclusively in Firestore."""

import logging
from datetime import datetime, timezone

from season_notebook import normalize_notebook

logger = logging.getLogger(__name__)


class NotepadStorageError(RuntimeError):
    pass


class NotepadStore:
    def __init__(self, cloud_ref=None, initial_season: int = 2026):
        self.cloud_ref = cloud_ref
        self.initial_season = initial_season
        self.backend = "Firestore"

    def _require_firestore(self):
        if self.cloud_ref is None:
            raise NotepadStorageError(
                "Firestore is not configured or could not initialize. Check your Firebase secrets and connection, then restart the app."
            )

    def load(self) -> dict:
        self._require_firestore()
        try:
            snapshot = self.cloud_ref.get()
            payload = (snapshot.to_dict() or {}) if snapshot.exists else {}
            return normalize_notebook(payload, self.initial_season)
        except Exception as exc:
            logger.warning("Firestore notebook load failed: %s", type(exc).__name__)
            raise NotepadStorageError(
                "Could not load your notebook from Firestore. Check your connection and try again. Your saved notes have not been changed."
            ) from exc

    def save(self, notebook: dict) -> dict:
        self._require_firestore()
        document = {**normalize_notebook(notebook, self.initial_season),
                    "updated_at": datetime.now(timezone.utc).isoformat()}
        try:
            self.cloud_ref.set(document, merge=True)
        except Exception as exc:
            logger.warning("Firestore notebook save failed: %s", type(exc).__name__)
            raise NotepadStorageError(
                "Could not confirm your changes were saved to Firestore. Check your connection and reload before trying again."
            ) from exc
        return document
