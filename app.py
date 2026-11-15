import streamlit as st
import pandas as pd
import json

# 1. Page configuration
st.set_page_config(page_title="VTuber Music Charts", page_icon="🎵", layout="wide")

st.title("🎵 VTuber Music Charts")
st.markdown("Tracking the top hits and newest releases in the VTuber scene.")

# 2. Load the data
# We use a try/except block in case the data hasn't been generated yet
try:
    with open("data/top10.json", "r") as f:
        top10_data = json.load(f)
    with open("data/newest.json", "r") as f:
        newest_data = json.load(f)
except FileNotFoundError:
    st.error("Data files not found. Please run the GitHub Action first to generate the data.")
    st.stop()

# Convert to Pandas DataFrames for easy display
df_top10 = pd.DataFrame(top10_data)
df_newest = pd.DataFrame(newest_data)

# 3. Display Top 10
st.header("🔥 Top 10 by Views")
if not df_top10.empty:
    # Reorder and rename columns for display
    df_display = df_top10[['title', 'channel', 'view_count']].copy()
    df_display.columns = ['Song Title', 'Channel', 'Total Views']
    
    # Format view counts with commas (e.g., 1,000,000)
    df_display['Total Views'] = df_display['Total Views'].apply(lambda x: f"{x:,}")
    
    # Display as a table (hide the index numbers)
    st.dataframe(df_display, use_container_width=True, hide_index=True)
else:
    st.write("No data available.")

# 4. Display Newest Releases
st.header("🆕 Newest Releases")
if not df_newest.empty:
    df_new_display = df_newest[['upload_date', 'title', 'channel']].copy()
    df_new_display.columns = ['Release Date', 'Song Title', 'Channel']
    
    st.dataframe(df_new_display, use_container_width=True, hide_index=True)
else:
    st.write("No data available.")

# 5. Footer
st.caption("Data automatically updated daily via GitHub Actions.")
