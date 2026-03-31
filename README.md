# 🏀 MyNBA Random Event Generator

Offline Streamlit companion for NBA 2K MyNBA storytelling.
Generate realistic random events by season phase, with weighted outcomes and automatic helper rolls for special events.

---

## Features

- Phase-based event generator (Regular Season, Trade Deadline, Playoffs, Draft Combine, etc.)
- Weighted event intensity controls:
  - Low Impact
  - Medium Impact
  - High Impact
  - Chaos
- Smart anti-repeat logic to reduce duplicate recent events
- Automatic random-number draws for events that include:
  - “Draw a number between X and Y”
- Conditional context display:
  - Team shown only when event requires a team draw
  - Player shown only when event requires a player draw
- Recent event history panel

---

## Project Structure

- app.py — Streamlit app UI + event logic
- events.json — Event database by MyNBA phase
- .gitignore — Python/Streamlit/macOS ignores

---

## Requirements

- Python 3.10+ (3.12 recommended)
- Streamlit

Install dependencies:

```bash
pip install streamlit
```

---

## Run Locally

From the project folder:

```bash
streamlit run app.py
```

Then open the local URL shown in terminal (usually <http://localhost:8501>).

---

## How It Works

1. Pick a phase tab.
2. Click **Generate Event**.
3. The app:
   - Selects an event with weighted probability based on inferred intensity.
   - Applies anti-repeat weighting if event appeared recently.
   - Auto-rolls numbers for matching draw-range events.
   - Shows only relevant team/player context when required by event text.

---

## Customizing Events

Edit events.json and add events inside the target phase list:

```json
{ "title": "Event Name", "effect": "Event instruction text." }
```

If you want auto-number rolls, include this phrase pattern in effect text:

- Draw a number between 1 and 45 ...

---

## Notes

- Keep events.json valid JSON (double quotes, commas, brackets).
- The app does not modify NBA 2K files directly; it acts as a companion decision tool.
- You can tune realism by lowering Chaos weight and increasing Low/Medium weights.

---

## Roadmap Ideas

- Preset weighting modes (Realistic, Balanced, Chaos League)
- Export recent events to text/CSV
- Event tagging (injury, contract, chemistry, coaching)
- Optional stricter realism filter mode

---

## License

Personal project / custom use. Add your preferred license if you plan to share publicly.
