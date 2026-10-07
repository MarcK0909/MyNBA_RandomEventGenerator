"""Presentation helpers for the MyNBA Streamlit interface."""

from html import escape
from pathlib import Path
from datetime import date

from season_notebook import season_label

import streamlit as st


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def apply_theme() -> None:
    css = Path(__file__).with_name("assets").joinpath("theme.css").read_text(encoding="utf-8")
    html(f"<style>{css}</style>")


def basketball_icon() -> str:
    return '<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><circle cx="16" cy="16" r="12"/><path d="M4 16h24M16 4v24M7.5 7.5c11 5 11 12 17 17M24.5 7.5c-11 5-11 12-17 17"/></svg>'


def render_header(scenario_count: int, phase_count: int, *, show_hero: bool = True) -> None:
    html(f"""
<div class="masthead">
  <div class="brand"><span class="brand-icon">{basketball_icon()}</span><span>MyNBA<span class="brand-divider">/</span><span class="brand-subtitle">The Front Office</span></span></div>
  <span class="edition"><span class="status-dot"></span> YOUR LEAGUE. YOUR STORY.</span>
</div>
""")
    if not show_hero:
        return
    html(f"""
<div class="hero">
  <div class="hero-copy">
    <div class="eyebrow">THE MYNBA STORYTELLING COMPANION</div>
    <h1>A new twist.<br><span class="hero-secondary">A whole new season.</span></h1>
    <p>Turn the unexpected into your next great storyline.</p>
    <div class="hero-stats"><span><b>{scenario_count}</b> scenarios</span><span><b>{phase_count}</b> season phases</span><span>Endless possibilities</span></div>
  </div>
  <div class="court-art" aria-hidden="true">
    <svg viewBox="0 0 400 250" fill="none">
      <rect x="46" y="18" width="310" height="214" rx="5"/>
      <path d="M201 18v214"/><circle cx="201" cy="125" r="31"/>
      <path d="M46 76h57v98H46M356 76h-57v98h57"/>
      <circle cx="103" cy="125" r="29"/><circle cx="299" cy="125" r="29"/>
      <path d="M46 37h23a99 99 0 0 1 0 176H46M356 37h-23a99 99 0 0 0 0 176h23"/>
      <path d="M62 109v32M340 109v32"/><circle cx="69" cy="125" r="6"/><circle cx="333" cy="125" r="6"/>
      <circle class="court-dot" cx="240" cy="79" r="5"/>
      <path class="court-play" d="m235 84-26 29m-7-7 1 13 13-1"/>
      <path class="court-cross" d="m267 159 10 10m0-10-10 10m-139-84 10 10m0-10-10 10"/>
    </svg>
    <span class="court-caption">EVERY SEASON HAS A STORY.</span>
  </div>
</div>
""")


def section_heading(number: str, title: str, subtitle: str = "", *, panel: bool = False, anchor: str = "") -> None:
    style = "section-heading panel-heading" if panel else "section-heading"
    anchor_attribute = f' id="{escape(anchor, quote=True)}"' if anchor else ""
    html(f'<div class="{style}"{anchor_attribute}><span class="step-number">{escape(number)}</span>'
         f'<div><h2>{escape(title)}</h2>'
         f'<p>{escape(subtitle)}</p></div></div>')


def empty_state(title: str, description: str, *, compact: bool = False) -> None:
    style = "empty-state compact" if compact else "empty-state"
    html(f'<div class="{style}"><div class="empty-icon">{basketball_icon()}</div>'
         f'<h3>{escape(title)}</h3><p>{escape(description)}</p></div>')


def render_event(event: dict) -> None:
    intensity = str(event.get("intensity", ""))
    tier = {"Low Impact": "low", "Medium Impact": "medium", "High Impact": "high"}.get(intensity, "high")
    html(f"""
<article class="event-card {tier}">
  <div class="event-meta"><span class="eyebrow">THE LATEST DEVELOPMENT</span><span class="impact-badge {tier}"><span></span>{escape(intensity)}</span></div>
  <h2>{escape(str(event.get('title', '')))}</h2>
  <p class="event-effect">{escape(str(event.get('effect', '')))}</p>
  <div class="event-phase">{escape(str(event.get('phase', '')))}<span> • </span>Generated event</div>
</article>
""")
    entities = [("Team", event.get("team")), ("Team 2", event.get("team_2")), ("Player", event.get("player"))]
    cards = "".join(
        f'<div class="context-card"><span>{label}</span><strong>{escape(str(value))}</strong></div>'
        for label, value in entities if value
    )
    if cards:
        html(f'<div class="context-grid">{cards}</div>')
    if event.get("event_roll"):
        roll = event["event_roll"]
        html(f'<div class="number-draw"><span class="draw-value">{escape(str(roll["value"]))}</span>'
             '<div><strong>Random number draw</strong>'
             f'<p>Automatically rolled · Range {escape(str(roll["label"]))}</p></div></div>')


def render_weight_distribution(weights: dict) -> None:
    total = sum(weights.values()) or 1
    segments = "".join(
        f'<span class="weight-{tier}" style="width:{weights.get(label, 0) / total * 100:.2f}%"></span>'
        for label, tier in [("Low Impact", "low"), ("Medium Impact", "medium"), ("High Impact", "high")]
    )
    html(f'<div class="weight-bar" aria-hidden="true">{segments}</div>'
         '<div class="weight-legend"><span><i class="weight-low"></i>Low</span>'
         '<span><i class="weight-medium"></i>Medium</span><span><i class="weight-high"></i>High</span></div>')


def render_note_card(item: dict) -> None:
    done = bool(item.get("done"))
    kind = "complete" if done else "active"
    status = "Completed" if done else "Open storyline"
    phase = item.get("phase", "Any")
    tags = f'<span class="note-tag">{escape(season_label(item["season"]))}</span>'
    if phase and phase != "Any":
        tags += f'<span class="note-tag">{escape(str(phase))}</span>'
    if item.get("due"):
        try:
            review = date.fromisoformat(item["due"]).strftime("%d %b %Y")
        except (ValueError, TypeError):
            review = str(item["due"])
        tags += f'<span class="note-tag review">Review {escape(review)}</span>'
    details = escape(str(item.get("details", "")))
    html(f'<article class="story-note {kind}"><div class="story-note-top">'
         f'<span class="note-status"><i></i>{status}</span></div>'
         f'<h3>{escape(str(item.get("title", "")))}</h3>'
         + (f'<p class="story-note-details">{details}</p>' if details else "")
         + f'<div class="note-tags">{tags}</div></article>')
