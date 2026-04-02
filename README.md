# MyNBA Random Event Generator

A clean Streamlit companion for NBA 2K MyNBA storytelling.

Generate realistic season events, track follow-up notes, and keep everything organized in one place with Firestore-backed persistence.

---

## Highlights

- Two-tab layout for quick switching between the event generator and the notepad
- Two-row phase selector to avoid horizontal scrolling
- Weighted event intensity controls with a default `50 / 30 / 20` split
- Anti-repeat logic to reduce duplicate recent events
- Automatic number draws for events that include a range prompt
- Conditional team and player context when an event needs it
- Persistent notepad backed by Firestore, with local JSON fallback
- Sidebar backend status indicator for quick troubleshooting

---

## Project Structure

- `app.py` — Streamlit UI, event flow, and notepad handling
- `event_engine.py` — event loading, weighting, and number-roll helpers
- `event_schema.py` — event validation
- `notepad_utils.py` — notepad helpers
- `events.json` — event database by MyNBA phase
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
/Users/marckallergis/Desktop/MyNBA/.venv/bin/streamlit run app.py
```

Then open the local URL shown in terminal (usually <http://localhost:8501>).

If Firestore is unavailable, the app automatically falls back to `event_notepad.json`.

---

## How It Works

1. Select a phase using the two-row phase picker.
2. Click **Generate Event**.
3. The app chooses an event using weighted probability, applies anti-repeat logic, and rolls any required number ranges.
4. The generated event displays team/player context only when needed.
5. Use the Notepad tab to review items, mark them done, remove them, or add new follow-up notes.

---

## Customizing Events

Edit `events.json` and add events inside the target phase list:

```json
{ "title": "Event Name", "effect": "Event instruction text." }
```

To trigger automatic number rolls, include this phrase pattern in the effect text:

- Draw a number between 1 and 45 ...

---

## Notes

- Keep `events.json` valid JSON (double quotes, commas, brackets).
- The app does not modify NBA 2K files directly; it acts as a companion decision tool.
- You can tune realism by adjusting the 50 / 30 / 20 impact weights in the sidebar.
- The main title uses a blue banner style in the UI.

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
