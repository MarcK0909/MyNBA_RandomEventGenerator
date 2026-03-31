import streamlit as st
import random
import time
from constants import DEFAULT_EVENT_WEIGHTS, PHASE_ICONS, TEAMS
from event_engine import (
    generate_event_number,
    get_event_intensity,
    load_events,
    requires_player_draw,
    requires_team_draw,
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

# -----------------------------
# Session state
# -----------------------------
if "history" not in st.session_state:
    st.session_state.history = []

if "last_event" not in st.session_state:
    st.session_state.last_event = None

if "event_weights" not in st.session_state:
    st.session_state.event_weights = DEFAULT_EVENT_WEIGHTS.copy()

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
    st.markdown("### 🔢 Event Number Generator")
    st.caption("Auto-rolls whenever an event asks to draw a random number.")

    if st.session_state.last_event and st.session_state.last_event.get("event_roll"):
        roll = st.session_state.last_event["event_roll"]
        st.success(f"Last auto-roll: {roll['value']} (range {roll['label']})")
    else:
        st.caption("No number-roll event generated yet.")

# -----------------------------
# Phase selection
# -----------------------------
phases = list(EVENTS.keys())
tabs = st.tabs([f"{PHASE_ICONS.get(p,'')} {p}" for p in phases])

selected_phase = None

for i, tab in enumerate(tabs):
    with tab:
        selected_phase = phases[i]

        st.markdown(
            f"<span class='pill'>{PHASE_ICONS.get(selected_phase,'')} {selected_phase}</span>",
            unsafe_allow_html=True
        )
        st.markdown(f"<span class='small'>{len(EVENTS[selected_phase])} scenarios available</span>", unsafe_allow_html=True)

        st.write("")

        if st.button("🎲 Generate Event", key=f"gen_{selected_phase}"):
            with st.spinner("Rolling the dice..."):
                time.sleep(0.4)

            recent_titles = {h["title"] for h in st.session_state.history[:3]}
            event = weighted_random_event(
                EVENTS[selected_phase],
                st.session_state.event_weights,
                recent_titles
            )
            effect_text = event.get("effect", "")
            team = random.choice(TEAMS) if requires_team_draw(event) else None
            player_number = random.randint(1, 15) if requires_player_draw(event) else None
            intensity = get_event_intensity(event)
            event_roll = generate_event_number(event)

            st.session_state.last_event = {
                "phase": selected_phase,
                "title": event["title"],
                "effect": effect_text,
                "team": team,
                "player": f"#{player_number} (Highest Overall)" if player_number else None,
                "intensity": intensity,
                "event_roll": event_roll
            }

            st.session_state.history.insert(0, st.session_state.last_event)
            st.session_state.history = st.session_state.history[:5]

            st.toast("🏀 New event generated!", icon="🎲")

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

    # # Copy-friendly block
    # roll_line = ""
    # if e.get("event_roll"):
    #     roll_line = f"\nRandom Draw: {e['event_roll']['value']} (Range {e['event_roll']['label']})"

    # st.code(
    #     f"{e['title']}\n\n{e['effect']}\n\nTeam: {e['team']}\nPlayer: {e['player']}{roll_line}",
    #     language="text"
    # )

# -----------------------------
# History
# -----------------------------
if st.session_state.history:
    with st.expander("🕘 Recent Events"):
        for h in st.session_state.history:
            context_bits = []
            if h.get("team"):
                context_bits.append(h["team"])
            if h.get("player"):
                context_bits.append(h["player"])

            context_text = " | ".join(context_bits)
            if context_text:
                st.markdown(f"• **{h['title']}** — {context_text} ({h['phase']})")
            else:
                st.markdown(f"• **{h['title']}** — ({h['phase']})")
