import streamlit as st
import pandas as pd
import json

st.set_page_config(page_title="VTuber Music Charts", page_icon="🎵", layout="wide")
st.title("🎵 VTuber Music Charts")
st.markdown("Tracking the top hits and newest releases in the VTuber scene.")

try:
    with open("data/top10.json", "r") as f:
        top10_data = json.load(f)
    with open("data/newest.json", "r") as f:
        newest_data = json.load(f)
except FileNotFoundError:
    st.error("Data files not found. Please run the GitHub Action first.")
    st.stop()

df_top10 = pd.DataFrame(top10_data)
df_newest = pd.DataFrame(newest_data)

# --- Top 10 Section ---
st.header("🔥 Top 10 by Weekly Views")
if not df_top10.empty:
    # We changed 'view_count' to 'weekly_views' here
    df_display = df_top10[['title', 'channel', 'weekly_views']].copy()
    df_display.columns = ['Song Title', 'Channel', 'Views Gained This Week']
    
    # Format with commas
    df_display['Views Gained This Week'] = df_display['Views Gained This Week'].apply(lambda x: f"{int(x):,}")
    
    st.dataframe(df_display, use_container_width=True, hide_index=True)
else:
    st.write("No data available.")

# --- Newest Releases Section ---
st.header("🆕 Newest Releases")
if not df_newest.empty:
    df_new_display = df_newest[['upload_date', 'title', 'channel']].copy()
    df_new_display.columns = ['Release Date', 'Song Title', 'Channel']
    
    st.dataframe(df_new_display, use_container_width=True, hide_index=True)
else:
    st.write("No data available.")

st.caption("Data automatically updated daily via GitHub Actions.")
