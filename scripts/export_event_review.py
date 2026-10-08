"""Regenerate the human review checklist after editing events.json."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def render_review(events: dict) -> str:
    count = sum(bool(event.get("needs_review")) for pool in events.values() for event in pool)
    lines = [
        "# Events awaiting your decision", "",
        f"{count} events are flagged in `events.json`. Normal draws exclude them unless you enable **Include events needing review**.", "",
        "Open **Event Review** in the app to browse the same questions by phase. The suggestions below are proposals, not approved instructions.", "",
        "For each event, decide the target, action, amount, duration, and follow-up. Edit its JSON entry, set `needs_review` to `false`, and remove resolved `review_notes`. Update impact and roll metadata if the decision changes them. Checking a box here alone does not change the app.", "",
        "Run `python3 scripts/export_event_review.py` to regenerate this checklist from the remaining flags. Regeneration replaces this file, so keep your final decisions in events.json.", "",
    ]
    for phase, pool in events.items():
        flagged = [event for event in pool if event.get("needs_review")]
        if not flagged:
            continue
        lines += [f"## {phase} ({len(flagged)})", ""]
        for event in flagged:
            lines += [f"### {event['title']}", "", f"- [ ] Resolve `{event['id']}`", "",
                      f"**Current instruction:** {event['effect']}", "",
                      f"**Impact:** {event['impact']}  ", f"**Duration:** {event['duration']}", "",
                      "**Decisions needed:**", ""]
            lines.extend(f"- {question}" for question in event["review_notes"])
            lines.append("")
            if event.get("review_suggestion"):
                lines += [f"**Suggested alternative:** {event['review_suggestion']}", ""]
            if event.get("original_effect") and event["original_effect"] != event["effect"]:
                lines += [f"**Original wording:** {event['original_effect']}", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    events = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
    output = ROOT / "docs" / "EVENT_REVIEW.md"
    output.parent.mkdir(exist_ok=True)
    output.write_text(render_review(events), encoding="utf-8")
    print(f"Updated {output.relative_to(ROOT)}")
