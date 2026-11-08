"""A small, independent catalog for matches the user plays manually."""

import json
import random
from pathlib import Path


MATCH_MODES = ("Player Lock", "Full Team")


def load_match_events(path=None):
    path = Path(path) if path is not None else Path(__file__).with_name("match_events.json")
    events = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        raise ValueError("Match events must be a list.")
    ids = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Each match event must be an object.")
        for field in ("id", "title", "effect", "duration", "cleanup"):
            if not isinstance(event.get(field), str) or not event[field].strip():
                raise ValueError(f"Match event needs a non-empty {field}.")
        if event["id"] in ids:
            raise ValueError("Match event IDs must be unique.")
        ids.add(event["id"])
        if event.get("scope") not in ("Player", "Team"):
            raise ValueError("Match event scope must be Player or Team.")
        if event.get("player_pool", "roster") not in ("roster", "two_way"):
            raise ValueError("Match player pool must be roster or two_way.")
        modes = event.get("modes")
        if not isinstance(modes, list) or not modes or any(mode not in MATCH_MODES for mode in modes):
            raise ValueError("Match events must specify supported modes.")
        if event["scope"] == "Team" and "Player Lock" in modes:
            raise ValueError("Team-control events cannot be used in Player Lock mode.")
    return events


def draw_match_event(events, previous_id=None):
    """Draw the control mode first, then a compatible event and roster rank."""
    modes = [mode for mode in MATCH_MODES if any(mode in event["modes"] for event in events)]
    if not modes:
        raise ValueError("No match events are available yet.")
    mode = random.choice(modes)
    eligible = [event for event in events if mode in event["modes"]]
    fresh = [event for event in eligible if event["id"] != previous_id]
    event = random.choice(fresh or eligible)
    two_way_order = None
    player_rank = None
    player = None
    if event.get("player_pool") == "two_way":
        # A random priority order works with one, two, or three eligible players
        # without needing the user's roster or biasing shorter lists.
        two_way_order = random.sample([1, 2, 3], 3)
        order = " → ".join(f"#{rank}" for rank in two_way_order)
        player = f"Two-way call-up: {order} (use the first available rank)"
    elif mode == "Player Lock" or event["scope"] == "Player":
        player_rank = random.randint(1, 15)
        player = f"#{player_rank} (rank by overall)"
    return {
        **event, "mode": mode, "player_rank": player_rank,
        "player": player, "two_way_order": two_way_order,
    }
