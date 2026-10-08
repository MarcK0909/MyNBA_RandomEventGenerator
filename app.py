import streamlit as st  # type: ignore
import logging
import random
import time
from datetime import date
from html import escape
from pathlib import Path
from constants import DEFAULT_EVENT_WEIGHTS, TEAMS
from season_notebook import (
    active_notes, advance_season, delete_note, save_note,
    scheduled_notes, season_label, set_note_done,
)
from notepad_store import NotepadStore, NotepadStorageError
from event_engine import (
    build_event_note,
    generate_event_number,
    get_event_intensity,
    load_events,
    requires_player_draw,
    requires_team_draw,
    weighted_random_event,
)
from ui import (
    apply_theme,
    empty_state,
    html,
    render_event,
    render_header,
    render_note_card,
    render_weight_distribution,
    section_heading,
)

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="MyNBA | The Front Office",
    page_icon="🏀",
    layout="wide"
)

# -----------------------------
# Load events
# -----------------------------
EVENTS = load_events("events.json")
phases = list(EVENTS.keys())
NOTEPAD_PATH = Path("event_notepad.json")
logger = logging.getLogger(__name__)

PHASE_BUTTON_LABELS = {
    "Regular Season": "Regular Season",
    "Regular Season Post-Deadline": "Post-Deadline",
    "Trade Deadline": "Trade Deadline",
    "Playoffs": "Playoffs",
    "Draft Combine": "Combine",
    "Draft": "Draft",
    "Free Agency": "Free Agency",
    "Summer League": "Summer League",
    "Training Camp": "Training Camp",
    "Coaching Carousel": "Coaching"
}


@st.cache_resource
def get_firestore_doc_ref():
    try:
        firebase_cfg = st.secrets.get("firebase")
        if not firebase_cfg:
            return None
        import firebase_admin  # type: ignore
        from firebase_admin import credentials, firestore  # type: ignore
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(credentials.Certificate(dict(firebase_cfg)))
        db = firestore.client()
        return db.collection(st.secrets.get("firestore_collection", "mynba")).document(
            st.secrets.get("firestore_document", "event_notepad")
        )
    except Exception as exc:
        logger.warning("Firestore unavailable: %s", type(exc).__name__)
        return None


def get_storage_backend_label() -> str:
    return st.session_state.notepad_store.backend


def commit_notebook(updated: dict) -> bool:
    """Only update the visible state once the complete notebook is saved."""
    try:
        # A second browser session may have advanced the shared notebook.
        latest = st.session_state.notepad_store.load()
        if latest["current_season"] != st.session_state.notebook["current_season"]:
            st.session_state.notebook = latest
            reset_note_editor()
            st.session_state.confirm_next_season = False
            st.session_state.last_event = None
            st.session_state.selected_phase = "Coaching Carousel" if "Coaching Carousel" in phases else phases[0]
            st.session_state.notebook_error = "The season changed in another session. Your notebook has refreshed; please try again."
            return False
        if latest.get("updated_at") != st.session_state.notebook.get("updated_at"):
            st.session_state.notebook = latest
            st.session_state.confirm_next_season = False
            st.session_state.notebook_error = "The notes changed in another session. Your notebook has refreshed. Review your draft and save again."
            return False
        st.session_state.notebook = st.session_state.notepad_store.save(updated)
        st.session_state.notebook_error = ""
        return True
    except NotepadStorageError as exc:
        st.session_state.notebook_error = str(exc)
        return False


def reset_note_editor():
    st.session_state.editing_note_id = None
    st.session_state.note_editor_pending = {
        "note_title": "", "note_details": "", "note_review_date": None,
        "note_phase": "Any", "note_season": st.session_state.notebook["current_season"],
        "note_source_event_id": None, "note_resolve_before_rollover": False,
    }
    st.session_state.note_editor_error = ""


