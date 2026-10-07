"""Persist the season and its notes together, with an atomic local fallback."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from season_notebook import normalize_notebook

logger = logging.getLogger(__name__)


class NotepadStorageError(RuntimeError):
    pass


class NotepadStore:
    def __init__(self, path: Path, cloud_ref=None, initial_season: int = 2026):
        self.path = path
        self.cloud_ref = cloud_ref
        self.initial_season = initial_season
        self.backend = "Local JSON"

    def load(self) -> dict:
        candidates = []
        errors = []
        if self.path.exists():
            try:
                candidates.append((normalize_notebook(json.loads(self.path.read_text(encoding="utf-8")), self.initial_season), "Local JSON"))
            except (OSError, ValueError) as exc:
                errors.append(exc)
        if self.cloud_ref is not None:
            try:
                snapshot = self.cloud_ref.get()
                if snapshot.exists:
                    candidates.append((normalize_notebook(snapshot.to_dict() or {}, self.initial_season), "Firestore"))
            except Exception as exc:
                logger.warning("Cloud notebook unavailable: %s", type(exc).__name__)
                errors.append(exc)
        if candidates:
            # A local write during a cloud outage must not be replaced by an older
            # cloud copy when the connection comes back. Prefer cloud on a tie.
            state, self.backend = max(candidates, key=lambda candidate: self._timestamp(candidate[0]))
            if len(candidates) > 1 and self._timestamp(candidates[0][0]) == self._timestamp(candidates[-1][0]):
                state, self.backend = candidates[-1]
            return state
        if errors:
            raise NotepadStorageError("Could not load your saved notebook. Your files have not been changed.") from errors[0]
        self.backend = "Firestore" if self.cloud_ref is not None else "Local JSON"
        return normalize_notebook({}, self.initial_season)

    @staticmethod
    def _timestamp(state: dict) -> float:
        try:
            stamp = datetime.fromisoformat(str(state.get("updated_at", "")))
            return stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).timestamp()
        except ValueError:
            return 0

    def save(self, notebook: dict) -> dict:
        document = {**normalize_notebook(notebook, self.initial_season),
                    "updated_at": datetime.now(timezone.utc).isoformat()}
        cloud_saved = False
        if self.cloud_ref is not None:
            try:
                self.cloud_ref.set(document, merge=True)
                cloud_saved = True
            except Exception as exc:
                logger.warning("Cloud notebook save failed: %s", type(exc).__name__)
        try:
            self._write_local(document)
        except OSError as exc:
            if not cloud_saved:
                raise NotepadStorageError("Your changes could not be saved. The season and notes have not changed; please try again.") from exc
            logger.warning("Local notebook cache unavailable: %s", type(exc).__name__)
        self.backend = "Firestore" if cloud_saved else "Local JSON"
        return document

    def _write_local(self, document: dict) -> None:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                             prefix=f".{self.path.name}.", suffix=".tmp", delete=False) as output:
                temporary_path = Path(output.name)
                json.dump(document, output, indent=2, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            temporary_path.replace(self.path)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
