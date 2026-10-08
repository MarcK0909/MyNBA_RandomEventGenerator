# MyNBA Random Event Generator

A Streamlit companion for NBA 2K MyNBA storytelling, styled as your own basketball front office.

Generate realistic season events, track follow-up notes, and keep everything organized in one place with Firestore-backed persistence.

---

## Highlights

- Dark charcoal theme with warm orange accents and a basketball court illustration
- Responsive generator and note editor, side by side on desktop and stacked on smaller screens
- Impact-colored event cards, team/player context, and automatic number-draw displays
- Season-scoped note cards with search, editing, completion, and optional review dates
- Current and future-season notes, with a confirmed rollover after the Playoffs
- Persistent navigation between the event generator, notepad, and Event Review
- Grouped phase selector with a full-width Playoffs button and an offseason row
- Weighted event intensity controls with a default `50 / 30 / 20` split
- Anti-repeat logic to reduce duplicate recent events
- Automatic number draws for events that include a range prompt
- Conditional team and player context when an event needs it
- Explicit event durations, eligible targets, and restoration instructions
- Flagged scenarios with review questions, original wording, and proposed alternatives
- Persistent notepad backed by Firestore, with local JSON fallback
- Sidebar backend status indicator for quick troubleshooting

---

## Project Structure

- `app.py` — Streamlit UI, event flow, and notepad handling
- `ui.py` — presentation helpers and HTML components
- `assets/theme.css` — responsive layout and component styling
- `.streamlit/config.toml` — native Streamlit colors and dark theme
- `event_engine.py` — event loading, weighting, and number-roll helpers
- `event_schema.py` — event validation
- `notepad_utils.py` — notepad helpers
- `season_notebook.py` — note creation, editing, visibility, and season rollover
- `notepad_store.py` — Firestore persistence and atomic local notebook storage
- `events.json` — event database by MyNBA phase
- `docs/EVENT_REVIEW.md` — checklist of events awaiting your decision
- `scripts/export_event_review.py` — regenerate the checklist from event flags
- `RULES.md` — draw frequency, eligibility, durations, and follow-up rules
- `.gitignore` — Python, Streamlit, and macOS ignores

---

## Requirements

- Python 3.10+ (3.12 recommended)
- Streamlit
- Firebase Admin SDK (for Firestore-backed notepad persistence)

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Run Locally

From the project folder:

```bash
python3.11 -m streamlit run app.py
```