def edit_note(item_id: str):
    item = next((item for item in st.session_state.notebook["items"] if item["id"] == item_id), None)
    if item is None:
        return
    try:
        review_date = date.fromisoformat(item.get("due", "")) if item.get("due") else None
    except ValueError:
        review_date = None
    st.session_state.editing_note_id = item_id
    st.session_state.note_editor_pending = {
        "note_title": item.get("title", ""), "note_details": item.get("details", ""),
        "note_review_date": review_date, "note_phase": item.get("phase", "Any"),
        "note_season": item["season"],
        "note_source_event_id": item.get("source_event_id"),
        "note_resolve_before_rollover": bool(item.get("resolve_before_rollover", False)),
    }
    st.session_state.note_editor_error = ""


def submit_note():
    try:
        season = st.session_state.note_season
        review_date = st.session_state.note_review_date
        updated = save_note(
            st.session_state.notebook, title=st.session_state.note_title,
            details=st.session_state.note_details, season=season,
            phase=st.session_state.note_phase,
            due=review_date.isoformat() if review_date else "",
            note_id=st.session_state.editing_note_id,
            source_event_id=st.session_state.note_source_event_id,
            resolve_before_rollover=st.session_state.note_resolve_before_rollover,
        )
        editing = st.session_state.editing_note_id is not None
        if commit_notebook(updated):
            reset_note_editor()
            if season > updated["current_season"]:
                st.session_state.notebook_notice = f"Note scheduled for {season_label(season)}. It will appear when that season starts."
            else:
                st.session_state.notebook_notice = "Note updated." if editing else "Note saved to your season notebook."
    except ValueError as exc:
        st.session_state.note_editor_error = str(exc)


def toggle_note_done(item_id: str, done: bool):
    if commit_notebook(set_note_done(st.session_state.notebook, item_id, done)):
        st.session_state.notebook_notice = "Note completed." if done else "Note reopened."


def remove_notepad_item(item_id: str):
    if commit_notebook(delete_note(st.session_state.notebook, item_id)):
        if st.session_state.editing_note_id == item_id:
            reset_note_editor()
        st.session_state.notebook_notice = "Note deleted."


def prefill_notepad_adder_for_event(event_payload: dict):
    # Filling a form is explicit so another event draw never overwrites a draft.
    draft = build_event_note(event_payload, st.session_state.notebook["current_season"])
    st.session_state.editing_note_id = None
    st.session_state.note_editor_pending = {
        "note_title": draft["title"],
        "note_details": draft["details"],
        "note_review_date": None,
        "note_phase": draft["phase"],
        "note_season": draft["season"],
        "note_source_event_id": draft["source_event_id"],
        "note_resolve_before_rollover": draft["resolve_before_rollover"],
    }
    st.session_state.note_editor_error = ""


def set_selected_phase(phase_name: str):
    st.session_state.selected_phase = phase_name
    st.session_state.confirm_next_season = False


def start_next_season():
    if st.session_state.selected_phase != "Playoffs" or not st.session_state.confirm_next_season:
        return
    previous = st.session_state.notebook["current_season"]
    if commit_notebook(advance_season(st.session_state.notebook)):
        reset_note_editor()
        st.session_state.last_event = None
        st.session_state.confirm_next_season = False
        st.session_state.selected_phase = "Coaching Carousel" if "Coaching Carousel" in phases else phases[0]
        st.session_state.notebook_notice = f"Welcome to {season_label(previous + 1)}. Last season’s notes have been deleted and this season’s notes are now available."


