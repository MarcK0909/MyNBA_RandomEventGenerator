from constants import VALID_INTENSITIES


ALLOWED_ROLL_TYPES = {"range"}


def _is_non_empty_str(value):
    return isinstance(value, str) and value.strip() != ""


def validate_events_schema(events_data: dict):
    if not isinstance(events_data, dict):
        raise ValueError("events.json root must be an object mapping phase -> events list")

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

            for bool_field in ("requires_team", "requires_player"):
                field_value = event.get(bool_field)
                if field_value is not None and not isinstance(field_value, bool):
                    raise ValueError(f"{context}: '{bool_field}' must be boolean when provided")

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
                if not isinstance(roll_min, int) or not isinstance(roll_max, int):
                    raise ValueError(
                        f"{context}: 'roll_type=range' requires integer 'roll_min' and 'roll_max'"
                    )
                if roll_min == roll_max:
                    raise ValueError(f"{context}: 'roll_min' and 'roll_max' cannot be equal")
