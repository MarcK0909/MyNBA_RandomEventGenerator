"""Season-scoped notes, independent of Streamlit and storage."""

from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4


def season_label(season: int) -> str:
    if season >= 1900:
        return f"{season}–{(season + 1) % 100:02d}"
    return f"Season {season}"


def normalize_notebook(payload, initial_season: int = 2026) -> dict:
    """Read both legacy note lists and the versioned notebook document.

    Legacy notes become notes for the initial season. Nothing is deleted
    during loading.
    """
    if isinstance(payload, list):
        payload = {"items": payload}
    if not isinstance(payload, dict):
        raise ValueError("The saved notebook must be an object or a list of notes.")
    current = payload.get("current_season", initial_season)
    if type(current) is not int or current < 1:
        raise ValueError("The saved season must be a positive number.")
    items = payload.get("items", [])
    if not isinstance(items, list):
        raise ValueError("The saved notes must be a list.")
    normalized = []
    ids = set()
    for original in items:
        if not isinstance(original, dict):
            raise ValueError("A saved note has an invalid format.")
        item = deepcopy(original)
        season = item.setdefault("season", current)
        if type(season) is not int or season < 1:
            raise ValueError("A saved note has an invalid season.")
        item_id = str(item.get("id") or uuid4().hex)
        if item_id in ids:
            item_id = uuid4().hex
        ids.add(item_id)
        item["id"] = item_id
        normalized.append(item)
    return {**payload, "schema_version": 2, "current_season": current, "items": normalized}


def active_notes(notebook: dict) -> list[dict]:
    return [item for item in notebook["items"] if item["season"] == notebook["current_season"]]


def scheduled_notes(notebook: dict) -> list[dict]:
    return [item for item in notebook["items"] if item["season"] > notebook["current_season"]]


def save_note(notebook: dict, *, title: str, details: str = "", season: int,
              phase: str = "Any", due: str = "", note_id: str | None = None,
              source_event_id: str | None = None, resolve_before_rollover: bool = False) -> dict:
    title = title.strip()
    if not title:
        raise ValueError("Give your note a title before saving.")
    if type(season) is not int or season < notebook["current_season"]:
        raise ValueError("Choose the current season or a future season.")
    if due:
        from datetime import date
        date.fromisoformat(due)
    result = deepcopy(notebook)
    existing = next((note for note in result["items"] if note["id"] == note_id), None)
    if note_id is not None and existing is None:
        raise ValueError("This note no longer exists. Refresh the notebook.")
    stamp = datetime.now(timezone.utc).isoformat()
    values = {"title": title, "details": details.strip(), "season": season,
              "phase": phase, "due": due, "updated_at": stamp,
              "source_event_id": source_event_id,
              "resolve_before_rollover": bool(resolve_before_rollover)}
    if existing is not None:
        existing.update(values)
    else:
        result["items"].insert(0, {**values, "id": uuid4().hex, "done": False, "created_at": stamp})
    return result


def set_note_done(notebook: dict, note_id: str, done: bool) -> dict:
    result = deepcopy(notebook)
    for item in result["items"]:
        if item["id"] == note_id:
            item["done"] = bool(done)
            return result
    raise ValueError("This note no longer exists. Refresh the notebook.")


def delete_note(notebook: dict, note_id: str) -> dict:
    result = deepcopy(notebook)
    result["items"] = [item for item in result["items"] if item["id"] != note_id]
    return result


def advance_season(notebook: dict) -> dict:
    """Remove the departing season's notes and reveal the next season's notes."""
    result = deepcopy(notebook)
    departing = result["current_season"]
    result["items"] = [item for item in result["items"] if item["season"] != departing]
    result["current_season"] += 1
    return result