def render_season_controls():
    notebook = st.session_state.notebook
    current = notebook["current_season"]
    open_count = sum(not item.get("done") for item in active_notes(notebook))
    html(f'<div class="season-banner"><div><span class="eyebrow">YOUR FRANCHISE TIMELINE</span>'
         f'<h2>{escape(season_label(current))}</h2></div><span class="season-open">{open_count} open notes</span></div>')
    if st.session_state.selected_phase == "Playoffs":
        if not st.session_state.confirm_next_season:
            st.button("Finish Playoffs · Start next season →", key="prepare_next_season", use_container_width=True,
                      on_click=lambda: st.session_state.update(confirm_next_season=True))
        else:
            expired = sum(item["season"] == current for item in notebook["items"])
            arriving = sum(item["season"] == current + 1 for item in notebook["items"])
            st.warning(f"Start {season_label(current + 1)}? This permanently deletes {expired} notes assigned to {season_label(current)} and reveals {arriving} scheduled notes.")
            pending = [item for item in notebook["items"] if item["season"] == current
                       and not item.get("done") and item.get("resolve_before_rollover")]
            if pending:
                st.info("Before continuing, restore any expired event changes and move still-active follow-ups to the next season. This app does not edit your NBA 2K save.")
                for item in pending:
                    st.write("• " + item.get("title", "Untitled follow-up"))
            confirm, cancel = st.columns(2)
            with confirm:
                st.button("Start next season", key="confirm_next_season_button", type="primary", use_container_width=True, on_click=start_next_season)
            with cancel:
                st.button("Stay in this season", use_container_width=True,
                          on_click=lambda: st.session_state.update(confirm_next_season=False))
    else:
        st.caption("Advance your season after the Playoffs. Scheduled notes appear when their season begins.")


def render_notepad_editor():
    if "note_editor_pending" in st.session_state:
        for key, value in st.session_state.pop("note_editor_pending").items():
            st.session_state[key] = value
    editing = st.session_state.editing_note_id is not None
    section_heading("02", "Edit your note" if editing else "A place for the next chapter",
                    "Make a change, then save it to your notebook." if editing else "Capture a storyline now. Choose when it matters.", panel=True, anchor="note-editor")
    if st.session_state.note_editor_error:
        st.error(st.session_state.note_editor_error)
    current = st.session_state.notebook["current_season"]
    season_options = list(range(current, current + 21))
    selected = st.session_state.get("note_season", current)
    if selected not in season_options:
        season_options.append(selected)
    if st.session_state.get("note_phase") not in ["Any"] + phases:
        st.session_state.note_phase = "Any"
    with st.form("note_editor", border=False):
        st.text_input("Note title", key="note_title", placeholder="e.g. Give the rookie a bigger role")
        st.text_area("Details", key="note_details", placeholder="The change, the player, the follow-up…", height=130)
        st.selectbox("Show this note in", season_options, key="note_season",
                     format_func=lambda season: season_label(season) + (" · current" if season == current else ""),
                     help="Future notes stay hidden until their season starts. Every note is deleted when its assigned season ends.")
        with st.expander("Phase & review date · optional"):
            st.selectbox("Related phase", ["Any"] + phases, key="note_phase")
            st.date_input("Review date", value=None, key="note_review_date", help="Optional reminder date. Seasons advance manually, independently of the calendar.")
            st.checkbox("Remind me before season rollover", key="note_resolve_before_rollover")
        st.form_submit_button("Save changes" if editing else "Save note", type="primary", use_container_width=True, on_click=submit_note)
    st.button("Cancel editing" if editing else "Clear draft", key="reset_note_editor", use_container_width=True, on_click=reset_note_editor)
    if st.session_state.last_event and not editing:
        st.button("Use latest event", key="use_event_in_note", use_container_width=True,
                  on_click=prefill_notepad_adder_for_event, args=(st.session_state.last_event,))


