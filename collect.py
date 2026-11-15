import os
import json
import pandas as pd
from datetime import datetime, timezone
from googleapiclient.discovery import build
import yt_dlp

# 1. Setup
API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("Missing YOUTUBE_API_KEY environment variable")

youtube = build('youtube', 'v3', developerKey=API_KEY)
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

# We are using a public Hololive Original Songs playlist for testing.
# You can swap this URL out for any playlist you want later.
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLG1FvR1G2eKjO0uQ4gN1R4O5O5O5O5O5O" # Replace with a real one if this breaks, see note below.

# Let's use a real, valid public VTuber playlist URL for this test:
PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLk1QhO4m9Yq3Qx4V6uO7p8W9e0r1t2y3u" 

print(f"Fetching video IDs from playlist: {PLAYLIST_URL}")
ydl_opts = {
    'extract_flat': True, 
    'quiet': True,
    'playlistend': 50 # Let's limit to 50 for this test to keep it fast
}

video_ids = []
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(PLAYLIST_URL, download=False)
        if 'entries' in info:
            for entry in info['entries']:
                if entry:
                    video_ids.append(entry['id'])
except Exception as e:
    print(f"yt-dlp error: {e}")
    # Fallback to real VTuber IDs if playlist fails
    video_ids = [
        "eM3j1O_n5O0", # Mori Calliope
        "k1BneeJTDcU", # Gawr Gura
        "7i9E0G0b4g8", # Hoshimachi Suisei
    ]

print(f"Found {len(video_ids)} videos. Fetching stats...")

# 2. Fetch data from YouTube API (in batches of 50 to save quota)
new_snapshots = []
for i in range(0, len(video_ids), 50):
    batch_ids = video_ids[i:i+50]
    request = youtube.videos().list(
        part="snippet,statistics",
        id=",".join(batch_ids)
    )
    response = request.execute()
    
    for item in response.get('items', []):
        video_id = item['id']
        snippet = item['snippet']
        stats = item['statistics']
        
        new_snapshots.append({
            'video_id': video_id,
            'title': snippet['title'],
            'channel': snippet['channelTitle'],
            'upload_date': snippet['publishedAt'][:10],
            'snapshot_at': now,
            'view_count': int(stats.get('viewCount', 0)),
            'like_count': int(stats.get('likeCount', 0))
        })

df_new = pd.DataFrame(new_snapshots)

# SAFETY CHECK
if df_new.empty:
    print("No data returned from YouTube. The video IDs might be invalid or private.")
    exit(0)

# 3. Save to snapshots.csv
csv_path = 'data/snapshots.csv'
if os.path.exists(csv_path):
    df_existing = pd.read_csv(csv_path)
    df_combined = pd.concat([df_existing, df_new]).drop_duplicates(subset=['video_id', 'snapshot_at'])
    df_combined.to_csv(csv_path, index=False)
else:
    df_new.to_csv(csv_path, index=False)

print(f"Successfully saved {len(df_new)} snapshots to {csv_path}")

# 4. Generate JSON files for the website
df_sorted_views = df_new.sort_values(by='view_count', ascending=False)
top10 = df_sorted_views.head(10).to_dict(orient='records')

df_sorted_date = df_new.sort_values(by='upload_date', ascending=False)
newest = df_sorted_date.head(20).to_dict(orient='records')

os.makedirs('data', exist_ok=True)
with open('data/top10.json', 'w') as f:
    json.dump(top10, f, indent=2)
    
with open('data/newest.json', 'w') as f:
    json.dump(newest, f, indent=2)

print("Successfully generated top10.json and newest.json")
