# Events awaiting your decision

0 events are flagged in `events.json`. Normal draws exclude them unless you enable **Include events needing review**.

Open **Event Review** in the app to browse the same questions by phase. The suggestions below are proposals, not approved instructions.

For each event, decide the target, action, amount, duration, and follow-up. Edit its JSON entry, set `needs_review` to `false`, and remove resolved `review_notes`. Update impact and roll metadata if the decision changes them. Checking a box here alone does not change the app.

Run `python3 scripts/export_event_review.py` to regenerate this checklist from the remaining flags. Regeneration replaces this file, so keep your final decisions in events.json.