def render_notepad_items_panel():
    notebook = st.session_state.notebook
    notes = active_notes(notebook)
    completed = sum(bool(item.get("done")) for item in notes)
    future_count = len(scheduled_notes(notebook))
    section_heading("01", "The season notebook", "Your active storylines, with room for what comes next.")
    html('<a class="note-editor-link" href="#note-editor">Jump to note editor ↗</a>')
    html(f'<div class="notebook-stats"><div><strong>{len(notes) - completed}</strong><span>Open storylines</span></div>'
         f'<div><strong>{completed}</strong><span>Completed</span></div>'
         f'<div><strong>{future_count}</strong><span>Scheduled for later</span></div></div>')
    filter_cols = st.columns([1.2, 1])
    with filter_cols[0]:
        query = st.text_input("Search season notes", key="note_search", placeholder="Find a player, team, or storyline…")
    with filter_cols[1]:
        status = st.selectbox("Show", ["Open notes", "All active notes", "Completed"], key="note_status")
    term = query.strip().lower()
    visible = [item for item in notes if
               (status != "Open notes" or not item.get("done")) and
               (status != "Completed" or item.get("done")) and
               (not term or term in (str(item.get("title", "")) + " " + str(item.get("details", ""))).lower())]
    if not visible:
        if term or status == "Completed":
            empty_state("No notes match this view", "Try another search or change the status filter.", compact=True)
        elif notes:
            empty_state("Everything is taken care of", "Your completed storylines are still here. Choose All active notes to revisit them.")
        else:
            empty_state("A fresh page for your season", "Add your first note here, or bring an event into the notebook with Use latest event.")
    for item in visible:
        with st.container(border=True):
            render_note_card(item)
            actions = st.columns([1.3, 1, 1])
            with actions[0]:
                st.button("Reopen" if item.get("done") else "Mark complete", key=f"done_{item['id']}", use_container_width=True,
                          on_click=toggle_note_done, args=(item["id"], not item.get("done", False)))
            with actions[1]:
                st.button("Edit", key=f"edit_{item['id']}", use_container_width=True, on_click=edit_note, args=(item["id"],))
            with actions[2]:
                st.button("Delete", key=f"delete_{item['id']}", use_container_width=True, on_click=remove_notepad_item, args=(item["id"],))
    if future_count:
        st.caption(f"{future_count} scheduled notes are tucked away. They will appear automatically when their assigned season starts.")


def render_event_review():
    flagged = [(phase, event) for phase, events in EVENTS.items() for event in events if event.get("needs_review")]
    section_heading("01", "Events for your review", f"{len(flagged)} scenarios need your judgment before they are ready for normal draws.")
    st.caption("Edit the event in events.json after making your decision, then set needs_review to false and remove the resolved review_notes. The suggested alternative is a proposal, not an instruction to apply.")
    filters = st.columns([1, 2])
    with filters[0]:
        phase_filter = st.selectbox("Review phase", ["All phases"] + phases, key="review_phase")
    with filters[1]:
        query = st.text_input("Find an event to review", key="review_search", placeholder="Search titles, instructions, or review questions…").strip().lower()
    matches = [(phase, event) for phase, event in flagged if
               (phase_filter == "All phases" or phase == phase_filter) and
               (not query or query in (event["title"] + " " + event["effect"] + " " + " ".join(event["review_notes"])).lower())]
    st.caption(f"{len(matches)} events in this view")
    for phase, event in matches:
        with st.expander(f"{phase} · {event['title']}"):
            st.write(event["effect"])
            st.caption(f"Impact: {event['impact']} · Duration: {event['duration']}")
            for note in event["review_notes"]:
                st.warning(note)
            if event.get("review_suggestion"):
                st.info("Suggested alternative: " + event["review_suggestion"])
            if event.get("original_effect") and event["original_effect"] != event["effect"]:
                st.caption("Original wording")
                st.write(event["original_effect"])
            st.code(event["id"], language=None)
    if not matches:
        empty_state("No flagged events in this view", "Try another phase or search term.", compact=True)


def roll_event_for_phase(phase_name: str):
    history = st.session_state.setdefault("recent_event_history", {})
    recent_titles = set(history.get(phase_name, []))
    event = weighted_random_event(
        EVENTS[phase_name],
        st.session_state.event_weights,
        recent_titles
    )

    effect_text = event.get("effect", "")
    locked_team = st.session_state.get("locked_team")
    team = (locked_team if locked_team else random.choice(TEAMS)) if requires_team_draw(event) else None
    player_number = random.randint(1, 15) if requires_player_draw(event) else None
    intensity = get_event_intensity(event)
    event_roll = generate_event_number(event)

    st.session_state.last_event = {
        **event,
        "phase": phase_name,
        "title": event["title"],
        "effect": effect_text,
        "team": team,
        "player": f"#{player_number} (rank by overall)" if player_number is not None else None,
        "intensity": intensity,
        "event_roll": event_roll
    }
    history[phase_name] = (history.get(phase_name, []) + [event.get("id", event["title"])])[-5:]
    st.toast("🏀 New event generated!", icon="🎲")

