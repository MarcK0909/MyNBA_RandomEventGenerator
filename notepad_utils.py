import re
from datetime import date, datetime, timedelta
from typing import Optional


def is_temporary_effect(effect_text: str) -> bool:
    text = effect_text.lower()
    if "permanent" in text or "permanently" in text:
        return False

    temp_markers = [
        "for the next",
        "for next",
        "out ",
        "one week",
        "next game",
        "next 3 games",
        "next 5 games",
        "next 10 days",
        "minutes restriction",
        "suspended for",
        "until the all-star break",
        "sits out for",
    ]
    return any(marker in text for marker in temp_markers)


def re_search_number_range_days(text: str) -> Optional[int]:
    match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*days", text)
    if not match:
        return None
    return max(int(match.group(1)), int(match.group(2)))


def re_search_number_days(text: str) -> Optional[int]:
    match = re.search(r"(\d+)\s*days", text)
    if not match:
        return None
    return int(match.group(1))


def re_search_number_games(text: str) -> Optional[int]:
    match = re.search(r"(\d+)\s*games", text)
    if not match:
        return None
    return int(match.group(1))


def estimate_due_date(effect_text: str, today: Optional[date] = None) -> date:
    base_date = today or date.today()
    text = effect_text.lower()

    range_days_match = re_search_number_range_days(text)
    if range_days_match is not None:
        return base_date + timedelta(days=range_days_match)

    days_match = re_search_number_days(text)
    if days_match is not None:
        return base_date + timedelta(days=days_match)

    games_match = re_search_number_games(text)
    if games_match is not None:
        return base_date + timedelta(days=max(2, games_match * 2))

    if "one week" in text:
        return base_date + timedelta(days=7)
    if "next game" in text:
        return base_date + timedelta(days=2)
    if "until the all-star break" in text:
        return base_date + timedelta(days=30)

    return base_date + timedelta(days=10)


def build_auto_notepad_item(event_payload: dict, now: Optional[datetime] = None, today: Optional[date] = None):
    effect_text = event_payload.get("effect", "")
    if not effect_text or not is_temporary_effect(effect_text):
        return None

    player = event_payload.get("player")
    team = event_payload.get("team")
    if player and team:
        subject = f"Player {player} on {team}"
    elif player:
        subject = f"Player {player}"
    elif team:
        subject = f"Team {team}"
    else:
        subject = "Manual target"

    stamp = now or datetime.now()
    due = estimate_due_date(effect_text, today=today)

    return {
        "id": int(stamp.timestamp() * 1000),
        "title": f"Temporary Event Tracker: {event_payload.get('title', 'Event')}",
        "details": f"{subject} has a temporary effect to track. Effect: {effect_text}",
        "due": due.isoformat(),
        "phase": event_payload.get("phase", "Any"),
        "done": False,
        "created_at": stamp.isoformat(timespec="seconds"),
    }
