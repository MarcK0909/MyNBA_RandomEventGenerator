# MyNBA Event Drawing Rules

This document defines when to draw events and how to resolve them in a consistent way.

## 1) When to Draw Events

Draw events at major MyNBA decision points, not on every small action.

Recommended frequency:

- **Regular season:** 2 draws per week, or 1 draw after a major roster/rotation change.
- **Trade Deadline:** 4 draws total on Deadline Day.
- **Playoffs:** 1 draw at the start of each playoff round, or after a major injury/sweep.
- **Training Camp:** 10 draws
- **Free Agency / Draft / Coaching changes:** 4 draws total per phase, split across the number of days in each phase.

If multiple major things happen at once, draw only once unless the situation clearly calls for separate consequences.

## 2) How to Draw Events

Use the app’s phase selector and event generator like this:

1. Pick the correct phase.
2. Click **Generate Event** once.
3. Use the generated event as the current storyline outcome.
4. If the event creates a follow-up issue, add it to the notepad.

## 3) Resolution Order

When an event is drawn, resolve it in this order:

1. Read the event title and effect.
2. Read its eligible target, duration, number roll, and follow-up instructions. If it is flagged, decide the unresolved questions before applying it.
3. Verify the target in your save, then apply the change manually in NBA 2K. Record original values and the actual changes made.
4. Use **Use latest event** and save the note to track the result and its expiry.
5. Move on to the next major phase or decision point.

## 4) Best Practices

- Do not spam draws for the same phase.
- Use one draw for one major story beat.
- If an event is mild, it should usually stay as a note or small adjustment.
- If an event is severe, it can create a longer follow-up chain.
- Keep the story realistic and avoid stacking too many major outcomes at once.

## 5) Notepad Usage

Use the notepad when an event needs future tracking:

- temporary injuries that affect attributes
- rotation changes
- player development changes
- contract or role changes
- storyline reminders

Mark items done once the follow-up has been handled.

## 6) Eligible Targets and Fallbacks

- Event-specific target instructions take priority. The app has no live roster, standings, injury, contract, or staff data; verify eligibility manually.
- A drawn player number is a roster rank by overall, highest first. Break equal-overall ties alphabetically by full name. If that rank does not exist or the player is ineligible, skip the event.
- When instructed to choose a random eligible player or prospect manually, give each eligible candidate an equal chance. "Best" means highest overall unless the event names another measure. "Worst" means lowest overall. Use the same alphabetical tie-breaker.
- Starters are the current starting five. For a sixth man, use the bench player with the most minutes per game. An event's more specific instructions override these defaults.
- If no eligible target, signing, legal trade, or staff opening exists, skip the event. Do not force an impossible roster action or silently substitute a different consequence.
- A flagged event still needs your decision even if you enable **Include events needing review**. Approve it in `events.json` after resolving the listed questions.

## 7) Duration and Restoration

- Use the displayed duration when the effect text omits a time limit. If those instructions conflict, flag the event for review before applying it.
- Games mean the affected team's games unless player appearances are explicitly specified. Days mean in-game calendar days. Count from when you apply the event, not from the computer's current date.
- "Current season" ends when you confirm the app's season rollover after the Playoffs. "Permanent" changes do not expire at rollover. Offseason instructions referring to the opening regular-season games apply to the upcoming regular season in your active app season.
- Respect the limits in your game's editor. Record the actual change after clamping; for example, a requested +3 that can only add +1 must later remove +1.
- For temporary changes, record the affected player, exact fields, actual deltas, and expiry. Reverse only those deltas when the event expires, preserving unrelated development and other events.
- Do not stack another copy of the same active event on the same target unless it explicitly defines a repeat outcome. Skip that draw instead. Different temporary events need separate records.
- Where older wording uses "shooting attributes", use Close Shot, Driving Layup, Mid-Range Shot, and Three-Point Shot. "Rebounding" includes Offensive and Defensive Rebound. If a named field cannot be mapped to your editor, flag the event rather than inventing a substitute.

## 8) Season Follow-ups

- Saving an event note preserves its actual roll, target context, duration, and follow-up. It does not change your NBA 2K save.
- Events with a future-season follow-up preselect that season in the note editor. Save the note to schedule it; it stays hidden until that season starts.
- Resolve retirement instructions and restore changes that expire at season end before confirming rollover. Unfinished notes with the rollover reminder enabled appear in the confirmation.
- If an injury or other effect continues into the next season, move its note to that season before advancing. Rollover deletes notes from the departing season and does not end an ongoing injury in your save.
- Future reminders do not roll new outcomes automatically. Make any instructed future decision or draw when that season begins.
