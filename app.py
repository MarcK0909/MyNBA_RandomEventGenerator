import streamlit as st
import json
import random
import time
import re


VALID_INTENSITIES = {"Low Impact", "Medium Impact", "High Impact", "Chaos"}


def infer_intensity(event: dict) -> str:
    text = f"{event.get('title', '')} {event.get('effect', '')}".lower()

    chaos_markers = [
        "forced to retire", "entire season", "100–200 days", "100-200 days",
        "must be traded", "superstar trade demand", "fire gm and head coach",
        "set all attributes to 25", "tear", "acl", "350 days"
    ]
    high_markers = [
        "trade", "fire coach", "suspend", "90 days", "severe injury",
        "out 30 days", "force loss", "force win", "decline", "decrease all"
    ]
    medium_markers = [
        "one week", "5 games", "minutes restriction", "offensive consistency",
        "defensive consistency", "potential by 5", "durability"
    ]

    if any(marker in text for marker in chaos_markers):
        return "Chaos"
    if any(marker in text for marker in high_markers):
        return "High Impact"
    if any(marker in text for marker in medium_markers):
        return "Medium Impact"
    return "Low Impact"


def weighted_random_event(events: list, weight_map: dict, recent_titles: set) -> dict:
    weighted_pool = []
    weights = []

    for event in events:
        intensity = get_event_intensity(event)
        base_weight = max(weight_map.get(intensity, 1), 0.0)
        if base_weight == 0:
            continue

        if event.get("title") in recent_titles:
            base_weight *= 0.35

        weighted_pool.append(event)
        weights.append(base_weight)

    if not weighted_pool:
        return random.choice(events)

    return random.choices(weighted_pool, weights=weights, k=1)[0]


def extract_draw_range(effect_text: str):
    if not effect_text:
        return None

    # Supports variations like:
    # "Draw a number between 1 and 30"
    # "draw a number between 1-30"
    match = re.search(r"draw\s+a\s+number\s+between\s+(\d+)\s*(?:and|-)\s*(\d+)", effect_text, re.IGNORECASE)
    if not match:
        return None

    start = int(match.group(1))
    end = int(match.group(2))
    if start > end:
        start, end = end, start
    return (start, end)


def _roll_payload(start: int, end: int):
    value = random.randint(start, end)
    return {
        "value": value,
        "start": start,
        "end": end,
        "label": f"{start}-{end}"
    }


def generate_event_number(event: dict):
    # Preferred structured metadata path
    roll_type = event.get("roll_type")
    if roll_type == "range":
        roll_min = event.get("roll_min")
        roll_max = event.get("roll_max")
        if isinstance(roll_min, int) and isinstance(roll_max, int):
            start, end = (roll_min, roll_max) if roll_min <= roll_max else (roll_max, roll_min)
            return _roll_payload(start, end)

    # Backward-compatible text parsing fallback
    effect_text = event.get("effect", "")
    range_tuple = extract_draw_range(effect_text)
    if not range_tuple:
        return None

    start, end = range_tuple
    return _roll_payload(start, end)


def get_event_intensity(event: dict) -> str:
    impact = event.get("impact")
    if isinstance(impact, str) and impact in VALID_INTENSITIES:
        return impact
    return infer_intensity(event)


def requires_team_draw(event: dict) -> bool:
    requires_team = event.get("requires_team")
    if isinstance(requires_team, bool):
        return requires_team

    effect_text = event.get("effect", "")
    return "team drawn" in effect_text.lower()


def requires_player_draw(event: dict) -> bool:
    requires_player = event.get("requires_player")
    if isinstance(requires_player, bool):
        return requires_player

    effect_text = event.get("effect", "")
    return "player drawn" in effect_text.lower()

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
with open("events.json", "r") as f:
    EVENTS = json.load(f)

# -----------------------------
# Constants
# -----------------------------
PHASE_ICONS = {
    "Regular Season": "🏀",
    "Regular Season Post-Deadline": "⏳",
    "Trade Deadline": "🔁",
    "Playoffs": "🏆",
    "Draft Combine": "📏",
    "Draft": "📋",
    "Free Agency": "💼",
    "Summer League": "🌞",
    "Training Camp": "🏋️",
    "Coaching Carousel": "🎩"
}

INTENSITY_TAGS = ["Low Impact", "Medium Impact", "High Impact", "Chaos"]

TEAMS = [
    "Atlanta Hawks", "Boston Celtics", "Brooklyn Nets", "Charlotte Hornets",
    "Chicago Bulls", "Cleveland Cavaliers", "Dallas Mavericks", "Denver Nuggets",
    "Detroit Pistons", "Golden State Warriors", "Houston Rockets", "Indiana Pacers",
    "LA Clippers", "Los Angeles Lakers", "Memphis Grizzlies", "Miami Heat",
    "Milwaukee Bucks", "Minnesota Timberwolves", "New Orleans Pelicans",
    "New York Knicks", "Oklahoma City Thunder", "Orlando Magic",
    "Philadelphia 76ers", "Phoenix Suns", "Portland Trail Blazers",
    "Sacramento Kings", "San Antonio Spurs", "Toronto Raptors",
    "Utah Jazz", "Washington Wizards", "Austin Bullets", "Seattle Supersonics "
]

# -----------------------------
# Session state
# -----------------------------
if "history" not in st.session_state:
    st.session_state.history = []

if "last_event" not in st.session_state:
    st.session_state.last_event = None

if "event_weights" not in st.session_state:
    st.session_state.event_weights = {
        "Low Impact": 45,
        "Medium Impact": 35,
        "High Impact": 15,
        "Chaos": 5
    }

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
        st.session_state.event_weights = {
            "Low Impact": 45,
            "Medium Impact": 35,
            "High Impact": 15,
            "Chaos": 5
        }
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
