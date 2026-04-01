import streamlit as st  # type: ignore
import json
import random
import time
from datetime import date, datetime
from pathlib import Path
from constants import DEFAULT_EVENT_WEIGHTS, PHASE_ICONS, TEAMS
from event_engine import (
    generate_event_number,
    get_event_intensity,
    load_events,
    weighted_random_event,
)

# -----------------------------
# Page config
# -----------------------------
st.set_page_config(
    page_title="MyNBA Random Event Generator",
    page_icon="🏀",
    layout="centered"
)

# -----------------------------
# Load events
# -----------------------------
EVENTS = load_events("events.json")
phases = list(EVENTS.keys())
NOTEPAD_PATH = Path("event_notepad.json")


@st.cache_resource
def get_firestore_doc_ref():
    try:
        firebase_cfg = st.secrets.get("firebase")
        if not firebase_cfg:
            return None

        import firebase_admin  # type: ignore
        from firebase_admin import credentials, firestore  # type: ignore

        if not firebase_admin._apps:
            firebase_dict = dict(firebase_cfg)
            firebase_admin.initialize_app(credentials.Certificate(firebase_dict))

        db = firestore.client()
        collection_name = st.secrets.get("firestore_collection", "mynba")
        document_id = st.secrets.get("firestore_document", "event_notepad")
        return db.collection(collection_name).document(document_id)
    except Exception:
        return None


