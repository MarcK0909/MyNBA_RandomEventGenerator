import streamlit as st  # type: ignore
import json
import logging
import random
import time
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any, Protocol
from constants import DEFAULT_EVENT_WEIGHTS, TEAMS
from event_engine import (
    generate_event_number,
    get_event_intensity,
    load_events,
    weighted_random_event,
)
from ui import (
    apply_theme,
    empty_state,
    html,
    render_event,
    render_header,
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


class FirestoreSnapshot(Protocol):
    exists: bool

    def to_dict(self) -> dict[str, Any] | None:
        ...


class FirestoreDocRef(Protocol):
    def get(self) -> FirestoreSnapshot:
        ...

    def set(self, document: dict[str, Any], merge: bool = False) -> None:
        ...


class FirestoreNotepadStore:
    def __init__(self, doc_ref: Any):
        self._doc_ref = doc_ref

    def load_items(self) -> list[dict[str, Any]]:
        snapshot = self._doc_ref.get()
        if snapshot.exists:
            payload = snapshot.to_dict() or {}
            items = payload.get("items", [])
            if isinstance(items, list):
                return items
        return []

    def save_items(self, items: list[dict[str, Any]]) -> None:
        self._doc_ref.set(
            {
                "items": items,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
            merge=True,
        )


@st.cache_resource
def get_firestore_doc_ref() -> FirestoreNotepadStore | None:
    try:
        firebase_cfg = st.secrets.get("firebase")
        if not firebase_cfg:
            return None

        import firebase_admin  # type: ignore
        from firebase_admin import credentials, firestore  # type: ignore

        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_dict = dict(firebase_cfg)
            firebase_admin.initialize_app(credentials.Certificate(firebase_dict))

        db = firestore.client()
        collection_name = st.secrets.get("firestore_collection", "mynba")
        document_id = st.secrets.get("firestore_document", "event_notepad")
        return FirestoreNotepadStore(db.collection(collection_name).document(document_id))
    except (ImportError, KeyError, AttributeError) as exc:
        logger.warning("Firestore client unavailable: %s", exc)
        return None
    except Exception:
        logger.exception("Unexpected error while initializing Firestore")
        return None


def is_firestore_available() -> bool:
    if "firestore_available" not in st.session_state:
        st.session_state["firestore_available"] = get_firestore_doc_ref() is not None
    return bool(st.session_state["firestore_available"])


def get_storage_backend_label() -> str:
    return "Firestore" if is_firestore_available() else "Local JSON (fallback)"


def load_notepad_items():
    doc_ref = get_firestore_doc_ref()
    if doc_ref is not None:
        try:
            return doc_ref.load_items()
        except Exception:
            logger.exception("Failed to load notepad items from Firestore")

    if not NOTEPAD_PATH.exists():
        return []

    try:
        with NOTEPAD_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError as exc:
        logger.warning("Could not decode local notepad JSON: %s", exc)
    except OSError:
        logger.exception("Failed to read local notepad file")
    return []


def save_notepad_items(items):
    doc_ref = get_firestore_doc_ref()
    if doc_ref is not None:
        try:
            doc_ref.save_items(items)
            return
        except Exception:
            logger.exception("Failed to save notepad items to Firestore")

    try:
        with NOTEPAD_PATH.open("w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
    except OSError:
        logger.exception("Failed to save local notepad file")


def clear_notepad_title():
    st.session_state.notepad_draft_item_pending = ""
    st.session_state.notepad_draft_source_key = None


def clear_notepad_details():
    st.session_state.notepad_draft_details_pending = ""
    st.session_state.notepad_draft_source_key = None


def clear_all_notepad_draft_fields():
    st.session_state.notepad_draft_item_pending = ""
    st.session_state.notepad_draft_details_pending = ""
    st.session_state.notepad_draft_due_pending = date.today()
    st.session_state.notepad_draft_phase_pending = "Any"
    st.session_state.notepad_draft_source_key = None


def remove_notepad_item(item_id):
    st.session_state.notepad_items = [
        item for item in st.session_state.notepad_items
        if item.get("id") != item_id
    ]
    save_notepad_items(st.session_state.notepad_items)


def sync_notepad_done(item_id):
    done_key = f"note_done_{item_id}"
    done_value = bool(st.session_state.get(done_key, False))

    for item in st.session_state.notepad_items:
        if item.get("id") == item_id:
            item["done"] = done_value
            break

    save_notepad_items(st.session_state.notepad_items)


def add_notepad_item():
    note_title = st.session_state.notepad_draft_item.strip()
    if not note_title:
        st.warning("Please add a title for the notepad item.")
        return

    new_item = {
        "id": int(datetime.now().timestamp() * 1000),
        "title": note_title,
        "details": st.session_state.notepad_draft_details.strip(),
        "due": st.session_state.notepad_draft_due.isoformat(),
        "phase": st.session_state.notepad_draft_phase,
        "done": False,
        "created_at": datetime.now().isoformat(timespec="seconds")
    }
    st.session_state.notepad_items.insert(0, new_item)
    save_notepad_items(st.session_state.notepad_items)
    clear_all_notepad_draft_fields()
    st.toast("Notepad item added.")
    st.rerun()


def _event_source_key(event_payload: dict) -> str:
    return "|".join([
        str(event_payload.get("phase", "")),
        str(event_payload.get("title", "")),
        str(event_payload.get("effect", "")),
        str(event_payload.get("team", "")),
        str(event_payload.get("player", "")),
        str((event_payload.get("event_roll") or {}).get("value", "")),
    ])


def prefill_notepad_adder_for_event(event_payload: dict):
    src_key = _event_source_key(event_payload)
    if st.session_state.get("notepad_draft_source_key") == src_key:
        return

    team = event_payload.get("team")
    player = event_payload.get("player")
    target_text = " • ".join([v for v in [team, player] if v])

    title = event_payload.get("title", "Generated Event")
    effect = event_payload.get("effect", "")
    phase = event_payload.get("phase", "Any")

    st.session_state.notepad_draft_item_pending = f"Track: {title}" + (f" ({target_text})" if target_text else "")
    st.session_state.notepad_draft_details_pending = (
        f"Event: {title}\n"
        f"Effect: {effect}" + (f"\nTarget: {target_text}" if target_text else "")
    )
    st.session_state.notepad_draft_due_pending = date.today()
    st.session_state.notepad_draft_phase_pending = phase if phase in phases else "Any"
    st.session_state.notepad_draft_source_key = src_key


def set_selected_phase(phase_name: str):
    st.session_state.selected_phase = phase_name


def handle_clear_title():
    clear_notepad_title()
    st.rerun()


def handle_clear_details():
    clear_notepad_details()
    st.rerun()


def handle_add_notepad_item():
    add_notepad_item()


def render_notepad_items_panel():
    section_heading("02", "Your season, on record", "Keep track of the changes that need a follow-up.")
    total = len(st.session_state.notepad_items)
    done = sum(bool(item.get("done")) for item in st.session_state.notepad_items)
    html(f'<div class="notepad-summary"><span><strong>{total - done}</strong> Open</span>'
         f'<span><strong>{done}</strong> Completed</span><span><strong>{total}</strong> Total notes</span></div>')

    show_open_only = st.toggle("Show open only", value=True, key="notepad_open_only")

    visible_items = [
        n for n in st.session_state.notepad_items
        if (not show_open_only) or (not n.get("done", False))
    ]

    if not visible_items:
        empty_state(
            "All caught up" if total else "Every storyline starts somewhere",
            "Turn off the open-only filter to see your completed notes." if total else
            "Add a follow-up from the Event Generator. Your season notes will be waiting here.",
        )
    else:
        for item in visible_items:
            iid = item.get("id")
            done_key = f"note_done_{iid}"

            with st.container(border=True):
                cols = st.columns([0.09, 0.73, 0.18])
                with cols[0]:
                    st.checkbox(
                        "Done",
                        value=item.get("done", False),
                        key=done_key,
                        label_visibility="collapsed",
                        on_change=sync_notepad_done,
                        args=(iid,)
                    )
                with cols[1]:
                    due_txt = item.get("due", "")
                    phase_txt = item.get("phase", "Any")
                    title_class = "note-title done" if item.get("done") else "note-title"
                    meta_line = f"Review {due_txt}"
                    if phase_txt and phase_txt != "Any":
                        meta_line += f" · {phase_txt}"
                    html(f'<p class="{title_class}">{escape(str(item.get("title", "")))}</p>'
                         f'<p class="note-meta">{escape(meta_line)}</p>')
                    if item.get("details"):
                        html(f'<p class="note-details">{escape(str(item["details"]))}</p>')
                with cols[2]:
                    st.button("Remove", key=f"note_remove_{iid}", use_container_width=True, on_click=remove_notepad_item, args=(iid,))


def render_notepad_adder():
    section_heading("02", "Keep the story going", "Save a follow-up to your event notepad.", panel=True)
    html('<div class="composer-tip">Generated events fill in the details for you. Add a review date to keep temporary changes on your radar.</div>')

    if "notepad_draft_item_pending" in st.session_state:
        st.session_state.notepad_draft_item = st.session_state.pop("notepad_draft_item_pending")
    if "notepad_draft_details_pending" in st.session_state:
        st.session_state.notepad_draft_details = st.session_state.pop("notepad_draft_details_pending")
    if "notepad_draft_due_pending" in st.session_state:
        st.session_state.notepad_draft_due = st.session_state.pop("notepad_draft_due_pending")
    if "notepad_draft_phase_pending" in st.session_state:
        st.session_state.notepad_draft_phase = st.session_state.pop("notepad_draft_phase_pending")

    if st.session_state.get("notepad_draft_phase") not in (["Any"] + phases):
        st.session_state.notepad_draft_phase = "Any"

    st.text_input("Note title", key="notepad_draft_item", placeholder="e.g. Review the starting rotation")
    st.text_area("Details", key="notepad_draft_details", placeholder="What changed? What needs a follow-up?", height=145)
    st.date_input("Review date", key="notepad_draft_due")
    st.selectbox("Related phase", ["Any"] + phases, key="notepad_draft_phase")
    st.button("Add to Notepad", key="add_notepad_item", use_container_width=True, type="primary", on_click=handle_add_notepad_item)
    clear_cols = st.columns(2)
    with clear_cols[0]:
        st.button("Clear title", key="clear_title", use_container_width=True, on_click=handle_clear_title)
    with clear_cols[1]:
        st.button("Clear details", key="clear_details", use_container_width=True, on_click=handle_clear_details)


def roll_event_for_phase(phase_name: str):
    recent_titles = set()
    event = weighted_random_event(
        EVENTS[phase_name],
        st.session_state.event_weights,
        recent_titles
    )

    effect_text = event.get("effect", "")
    locked_team = st.session_state.get("locked_team")
    team = locked_team if locked_team else random.choice(TEAMS)
    player_number = random.randint(1, 15)
    intensity = get_event_intensity(event)
    event_roll = generate_event_number(event)

    st.session_state.last_event = {
        "phase": phase_name,
        "title": event["title"],
        "effect": effect_text,
        "team": team,
        "player": f"#{player_number} (Highest Overall)",
        "intensity": intensity,
        "event_roll": event_roll
    }
    prefill_notepad_adder_for_event(st.session_state.last_event)
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

if "notepad_items" not in st.session_state:
    st.session_state.notepad_items = load_notepad_items()

if "notepad_draft_item" not in st.session_state:
    st.session_state.notepad_draft_item = ""

if "notepad_draft_details" not in st.session_state:
    st.session_state.notepad_draft_details = ""

if "notepad_draft_due" not in st.session_state:
    st.session_state.notepad_draft_due = date.today()

if "notepad_draft_phase" not in st.session_state:
    st.session_state.notepad_draft_phase = "Any"

if "notepad_draft_source_key" not in st.session_state:
    st.session_state.notepad_draft_source_key = None

if "selected_phase" not in st.session_state:
    st.session_state.selected_phase = phases[0]

# -----------------------------
# Visual theme and header
# -----------------------------
apply_theme()
render_header(sum(len(events) for events in EVENTS.values()), len(phases))

# -----------------------------
# Weight controls
# -----------------------------
with st.sidebar:
    html('<div class="sidebar-brand">League settings</div><div class="sidebar-kicker">SET THE TONE FOR YOUR SEASON</div>')
    st.markdown("### Event intensity")
    st.caption("Adjust how often each impact tier appears.")

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

app_tabs = st.tabs(["Event Generator", "Notepad"])

with app_tabs[0]:
    generator_col, notepad_col = st.columns([1.8, 1], gap="large")
    with generator_col:
        with st.container(border=True):
            section_heading("01", "Set the scene", "Choose where you are in your season.", panel=True)
            row_size = (len(phases) + 1) // 2
            for row_idx in range(2):
                cols = st.columns(row_size)
                for col_idx in range(row_size):
                    phase_idx = row_idx * row_size + col_idx
                    with cols[col_idx]:
                        if phase_idx < len(phases):
                            phase_name = phases[phase_idx]
                            is_selected = st.session_state.selected_phase == phase_name
                            phase_label = PHASE_BUTTON_LABELS.get(phase_name) or phase_name
                            st.button(
                                phase_label,
                                key=f"phase_btn_{phase_name}",
                                help=phase_name,
                                use_container_width=True,
                                type="primary" if is_selected else "secondary",
                                on_click=set_selected_phase,
                                args=(phase_name,)
                            )
                        else:
                            st.markdown("")

            selected_phase = st.session_state.selected_phase
            phase_events = EVENTS[selected_phase]
            filter_key = f"filter_{selected_phase}"
            st.text_input(
                "Filter events in this phase",
                key=filter_key,
                placeholder="Search scenarios by title or effect…"
            )
            search_term = st.session_state.get(filter_key, "").strip().lower()

            if search_term:
                filtered_events = [
                    ev for ev in phase_events
                    if search_term in ev.get("title", "").lower() or search_term in ev.get("effect", "").lower()
                ]
            else:
                filtered_events = phase_events

            html(f'<div class="phase-summary"><strong>{escape(selected_phase)}</strong>'
                 f'<span><b>{len(filtered_events)}</b> / {len(phase_events)} scenarios available</span></div>')

            if st.button("Generate Event ↗", key=f"gen_{selected_phase}", type="primary", use_container_width=True):
                with st.spinner("Rolling the dice..."):
                    time.sleep(0.4)
                if filtered_events:
                    original_events = EVENTS[selected_phase]
                    EVENTS[selected_phase] = filtered_events
                    roll_event_for_phase(selected_phase)
                    EVENTS[selected_phase] = original_events
                else:
                    st.warning("No events match this filter. Clear or adjust the filter.")
            html('<p class="draw-hint">One draw. A new direction for your season.</p>')

        if st.session_state.last_event:
            render_event(st.session_state.last_event)
        else:
            empty_state("Your next storyline is one draw away", "Choose a season phase, dial in the intensity, and let your league surprise you.")

    with notepad_col:
        with st.container(border=True):
            render_notepad_adder()

with app_tabs[1]:
    render_notepad_items_panel()

html('<footer class="app-footer"><span>MyNBA / The Front Office</span><span>A little unpredictability. A more memorable league.</span></footer>')