# -----------------------------
# Session state
# -----------------------------
if "last_event" not in st.session_state:
    st.session_state.last_event = None

if "event_weights" not in st.session_state:
    st.session_state.event_weights = DEFAULT_EVENT_WEIGHTS.copy()

if "locked_team" not in st.session_state:
    st.session_state.locked_team = None

if "notebook" not in st.session_state:
    st.session_state.notepad_store = NotepadStore(NOTEPAD_PATH, get_firestore_doc_ref(), initial_season=2026)
    try:
        st.session_state.notebook = st.session_state.notepad_store.load()
    except NotepadStorageError as exc:
        st.error(str(exc))
        st.stop()

for state_key, default in {
    "editing_note_id": None, "note_editor_error": "", "notebook_error": "",
    "notebook_notice": "", "confirm_next_season": False, "workspace": "Event Generator",
    "note_source_event_id": None, "note_resolve_before_rollover": False,
}.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default

if "note_title" not in st.session_state and "note_editor_pending" not in st.session_state:
    reset_note_editor()

if "selected_phase" not in st.session_state:
    st.session_state.selected_phase = phases[0]

# -----------------------------
# Visual theme and header
# -----------------------------
apply_theme()
render_header(sum(len(events) for events in EVENTS.values()), len(phases), show_hero=st.session_state.workspace == "Event Generator")

# -----------------------------
# Weight controls
# -----------------------------
with st.sidebar:
    html('<div class="sidebar-brand">League settings</div><div class="sidebar-kicker">SET THE TONE FOR YOUR SEASON</div>')
    st.markdown("### Event intensity")
    st.caption("Choose the probability split between available impact tiers. Each tier’s share is independent of its number of events.")

    low_w = st.slider("Low Impact", min_value=0, max_value=100, value=st.session_state.event_weights["Low Impact"], step=5)
    med_w = st.slider("Medium Impact", min_value=0, max_value=100, value=st.session_state.event_weights["Medium Impact"], step=5)
    high_w = st.slider("High Impact", min_value=0, max_value=100, value=st.session_state.event_weights["High Impact"], step=5)

    weight_total = low_w + med_w + high_w
    if weight_total == 0:
        st.warning("All tiers are set to 0. Using default weighting.")
        st.session_state.event_weights = DEFAULT_EVENT_WEIGHTS.copy()
    else:
        st.session_state.event_weights = {
            "Low Impact": low_w,
            "Medium Impact": med_w,
            "High Impact": high_w
        }

    render_weight_distribution(st.session_state.event_weights)
    st.caption(f"Total weight: {sum(st.session_state.event_weights.values())}")

    st.markdown("---")
    st.markdown("### Team context")
    st.caption("Keep the spotlight on one franchise.")
    use_locked_team = st.toggle("Lock team context", value=st.session_state.locked_team is not None)
    if use_locked_team:
        st.session_state.locked_team = st.selectbox("Locked team", TEAMS, index=0)
    else:
        st.session_state.locked_team = None

    if st.button("Clear last event", use_container_width=True):
        st.session_state.last_event = None
        st.toast("Last event cleared.")

    st.markdown("---")
    st.markdown("### The number draw")
    st.caption("Automatically rolled when a scenario calls for a random number.")

    if st.session_state.last_event and st.session_state.last_event.get("event_roll"):
        roll = st.session_state.last_event["event_roll"]
        html(f'<div class="sidebar-roll"><b>{escape(str(roll["value"]))}</b><span>Last auto-roll<br>Range {escape(str(roll["label"]))}</span></div>')
    else:
        st.caption("Waiting for your first number draw.")

    st.markdown("---")
    html(f'<div class="storage-label">Storage · {escape(get_storage_backend_label())}</div>')

st.radio("Workspace", ["Event Generator", "Notepad", "Event Review"], horizontal=True, key="workspace", label_visibility="collapsed")
render_season_controls()
if st.session_state.notebook_error:
    st.error(st.session_state.notebook_error)
