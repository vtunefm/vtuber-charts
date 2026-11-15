import html
import json
import os

import streamlit as st

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
      .mv { font-size: .8rem; font-weight: 700; }
      .up { color: #6ee7a0; } .down { color: #f87171; }
      .same { color: #6b7285; } .new { color: #fbbf24; letter-spacing: .1em; }
      .stats { font-size: .7rem; color: #7b8194; }
      .chartrow {
        display: grid; grid-template-columns: 48px 100px 1fr 92px 140px;
        gap: 14px; align-items: center; padding: .5rem 0;
        border-bottom: 1px solid #1c2029;
        animation: slide .5s cubic-bezier(.2,.8,.3,1) both;
      }
      @keyframes slide {
        from { opacity: 0; transform: translateX(-48px); }
        to   { opacity: 1; transform: translateX(0); }
      }
      .hero { display: grid; grid-template-columns: 220px 1fr; gap: 20px;
              align-items: center; border: 1px solid #2a2f3a; border-radius: 8px;
              padding: 14px; margin-bottom: 18px; background: #12151c; }
      .hero img { width: 100%; border-radius: 6px; display: block; }
      .hero .kicker { font-size: .7rem; letter-spacing: .18em; color: #fbbf24;
                      text-transform: uppercase; }
      .hero .big { font-size: 1.6rem; font-weight: 800; color: #fff; margin: 4px 0; }
      .hero .big a { color: #fff; text-decoration: none; }
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


def movement(entry):
    m = entry.get("movement")
    last = entry.get("last_week")
    if m == "new":
        return "<span class='mv new'>NEW</span>"
    if m == "up" and last:
        return f"<span class='mv up'>▲{last - entry['rank']}</span>"
    if m == "down" and last:
        return f"<span class='mv down'>▼{entry['rank'] - last}</span>"
    return "<span class='mv same'>=</span>"


def chart_row(entry):
    tag = f"<span class='tag'>{html.escape(entry['type'])}</span>" if entry.get("type") else ""
    url = WATCH.format(entry["video_id"])
    last = entry.get("last_week")
    return (
        f"<div class='chartrow' style='animation-delay:{(20 - entry['rank']) * 0.14:.2f}s'>"
        f"<div class='rank'>{entry['rank']}</div>"
        f"<div class='thumb'><a href='{url}' target='_blank' rel='noopener'>"
        f"<img src='{entry['thumbnail']}' alt=''></a></div>"
        f"<div><div class='song'><a href='{url}' target='_blank' rel='noopener'>"
        f"{html.escape(entry['title'] or '')}</a>{tag}</div>"
        f"<div class='who'>{html.escape(entry.get('artists') or '')}</div></div>"
        f"<div>{movement(entry)}<div class='stats'>LW {last if last else '—'}"
        f" · PK {entry['peak']} · {entry['weeks_on_chart']}w</div></div>"
        f"<div><div class='gain'>+{entry['views_gained']:,}</div>"
        f"<div class='who' style='text-align:right'>{entry['days_covered']}d</div></div>"
        f"</div>"
    )


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
entries = (chart or {}).get("entries") or []

if entries:
    top = entries[0]
    st.markdown(
        f"<div class='hero'>"
        f"<a href='{WATCH.format(top['video_id'])}' target='_blank' rel='noopener'>"
        f"<img src='{top['thumbnail']}' alt=''></a>"
        f"<div><div class='kicker'>No. 1 this week</div>"
        f"<div class='big'><a href='{WATCH.format(top['video_id'])}' target='_blank' "
        f"rel='noopener'>{html.escape(top['title'] or '')}</a></div>"
        f"<div class='who'>{html.escape(top.get('artists') or '')}</div>"
        f"<div class='gain' style='text-align:left;margin-top:6px'>+{top['views_gained']:,}</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )

st.header("Top 10")
if chart and entries:
    st.caption(f"Chart week {chart['week_start']} → {chart['week_end']}")
    st.markdown("".join(chart_row(e) for e in entries[:10]), unsafe_allow_html=True)
else:
    st.info("No chart published yet.")

if len(entries) > 10:
    st.subheader("Bubbling Under")
    st.markdown("".join(chart_row(e) for e in entries[10:20]), unsafe_allow_html=True)

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
            url = f"https://www.youtube.com/playlist?list={pl['id']}"
            if pl.get("thumb"):
                st.markdown(
                    f"<a href='{url}' target='_blank' rel='noopener'>"
                    f"<img src='{pl['thumb']}' style='width:100%;border-radius:6px;display:block'>"
                    f"</a>",
                    unsafe_allow_html=True,
                )
            st.markdown(f"**{html.escape(pl['title'])}**")
            st.link_button("Open playlist ↗", url, use_container_width=True)
        else:
            st.caption("Playlist not loaded yet.")

st.caption("Views are counted Monday–Saturday and frozen when the chart publishes.")