Then open the local URL shown in terminal (usually <http://localhost:8501>).

Use the Python interpreter where you installed the requirements. If a server is already running, stop it with **Ctrl+C** and restart to pick up the theme configuration.

If Firestore is unavailable, the app automatically falls back to `event_notepad.json`.

### Check the design refresh

Compare the [original layout](docs/ui-before.png) with the [first design refresh](docs/ui-after.png). In the app, select a phase, generate an event, and open Notepad. Narrow the browser window to check the stacked layout and compact phase grid.

---

## How It Works

1. Select a phase using the grouped phase picker.
2. Click **Generate Event**.
3. The app chooses an event using weighted probability, applies anti-repeat logic, and rolls any required number ranges.
4. The generated event displays team/player context only when needed.
5. Choose **Use latest event** to fill a note, or write one yourself. New event draws leave your draft intact.
6. Open **Notepad** to create, edit, search, complete, reopen, or delete your notes.

The default impact weights give Low, Medium, and High tiers a **50% / 30% / 20%** chance when all three are available. A tier's number of events does not change its total chance. Missing or disabled tiers redistribute their share among the remaining enabled tiers; the generator shows the effective split for your current search. Recent draws receive a smaller chance within their tier. If every available tier has zero weight, events are drawn with equal probability.

### Review unclear events

Open **Event Review** to filter unresolved scenarios by phase or search their instructions and questions. Normal draws exclude these events; **Include events needing review** opts them into the pool and displays their questions when drawn.

The [review checklist](docs/EVENT_REVIEW.md) contains the same flagged events. Decide each event's target, action, amount, duration, and follow-up, then edit its entry in `events.json`. Set `needs_review` to `false` and remove the resolved `review_notes`. Update its impact, target, duration, tracking, and roll fields to match your decision. Keep the `id` stable. Checking a Markdown box alone does not approve an event in the app.

Refresh the app after saving your edits, then regenerate the checklist:

```bash
python3.11 scripts/export_event_review.py
```

The script replaces the checklist, so keep final decisions in `events.json`.

## Seasons and the Notepad

See the [season notebook preview](docs/ui-notebook.png).

- Your first season is **2026–27**. Existing notes are assigned to it without losing their contents or completion status.
- Notes default to the current season. Use **Show this note in** to schedule one for a future season.
- Only notes assigned to the active season appear in the notebook or its search results. The scheduled count tells you how many are waiting; their contents stay hidden until the assigned season begins.
- Choose **Playoffs**, then **Finish Playoffs · Start next season**. Review the note counts and confirm **Start next season** to advance one year and move into the offseason at Coaching Carousel.
- Advancing permanently deletes all notes assigned to the departing season, including completed notes. Notes scheduled for the new season become visible; later notes stay stored and hidden. Merely selecting another phase never advances the season.
- For example, moving from **2026–27** to **2027–28** deletes the 2026–27 notes, reveals the 2027–28 notes, and keeps 2028–29 notes hidden.
- A review date is optional and does not control season progression. You advance the season manually when your MyNBA playoffs are finished.
- **Use latest event** includes the actual roll, target, duration, and follow-up in your draft. Events with a next-season follow-up preselect that future season. Saving the draft is still required.
- Notes marked **Remind me before season rollover** appear in the rollover confirmation while unfinished. Handle retirements and restore expired temporary changes before advancing. Move any still-active follow-up into the next season before confirming, since departing notes are deleted.

The active season and notes are saved together in the same Firestore document, with an atomic local JSON fallback. The app also reads the original flat-list format. Failed saves keep the existing state, and reloading preserves the active season. Test rollover in a separate local copy if you want to try it without deleting your real season notes.

---

## Customizing Events

Edit `events.json` and add events inside the target phase list. A complete entry looks like this:

```json
{
  "id": "regular-season--extra-shooting-work",
  "title": "Extra Shooting Work",
  "effect": "The player drawn gains +2 Three-Point Shot for the next 3 team games.",
  "impact": "Low Impact",
  "requires_team": true,
  "requires_player": true,
  "target": "The drawn roster rank on the drawn team, ranked by overall.",
  "duration": "Next 3 team games",
  "tracking": "Record the actual increase and its expiry; remove only this event's increase afterward.",
  "needs_review": false,
  "note_season_offset": 0,
  "resolve_before_rollover": false
}
```

Use `Low Impact`, `Medium Impact`, or `High Impact` explicitly. For an uncertain event, set `needs_review: true`, add a nonempty list of `review_notes`, and preserve its wording in `original_effect`. An optional `review_suggestion` provides an alternative for you to consider.

To roll a number, add `roll_type: "range"`, integer `roll_min` and `roll_max`, and a descriptive `roll_purpose`. Optional `roll_outcomes` entries have `min`, `max`, and `label`; they must cover the entire range without gaps or overlaps. The app displays the result and copies it into event notes.

`note_season_offset: 1` schedules the note for the following season; `0` uses the active season. `resolve_before_rollover: true` adds an unfinished-note reminder to the rollover confirmation. These fields do not apply changes inside NBA 2K or execute future outcomes automatically.

Legacy entries containing only `title` and `effect` still load, including the automatic-roll phrase “Draw a number between 1 and 45”. Explicit metadata is preferred for new entries.

Validate changes with:

```bash
python3.11 -m unittest discover -s tests
```

---

## Notes

- Keep `events.json` valid JSON (double quotes, commas, brackets).
- The app does not modify NBA 2K files directly; it acts as a companion decision tool.
- You can tune realism by adjusting the 50 / 30 / 20 impact weights in the sidebar.
- The visual theme is defined in `assets/theme.css` and `.streamlit/config.toml`.

---

## Roadmap Ideas

- Preset weighting modes (Realistic, Balanced, Chaos League)
- Export recent events to text/CSV
- Event tagging (injury, contract, chemistry, coaching)
- Optional stricter realism filter mode

## Firestore Setup

- Create a Firestore database in the `nba-event-generator` project.
- Store your service account details in `.streamlit/secrets.toml` locally and in Streamlit Cloud secrets for deployment.
- The app reads from collection `mynba` and document `event_notepad` by default.
- If Firestore is unavailable, the app uses local JSON storage automatically.

---

## License

Personal project / custom use. Add your preferred license if you plan to share publicly.
