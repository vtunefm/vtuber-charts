import streamlit as st

import ui

st.set_page_config(page_title="Music Top 100 — VTune FM", page_icon="📻", layout="wide")
ui.inject()

st.page_link("app.py", label="← Back")
st.title("Music Top 100")

chart = ui.load("data/chart.json")
entries = (chart or {}).get("entries") or []

if chart and entries:
    st.caption(f"Chart week {chart['week_start']} → {chart['week_end']}")
    st.markdown("".join(ui.chart_row(e, len(entries)) for e in entries), unsafe_allow_html=True)
else:
    st.info("No chart published yet.")
