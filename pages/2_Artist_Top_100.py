import streamlit as st

import ui

st.set_page_config(page_title="Artist Top 100 — VTune FM", page_icon="📻", layout="wide")
ui.inject()

st.page_link("app.py", label="← Back")
st.title("Artist Top 100")
st.caption("One entry per artist · links open the artist's channel · collab gains credited to all")

chart = ui.load("data/chart.json")
artists = (chart or {}).get("artists") or []

if chart:
    st.caption(f"Chart week {chart['week_start']} → {chart['week_end']}")
if artists:
    st.markdown("".join(ui.artist_row(a, len(artists)) for a in artists), unsafe_allow_html=True)
else:
    st.info("No artist chart published yet.")
