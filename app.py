import html
import json
import os

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="VTune FM — VTuber Music Charts", page_icon="📻", layout="wide")

st.markdown(
    """
    <style>
      .stApp { background: #0d0f14; }
      .block-container { padding-top: 1.6rem; max-width: 1100px; }
      .rank { font-size: 1.9rem; font-weight: 800; color: #6b7285; text-align: right; }
      .song { font-size: 1.05rem; font-weight: 700; margin-bottom: 2px; }
      .song a { color: #eceef5; text-decoration: none; }
      .song a:hover { text-decoration: underline; }
      .who { font-size: .85rem; color: #8b90a0; }
      .gain { font-size: 1rem; font-weight: 700; color: #6ee7a0; text-align: right; }
      .tag { font-size: .7rem; text-transform: uppercase; letter-spacing: .08em;
             color: #a78bfa; border: 1px solid #3b2f63; border-radius: 3px;
             padding: 1px 5px; margin-left: 6px; }
      .thumb img { width: 100%; border-radius: 4px; display: block; }
      .tagline { font-size: .95rem; color: #9aa0b4; margin-top: -6px; }
      h1, h2, h3 { color: #f2f3f8; }
      a { color: #a78bfa; }
    </style>
    """,
    unsafe_allow_html=True,
)

logo_col, head_col = st.columns([1, 4])
if os.path.exists("assets/logo.png"):
    logo_col.image("assets/logo.png", use_container_width=True)
with head_col:
    st.title("VTune FM")
    st.markdown(
        "<div class='tagline'>Weekly VTuber music charts · Top 10 by views gained, Monday to Saturday</div>",
        unsafe_allow_html=True,
    )

link_cols = st.columns([1, 1, 6])
link_cols[0].link_button("X · @vtunefm", "https://x.com/vtunefm", use_container_width=True)
link_cols[1].link_button("YouTube", "https://www.youtube.com/@vtunefm-q105", use_container_width=True)

WATCH = "https://www.youtube.com/watch?v={}"


def load(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def thumb_html(entry):
    return (
        f"<a href='{WATCH.format(entry['video_id'])}' target='_blank' rel='noopener'>"
        f"<img src='{entry['thumbnail']}' alt=''></a>"
    )


def title_html(entry):
    tag = f"<span class='tag'>{html.escape(entry['type'])}</span>" if entry.get("type") else ""
    safe = html.escape(entry["title"] or "")
    return (
        f"<div class='song'>"
        f"<a href='{WATCH.format(entry['video_id'])}' target='_blank' rel='noopener'>{safe}</a>"
        f"{tag}</div>"
        f"<div class='who'>{html.escape(entry.get('artists') or '')}</div>"
    )


chart = load("data/chart.json")

st.header("Top 10")
if chart and chart.get("entries"):
    st.caption(f"Chart week {chart['week_start']} → {chart['week_end']}")
    for entry in chart["entries"]:
        rank, thumb, body, gain = st.columns([1, 1, 6, 2])
        rank.markdown(f"<div class='rank'>{entry['rank']}</div>", unsafe_allow_html=True)
        thumb.markdown(thumb_html(entry), unsafe_allow_html=True)
        body.markdown(title_html(entry), unsafe_allow_html=True)
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
        thumb.markdown(thumb_html(entry), unsafe_allow_html=True)
        body.markdown(title_html(entry), unsafe_allow_html=True)
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

playlists = load("data/playlists.json") or {}
st.header("From the Show")
show_cols = st.columns(2)
for col, key in zip(show_cols, ("latest_episode", "heart2heart")):
    pl = playlists.get(key)
    with col:
        if pl:
            st.markdown(f"**{html.escape(pl['title'])}**")
            st.link_button(
                "Open playlist ↗",
                f"https://www.youtube.com/playlist?list={pl['id']}",
                use_container_width=True,
            )
        else:
            st.caption("Playlist not loaded yet.")

st.caption("Views are counted Monday–Saturday and frozen when the chart publishes.")
