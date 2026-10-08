import json
import random
import re
from collections import defaultdict

from constants import VALID_INTENSITIES
from event_schema import validate_events_schema


def load_events(path: str = "events.json") -> dict:
    with open(path, "r") as f:
        events = json.load(f)

    validate_events_schema(events)
    return events


def infer_intensity(event: dict) -> str:
    text = f"{event.get('title', '')} {event.get('effect', '')}".lower()

    high_markers = [
        "trade", "fire coach", "suspend", "90 days", "severe injury",
        "out 30 days", "force loss", "force win", "decline", "decrease all"
    ]
    high_markers += [
        "forced to retire", "entire season", "100–200 days", "100-200 days",
        "must be traded", "superstar trade demand", "fire gm and head coach",
        "set all attributes to 25", "tear", "acl", "350 days"
    ]
    medium_markers = [
        "one week", "5 games", "minutes restriction", "offensive consistency",
        "defensive consistency", "potential by 5", "durability"
    ]

    if any(marker in text for marker in high_markers):
        return "High Impact"
    if any(marker in text for marker in medium_markers):
        return "Medium Impact"
    return "Low Impact"


def get_event_intensity(event: dict) -> str:
    impact = event.get("impact")
    if isinstance(impact, str) and impact in VALID_INTENSITIES:
        return impact
    return infer_intensity(event)


def weighted_random_event(events: list, weight_map: dict, recent_titles: set) -> dict:
    """Keep each available tier's probability independent of its pool size.

    Recent events are penalized within their tier without distorting the
    selected tier split. Missing/disabled tiers are excluded and the remaining
    weights are renormalized by random.choices.
    """
    if not events:
        raise ValueError("No eligible events are available.")
    groups = defaultdict(list)
    for event in events:
        intensity = get_event_intensity(event)
        tier_weight = max(weight_map.get(intensity, 0), 0.0)
        if tier_weight > 0:
            recent = event.get("id", event.get("title")) in recent_titles or event.get("title") in recent_titles
            groups[intensity].append((event, 0.35 if recent else 1.0))
    weighted_pool, weights = [], []
    for intensity, members in groups.items():
        denominator = sum(factor for _, factor in members)
        for event, factor in members:
            weighted_pool.append(event)
            weights.append(weight_map[intensity] * factor / denominator)
    if not weighted_pool:
        return random.choice(events)
    return random.choices(weighted_pool, weights=weights, k=1)[0]


def extract_draw_range(effect_text: str):
    if not effect_text:
        return None

    match = re.search(r"draw\s+a\s+number\s+between\s+(\d+)\s*(?:and|-)\s*(\d+)", effect_text, re.IGNORECASE)
    if not match:
        return None

    start = int(match.group(1))
    end = int(match.group(2))
    if start > end:
        start, end = end, start
    return (start, end)


def _roll_payload(start: int, end: int):
    value = random.randint(start, end)
    return {
        "value": value,
        "start": start,
        "end": end,
        "label": f"{start}-{end}"
    }


def generate_event_number(event: dict):
    roll_type = event.get("roll_type")
    if roll_type == "range":
        roll_min = event.get("roll_min")
        roll_max = event.get("roll_max")
        if isinstance(roll_min, int) and isinstance(roll_max, int):
            start, end = (roll_min, roll_max) if roll_min <= roll_max else (roll_max, roll_min)
            roll = _roll_payload(start, end)
            roll["purpose"] = event.get("roll_purpose", "Random number draw")
            for outcome in event.get("roll_outcomes", []):
                if outcome["min"] <= roll["value"] <= outcome["max"]:
                    roll["outcome"] = outcome["label"]
                    break
            return roll

    effect_text = event.get("effect", "")
    range_tuple = extract_draw_range(effect_text)
    if not range_tuple:
        return None

    start, end = range_tuple
    return _roll_payload(start, end)


def requires_team_draw(event: dict) -> bool:
    requires_team = event.get("requires_team")
    if isinstance(requires_team, bool):
        return requires_team

    effect_text = event.get("effect", "")
    return "team drawn" in effect_text.lower()


def requires_player_draw(event: dict) -> bool:
    requires_player = event.get("requires_player")
    if isinstance(requires_player, bool):
        return requires_player

    effect_text = event.get("effect", "")
    return "player drawn" in effect_text.lower()


def build_event_note(event: dict, current_season: int) -> dict:
    """Prepare a traceable follow-up without translating game time to real dates."""
    lines = [event.get("effect", "")]
    targets = [str(event[key]) for key in ("team", "team_2", "player") if event.get(key)]
    if targets:
        lines.append("Context: " + " · ".join(targets))
    for field, label in (("target", "Eligible target"), ("duration", "Duration"), ("tracking", "Follow-up")):
        if event.get(field):
            lines.append(f"{label}: {event[field]}")
    roll = event.get("event_roll")
    if roll:
        result = f'{roll.get("purpose", "Random draw")}: {roll["value"]} (range {roll["label"]})'
        if roll.get("outcome"):
            result += f' — {roll["outcome"]}'
        lines.append(result)
    if event.get("needs_review"):
        lines.append("NEEDS YOUR REVIEW BEFORE APPLYING:\n" + "\n".join(event.get("review_notes", [])))
    return {
        "title": event.get("title", "Generated event"),
        "details": "\n\n".join(lines),
        "season": current_season + event.get("note_season_offset", 0),
        "phase": "Any" if event.get("note_season_offset", 0) else event.get("phase", "Any"),
        "source_event_id": event.get("id"),
        "resolve_before_rollover": bool(event.get("resolve_before_rollover", False)),
    }
