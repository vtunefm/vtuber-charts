import json
import os

import streamlit as st

st.set_page_config(page_title="VTune FM — VTuber Music Charts", page_icon="📻", layout="wide")

st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1100px; }
      .rank { font-size: 1.9rem; font-weight: 800; color: #b4b8c4; text-align: right; }
      .song { font-size: 1.05rem; font-weight: 700; margin-bottom: 2px; }
      .who { font-size: .85rem; color: #8b90a0; }
      .gain { font-size: 1rem; font-weight: 700; color: #6ee7a0; text-align: right; }
      .tag { font-size: .7rem; text-transform: uppercase; letter-spacing: .08em;
             color: #8b90a0; border: 1px solid #2a2f3a; border-radius: 3px;
             padding: 1px 5px; margin-left: 6px; }
      .row { border-bottom: 1px solid #1c2029; padding: .55rem 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("VTune FM")
st.caption("Weekly VTuber music charts · Top 10 by views gained, Monday to Saturday")


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


chart = load("data/chart.json")

st.header("Top 10")
if chart and chart.get("entries"):
    st.caption(f"Chart week {chart['week_start']} → {chart['week_end']}")
    for entry in chart["entries"]:
        rank, thumb, body, gain = st.columns([1, 1, 6, 2])
        rank.markdown(f"<div class='rank'>{entry['rank']}</div>", unsafe_allow_html=True)
        thumb.image(entry["thumbnail"], use_container_width=True)
        tag = f"<span class='tag'>{entry['type']}</span>" if entry.get("type") else ""
        body.markdown(
            f"<div class='song'>{entry['title']}{tag}</div>"
            f"<div class='who'>{entry.get('artists') or entry.get('channel') or ''}</div>",
            unsafe_allow_html=True,
        )
        gain.markdown(
            f"<div class='gain'>+{entry['views_gained']:,}</div>"
            f"<div class='who'>{entry['days_covered']}d</div>",
            unsafe_allow_html=True,
        )
else:
    st.info("No chart published yet.")

newest = load("data/newest.json") or {}
today_rows = newest.get("today") or []
yesterday_rows = newest.get("yesterday") or []


def release_block(rows):
    for entry in rows:
        thumb, body, when = st.columns([1, 6, 2])
        thumb.image(entry["thumbnail"], use_container_width=True)
        tag = f"<span class='tag'>{entry['type']}</span>" if entry.get("type") else ""
        body.markdown(
            f"<div class='song'>{entry['title']}{tag}</div>"
            f"<div class='who'>{entry.get('artists') or ''}</div>",
            unsafe_allow_html=True,
        )
        when.markdown(
            f"<div class='who' style='text-align:right'>{entry['published_at']}</div>",
            unsafe_allow_html=True,
        )


if today_rows or yesterday_rows:
    if today_rows:
        st.header("Today's Releases")
        release_block(today_rows)
    if yesterday_rows:
        st.header("Yesterday's Releases")
        release_block(yesterday_rows)
else:
    st.header("Recent Releases")
    st.caption("Nothing in the last two days.")
    release_block((newest.get("earlier") or [])[:10])

st.caption("Views are counted Monday–Saturday and frozen when the chart publishes.")