def load_notepad_items():
    doc_ref = get_firestore_doc_ref()
    if doc_ref is not None:
        try:
            snapshot = doc_ref.get()
            if snapshot.exists:
                payload = snapshot.to_dict() or {}
                items = payload.get("items", [])
                if isinstance(items, list):
                    return items
            return []
        except Exception:
            pass

    if not NOTEPAD_PATH.exists():
        return []

    try:
        with NOTEPAD_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def save_notepad_items(items):
    doc_ref = get_firestore_doc_ref()
    if doc_ref is not None:
        try:
            doc_ref.set(
                {
                    "items": items,
                    "updated_at": datetime.now().isoformat(timespec="seconds")
                },
                merge=True
            )
            return
        except Exception:
            pass

    with NOTEPAD_PATH.open("w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)


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

    st.session_state.notepad_draft_item = f"Track: {title}" + (f" ({target_text})" if target_text else "")
    st.session_state.notepad_draft_details = (
        f"Event: {title}\n"
        f"Effect: {effect}" + (f"\nTarget: {target_text}" if target_text else "")
    )
    st.session_state.notepad_draft_due = date.today()
    st.session_state.notepad_draft_phase = phase if phase in phases else "Any"
    st.session_state.notepad_draft_source_key = src_key


def render_notepad_items_panel():
    st.markdown("### 📝 Event Notepad")
    st.caption("Open items are shown here while you manage event changes.")

    show_open_only = st.toggle("Show open only", value=True, key="notepad_open_only")

    notes_dirty = False
    remove_ids = []

    visible_items = [
        n for n in st.session_state.notepad_items
        if (not show_open_only) or (not n.get("done", False))
    ]

    if not visible_items:
        st.caption("No notepad items yet.")
    else:
        for item in visible_items:
            iid = item.get("id")
            done_key = f"note_done_{iid}"

            cols = st.columns([0.14, 0.62, 0.24])
            with cols[0]:
                is_done = st.checkbox("Done", value=item.get("done", False), key=done_key, label_visibility="collapsed")
            with cols[1]:
                due_txt = item.get("due", "")
                phase_txt = item.get("phase", "Any")
                st.markdown(f"**{item.get('title', '')}**")
                meta_line = f"Due: {due_txt}"
                if phase_txt and phase_txt != "Any":
                    meta_line += f" • {phase_txt}"
                st.caption(meta_line)
                if item.get("details"):
                    st.caption(item.get("details"))
            with cols[2]:
                if st.button("Remove", key=f"note_remove_{iid}"):
                    remove_ids.append(iid)

            if is_done != item.get("done", False):
                item["done"] = is_done
                notes_dirty = True

    if remove_ids:
        st.session_state.notepad_items = [n for n in st.session_state.notepad_items if n.get("id") not in set(remove_ids)]
        notes_dirty = True

    if notes_dirty:
        save_notepad_items(st.session_state.notepad_items)


def render_notepad_adder():
    st.markdown("### Add Notepad Item")
    st.caption("Track non-permanent changes and when to revert them.")

    if st.session_state.get("notepad_draft_phase") not in (["Any"] + phases):
        st.session_state.notepad_draft_phase = "Any"

    # Handle clear button logic
    if st.session_state.get("_clear_title_flag"):
        st.session_state.notepad_draft_item = ""
        st.session_state._clear_title_flag = False

    if st.session_state.get("_clear_details_flag"):
        st.session_state.notepad_draft_details = ""
        st.session_state._clear_details_flag = False

    title_col, title_clear = st.columns([0.80, 0.20])
    with title_col:
        note_title = st.text_input("Item", key="notepad_draft_item", placeholder="Example: Revert SG back to bench role")
    with title_clear:
        if st.button("Clear", key="clear_title"):
            st.session_state._clear_title_flag = True
            st.rerun()

    details_col, details_clear = st.columns([0.80, 0.20])
    with details_col:
        note_details = st.text_area("Details", key="notepad_draft_details", placeholder="What changed and what to undo")
    with details_clear:
        if st.button("Clear", key="clear_details"):
            st.session_state._clear_details_flag = True
            st.rerun()

    with st.form("notepad_add_form", clear_on_submit=False):
        note_due = st.date_input("Due / Review Date", key="notepad_draft_due")
        note_phase = st.selectbox("Related Phase", ["Any"] + phases, key="notepad_draft_phase")
        submitted = st.form_submit_button("Add to Notepad")

        if submitted:
            if note_title.strip():
                new_item = {
                    "id": int(datetime.now().timestamp() * 1000),
                    "title": note_title.strip(),
                    "details": note_details.strip(),
                    "due": note_due.isoformat(),
                    "phase": note_phase,
                    "done": False,
                    "created_at": datetime.now().isoformat(timespec="seconds")
                }
                st.session_state.notepad_items.insert(0, new_item)
                save_notepad_items(st.session_state.notepad_items)
                st.toast("Notepad item added.")
            else:
                st.warning("Please add a title for the notepad item.")


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

# -----------------------------
# CSS
# -----------------------------
st.markdown("""
<style>
body {
    background-color: #0f172a;
}
.card {
    background: linear-gradient(145deg, #111827, #0b1220);
    border-left: 4px solid #ef4444;
    padding: 1.2rem;
    border-radius: 14px;
    margin-top: 1rem;
    box-shadow: 0 10px 25px rgba(0,0,0,0.35);
}
.pill {
    display: inline-block;
    padding: 4px 10px;
    border-radius: 999px;
    background-color: #1f2933;
    font-size: 0.8rem;
    margin-right: 6px;
}
.small {
    color: #9ca3af;
    font-size: 0.85rem;
}
hr {
    border: none;
    height: 1px;
    background: linear-gradient(to right, transparent, #374151, transparent);
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# Header
# -----------------------------
st.markdown(
    "<h1 style='text-align:center;'>🏀 MyNBA Random Event Generator</h1>",
    unsafe_allow_html=True
)
st.markdown(
    "<p class='small' style='text-align:center;'>Offline companion for MyNBA storytelling</p>",
    unsafe_allow_html=True
)

st.write("")

# -----------------------------
# Weight controls
# -----------------------------
with st.sidebar:
    st.markdown("### 🎛️ Event Weighting")
    st.caption("Adjust how often each impact tier appears.")

    low_w = st.slider("Low Impact", min_value=0, max_value=100, value=st.session_state.event_weights["Low Impact"], step=5)
    med_w = st.slider("Medium Impact", min_value=0, max_value=100, value=st.session_state.event_weights["Medium Impact"], step=5)
    high_w = st.slider("High Impact", min_value=0, max_value=100, value=st.session_state.event_weights["High Impact"], step=5)
    chaos_w = st.slider("Chaos", min_value=0, max_value=100, value=st.session_state.event_weights["Chaos"], step=5)

    weight_total = low_w + med_w + high_w + chaos_w
    if weight_total == 0:
        st.warning("All tiers are set to 0. Using default weighting.")
        st.session_state.event_weights = DEFAULT_EVENT_WEIGHTS.copy()
    else:
        st.session_state.event_weights = {
            "Low Impact": low_w,
            "Medium Impact": med_w,
            "High Impact": high_w,
            "Chaos": chaos_w
        }

    st.caption(f"Current total weight: {sum(st.session_state.event_weights.values())}")

    st.markdown("---")
    st.markdown("### ⚙️ UX Controls")
    use_locked_team = st.toggle("Lock team context", value=st.session_state.locked_team is not None)
    if use_locked_team:
        st.session_state.locked_team = st.selectbox("Locked team", TEAMS, index=0)
    else:
        st.session_state.locked_team = None

    if st.button("🗑️ Clear last event"):
        st.session_state.last_event = None
        st.toast("Last event cleared.")

    st.markdown("---")
    st.markdown("### 🔢 Event Number Generator")
    st.caption("Auto-rolls whenever an event asks to draw a random number.")

    if st.session_state.last_event and st.session_state.last_event.get("event_roll"):
        roll = st.session_state.last_event["event_roll"]
        st.success(f"Last auto-roll: {roll['value']} (range {roll['label']})")
    else:
        st.caption("No number-roll event generated yet.")

main_col, notes_col = st.columns([0.68, 0.32], gap="large")

with notes_col:
    render_notepad_items_panel()

with main_col:
    # -----------------------------
    # Phase selection
    # -----------------------------
    tabs = st.tabs([f"{PHASE_ICONS.get(p,'')} {p}" for p in phases])

    selected_phase = None

    for i, tab in enumerate(tabs):
        with tab:
            selected_phase = phases[i]

            phase_events = EVENTS[selected_phase]

            filter_key = f"filter_{selected_phase}"
            search_term = st.session_state.get(filter_key, "").strip().lower()

            if search_term:
                filtered_events = [
                    ev for ev in phase_events
                    if search_term in ev.get("title", "").lower() or search_term in ev.get("effect", "").lower()
                ]
            else:
                filtered_events = phase_events

            st.markdown(
                f"<span class='pill'>{PHASE_ICONS.get(selected_phase,'')} {selected_phase}</span>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<span class='small'>{len(filtered_events)} / {len(phase_events)} scenarios available</span>",
                unsafe_allow_html=True
            )

            st.write("")

            if st.button("🎲 Generate Event", key=f"gen_{selected_phase}"):
                with st.spinner("Rolling the dice..."):
                    time.sleep(0.4)
                if filtered_events:
                    original_events = EVENTS[selected_phase]
                    EVENTS[selected_phase] = filtered_events
                    roll_event_for_phase(selected_phase)
                    EVENTS[selected_phase] = original_events
                else:
                    st.warning("No events match this filter. Clear or adjust the filter.")

            st.write("")
            st.text_input(
                "Filter events in this phase",
                key=filter_key,
                placeholder="Type keyword (title or effect)..."
            )

    # -----------------------------
    # Display event
    # -----------------------------
    if st.session_state.last_event:
        e = st.session_state.last_event

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown("## 🎲 Generated Event")

        st.markdown(f"""
        <div class="card">
            <span class="pill">🔥 {e['intensity']}</span>
            <h3>📌 {e['title']}</h3>
            <p>{e['effect']}</p>
        </div>
        """, unsafe_allow_html=True)

        entity_cards = []
        if e.get("team"):
            entity_cards.append(("🏀 Team", e["team"]))
        if e.get("player"):
            entity_cards.append(("👤 Player", e["player"]))

        if entity_cards:
            cols = st.columns(len(entity_cards))
            for col, (label, value) in zip(cols, entity_cards):
                with col:
                    st.markdown(f"""
                    <div class="card">
                        <h4>{label}</h4>
                        <p>{value}</p>
                    </div>
                    """, unsafe_allow_html=True)

        if e.get("event_roll"):
            roll = e["event_roll"]
            st.markdown(f"""
            <div class="card">
                <h4>🔢 Random Number Draw</h4>
                <p><strong>{roll['value']}</strong> (Range {roll['label']})</p>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)
    render_notepad_adder()

    # # Copy-friendly block
    # roll_line = ""
    # if e.get("event_roll"):
    #     roll_line = f"\nRandom Draw: {e['event_roll']['value']} (Range {e['event_roll']['label']})"

    # st.code(
    #     f"{e['title']}\n\n{e['effect']}\n\nTeam: {e['team']}\nPlayer: {e['player']}{roll_line}",
    #     language="text"
    # )
