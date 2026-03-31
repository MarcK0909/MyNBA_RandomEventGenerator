import json
import random
import re

from constants import VALID_INTENSITIES


def load_events(path: str = "events.json") -> dict:
    with open(path, "r") as f:
        return json.load(f)


def infer_intensity(event: dict) -> str:
    text = f"{event.get('title', '')} {event.get('effect', '')}".lower()

    chaos_markers = [
        "forced to retire", "entire season", "100–200 days", "100-200 days",
        "must be traded", "superstar trade demand", "fire gm and head coach",
        "set all attributes to 25", "tear", "acl", "350 days"
    ]
    high_markers = [
        "trade", "fire coach", "suspend", "90 days", "severe injury",
        "out 30 days", "force loss", "force win", "decline", "decrease all"
    ]
    medium_markers = [
        "one week", "5 games", "minutes restriction", "offensive consistency",
        "defensive consistency", "potential by 5", "durability"
    ]

    if any(marker in text for marker in chaos_markers):
        return "Chaos"
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
    weighted_pool = []
    weights = []

    for event in events:
        intensity = get_event_intensity(event)
        base_weight = max(weight_map.get(intensity, 1), 0.0)
        if base_weight == 0:
            continue

        if event.get("title") in recent_titles:
            base_weight *= 0.35

        weighted_pool.append(event)
        weights.append(base_weight)

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
            return _roll_payload(start, end)

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