if st.session_state.notebook_notice:
    st.success(st.session_state.pop("notebook_notice"))

if st.session_state.workspace == "Event Generator":
    generator_col, notepad_col = st.columns([1.8, 1], gap="large")
    with generator_col:
        with st.container(border=True):
            section_heading("01", "Set the scene", "Choose where you are in your season.", panel=True)
            playoffs_index = phases.index("Playoffs")
            phase_rows = [
                phases[:playoffs_index],
                ["Playoffs"],
                phases[playoffs_index + 1:],
            ]
            for phase_row in phase_rows:
                if not phase_row:
                    continue
                for col, phase_name in zip(st.columns(len(phase_row)), phase_row):
                    with col:
                        st.button(
                            PHASE_BUTTON_LABELS.get(phase_name) or phase_name,
                            key=f"phase_btn_{phase_name}",
                            help=phase_name,
                            use_container_width=True,
                            type="primary" if st.session_state.selected_phase == phase_name else "secondary",
                            on_click=set_selected_phase,
                            args=(phase_name,)
                        )

            selected_phase = st.session_state.selected_phase
            phase_events = EVENTS[selected_phase]
            include_review = st.toggle("Include events needing review", value=False, key="include_review_events",
                                       help="Unresolved events are excluded by default. Browse them in Event Review; enabling this includes their original uncertainties in draws.")
            eligible_events = [event for event in phase_events if include_review or not event.get("needs_review")]
            filter_key = f"filter_{selected_phase}"
            st.text_input(
                "Filter events in this phase",
                key=filter_key,
                placeholder="Search scenarios by title or effect…"
            )
            search_term = st.session_state.get(filter_key, "").strip().lower()

            if search_term:
                filtered_events = [
                    ev for ev in eligible_events
                    if search_term in ev.get("title", "").lower() or search_term in ev.get("effect", "").lower()
                ]
            else:
                filtered_events = eligible_events

            html(f'<div class="phase-summary"><strong>{escape(selected_phase)}</strong>'
                 f'<span><b>{len(filtered_events)}</b> / {len(phase_events)} scenarios available</span></div>')
            available_tiers = {get_event_intensity(event) for event in filtered_events}
            if available_tiers:
                total = sum(st.session_state.event_weights[tier] for tier in available_tiers)
                if total:
                    split = " · ".join(f"{tier.replace(' Impact', '')} {st.session_state.event_weights[tier] / total:.0%}"
                                       for tier in DEFAULT_EVENT_WEIGHTS if tier in available_tiers)
                    st.caption("This pool: " + split)
                else:
                    st.caption("All tiers present in this pool have zero weight. The next draw will use equal event probabilities.")

            if st.button("Generate Event ↗", key=f"gen_{selected_phase}", type="primary", use_container_width=True):
                with st.spinner("Rolling the dice..."):
                    time.sleep(0.4)
                if filtered_events:
                    original_events = EVENTS[selected_phase]
                    EVENTS[selected_phase] = filtered_events
                    roll_event_for_phase(selected_phase)
                    EVENTS[selected_phase] = original_events
                else:
                    st.warning("No events match this filter. Clear the search or check Event Review for flagged scenarios.")
            html('<p class="draw-hint">One draw. A new direction for your season.</p>')

        if st.session_state.last_event:
            render_event(st.session_state.last_event)
        else:
            empty_state("Your next storyline is one draw away", "Choose a season phase, dial in the intensity, and let your league surprise you.")

    with notepad_col:
        with st.container(border=True):
            render_notepad_editor()

elif st.session_state.workspace == "Notepad":
    notes_col, editor_col = st.columns([1.8, 1], gap="large")
    with notes_col:
        render_notepad_items_panel()
    with editor_col:
        with st.container(border=True):
            render_notepad_editor()

else:
    render_event_review()

html('<footer class="app-footer"><span>MyNBA / The Front Office</span><span>A little unpredictability. A more memorable league.</span></footer>')
