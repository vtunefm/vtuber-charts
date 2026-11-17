import html
import os

import streamlit as st

import ui

st.set_page_config(page_title="VTune FM — VTuber Music Charts", page_icon="📻", layout="wide")
ui.inject()

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

chart = ui.load("data/chart.json")
entries = (chart or {}).get("entries") or []
artists = (chart or {}).get("artists") or []
newest = ui.load("data/newest.json") or {}
playlists = ui.load("data/playlists.json") or {}

panel_size = 0
if os.path.exists("roster.txt"):
    with open("roster.txt", encoding="utf-8") as f:
        panel_size = sum(1 for line in f if line.strip() and not line.startswith("#"))

chart_tab, newest_tab, show_tab, about_tab = st.tabs(
    ["Charts", "Newest Releases", "From the Show", "About"]
)

with chart_tab:
    if entries:
        top = entries[0]
        st.markdown(
            f"<div class='hero'>"
            f"<a href='{ui.WATCH.format(top['video_id'])}' target='_blank' rel='noopener'>"
            f"<img src='{top['thumbnail']}' alt=''></a>"
            f"<div><div class='kicker'>No. 1 this week</div>"
            f"<div class='big'><a href='{ui.WATCH.format(top['video_id'])}' target='_blank' "
            f"rel='noopener'>{html.escape(top['title'] or '')}</a></div>"
            f"<div class='who'>{html.escape(top.get('artists') or '')}</div>"
            f"<div class='gain' style='text-align:left;margin-top:6px'>+{top['views_gained']:,}</div>"
            f"</div></div>",
            unsafe_allow_html=True,
        )

    st.subheader("Music Top 10")
    if chart and entries:
        st.caption(f"Chart week {chart['week_start']} → {chart['week_end']}")
        st.markdown("".join(ui.chart_row(e, len(entries)) for e in entries[:10]), unsafe_allow_html=True)
        st.page_link("pages/1_Music_Top_100.py", label="Full Music Top 100 →")
    else:
        st.info("No chart published yet.")

    st.subheader("Artist Top 10")
    if chart:
        st.caption(f"Chart week {chart['week_start']} → {chart['week_end']}")
        st.caption("One entry per artist · highest-gaining video shown · collab gains credited to all")
    if artists:
        st.markdown("".join(ui.artist_row(a, len(artists)) for a in artists[:10]), unsafe_allow_html=True)
        st.page_link("pages/2_Artist_Top_100.py", label="Full Artist Top 100 →")
    else:
        st.info("No artist chart published yet.")

with newest_tab:
    today_rows = newest.get("today") or []
    yesterday_rows = newest.get("yesterday") or []

    if today_rows or yesterday_rows:
        if today_rows:
            st.subheader("Today's Releases")
            ui.release_block(today_rows)
        if yesterday_rows:
            st.subheader("Yesterday's Releases")
            ui.release_block(yesterday_rows)
    else:
        st.subheader("Recent Releases")
        st.caption("Nothing in the last two days.")
        ui.release_block((newest.get("earlier") or [])[:10])

with show_tab:
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

with about_tab:
    st.subheader("How the chart works")
    st.markdown(
        f"""
**Tracking window.** Views are counted from Monday 00:00 to Saturday 23:59 UTC.
The chart freezes when it publishes. Sunday is the scheduling day.

**What gets ranked.** Position is decided by views *gained* in that window, not by
lifetime totals. An older song competes on the same footing as one released
yesterday, because only the week's movement counts.

**The panel.** The chart covers a curated panel of {panel_size or "several"} VTubers and
VSingers. It is not an open index — artists are added deliberately.

**Eligibility.** Shorts and vertical clips are excluded, as are streams over 15
minutes and videos under 500 views in the window.

**Ties** break toward the older upload.

**Artist chart.** One entry per artist, no matter how many songs they chart. Their
highest-gaining song is shown. On collabs the full gain is credited to every
credited artist.

**Peaks and weeks** are cumulative from the chart's first published week.
        """
    )
    st.caption(
        "Data: YouTube view counts collected daily. Chart placement is automated; "
        "the panel is curated by hand."
    )

st.caption("Views are counted Monday–Saturday and frozen when the chart publishes.")
