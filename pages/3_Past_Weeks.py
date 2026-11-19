import json
import os

import streamlit as st

import ui

st.set_page_config(page_title="Past Weeks — VTune FM", page_icon="📻", layout="wide")
ui.inject()

st.title("Past Weeks")
st.caption("Each week's Top 10 music, frozen when the week closed.")

HISTORY = "data/history"


def weeks():
    if not os.path.isdir(HISTORY):
        return []
    return sorted(
        (n[:-5] for n in os.listdir(HISTORY) if n.endswith(".json")),
        reverse=True,
    )


found = weeks()
if not found:
    st.info("No completed weeks yet. The first record lands when this week closes on Saturday.")
else:
    for week in found:
        try:
            with open(os.path.join(HISTORY, f"{week}.json"), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        rows = data.get("top10") or []
        if not rows:
            continue
        st.subheader(f"Week ending {week}")
        st.markdown(
            "".join(ui.chart_row(e, len(rows)) for e in rows),
            unsafe_allow_html=True,
        )
        st.divider()
