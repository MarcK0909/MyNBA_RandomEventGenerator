from typing import Any

from constants import VALID_INTENSITIES


ALLOWED_ROLL_TYPES = {"range"}


def _is_non_empty_str(value):
    return isinstance(value, str) and value.strip() != ""


def validate_events_schema(events_data: Any):
    if not isinstance(events_data, dict):
        raise ValueError("events.json root must be an object mapping phase -> events list")

    event_ids = set()
    for phase, events in events_data.items():
        if not _is_non_empty_str(phase):
            raise ValueError("All phase names must be non-empty strings")

        if not isinstance(events, list):
            raise ValueError(f"Phase '{phase}' must contain a list of events")

        for idx, event in enumerate(events):
            context = f"phase '{phase}', event index {idx}"

            if not isinstance(event, dict):
                raise ValueError(f"{context}: event must be an object")

            title = event.get("title")
            effect = event.get("effect")
            if not _is_non_empty_str(title):
                raise ValueError(f"{context}: 'title' is required and must be a non-empty string")
            if not _is_non_empty_str(effect):
                raise ValueError(f"{context}: 'effect' is required and must be a non-empty string")

            impact = event.get("impact")
            if impact is not None and impact not in VALID_INTENSITIES:
                raise ValueError(
                    f"{context}: invalid 'impact' value '{impact}'. "
                    f"Allowed: {sorted(VALID_INTENSITIES)}"
                )

            for bool_field in ("requires_team", "requires_player", "needs_review", "resolve_before_rollover"):
                field_value = event.get(bool_field)
                if field_value is not None and not isinstance(field_value, bool):
                    raise ValueError(f"{context}: '{bool_field}' must be boolean when provided")

            event_id = event.get("id")
            if event_id is not None:
                if not _is_non_empty_str(event_id) or event_id in event_ids:
                    raise ValueError(f"{context}: event id must be non-empty and unique")
                event_ids.add(event_id)
            for field in ("duration", "target", "tracking", "roll_purpose", "original_effect", "review_suggestion"):
                if field in event and not _is_non_empty_str(event[field]):
                    raise ValueError(f"{context}: '{field}' must be a non-empty string")
            notes = event.get("review_notes", [])
            if not isinstance(notes, list) or any(not _is_non_empty_str(note) for note in notes):
                raise ValueError(f"{context}: review_notes must be a list of non-empty strings")
            if event.get("needs_review") and not notes:
                raise ValueError(f"{context}: a flagged event needs review_notes explaining the decision")
            offset = event.get("note_season_offset", 0)
            if type(offset) is not int or offset < 0:
                raise ValueError(f"{context}: note_season_offset must be a nonnegative integer")

            roll_type = event.get("roll_type")
            roll_min = event.get("roll_min")
            roll_max = event.get("roll_max")

            if roll_type is not None and roll_type not in ALLOWED_ROLL_TYPES:
                raise ValueError(
                    f"{context}: invalid 'roll_type' value '{roll_type}'. "
                    f"Allowed: {sorted(ALLOWED_ROLL_TYPES)}"
                )

            has_roll_bounds = roll_min is not None or roll_max is not None
            if has_roll_bounds and roll_type != "range":
                raise ValueError(
                    f"{context}: 'roll_min'/'roll_max' require 'roll_type' set to 'range'"
                )

            if roll_type == "range":
                if type(roll_min) is not int or type(roll_max) is not int:
                    raise ValueError(
                        f"{context}: 'roll_type=range' requires integer 'roll_min' and 'roll_max'"
                    )
                if roll_min == roll_max:
                    raise ValueError(f"{context}: 'roll_min' and 'roll_max' cannot be equal")

            if "roll_purpose" in event and roll_type != "range":
                raise ValueError(f"{context}: roll_purpose requires a range roll")
            if "roll_outcomes" in event:
                outcomes = event["roll_outcomes"]
                if roll_type != "range" or not isinstance(outcomes, list) or not outcomes:
                    raise ValueError(f"{context}: roll_outcomes requires a non-empty list and a range roll")
                expected = min(roll_min, roll_max)
                if any(not isinstance(outcome, dict) or type(outcome.get("min")) is not int
                       or type(outcome.get("max")) is not int or not _is_non_empty_str(outcome.get("label"))
                       for outcome in outcomes):
                    raise ValueError(f"{context}: invalid roll outcome")
                for outcome in sorted(outcomes, key=lambda item: item["min"]):
                    if outcome["min"] != expected or outcome["max"] < outcome["min"]:
                        raise ValueError(f"{context}: roll outcomes must cover the range without gaps or overlap")
                    expected = outcome["max"] + 1
                if expected != max(roll_min, roll_max) + 1:
                    raise ValueError(f"{context}: roll outcomes must cover the entire roll range")
