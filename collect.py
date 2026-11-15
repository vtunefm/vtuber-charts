import os
import json
import pandas as pd
from datetime import datetime, timezone
from googleapiclient.discovery import build
import yt_dlp

# 1. Setup
API_KEY = os.environ.get("YOUTUBE_API_KEY")
youtube = build('youtube', 'v3', developerKey=API_KEY)
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

# Search for 50 real VTuber videos
print("Searching YouTube for VTuber songs...")
ydl_opts = {'extract_flat': True, 'quiet': True, 'playlistend': 50}
video_ids = []
try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info("ytsearch50:hololive original song", download=False)
        for entry in info.get('entries', []):
            if entry and 'id' in entry:
                video_ids.append(entry['id'])
except Exception as e:
    print(f"yt-dlp search failed: {e}")
    exit(1)

# 2. Fetch data from YouTube API
new_snapshots = []
for i in range(0, len(video_ids), 50):
    batch_ids = video_ids[i:i+50]
    request = youtube.videos().list(part="snippet,statistics", id=",".join(batch_ids))
    response = request.execute()
    
    for item in response.get('items', []):
        new_snapshots.append({
            'video_id': item['id'],
            'title': item['snippet']['title'],
            'channel': item['snippet']['channelTitle'],
            'upload_date': item['snippet']['publishedAt'][:10],
            'snapshot_at': now,
            'view_count': int(item['statistics'].get('viewCount', 0)),
            'like_count': int(item['statistics'].get('likeCount', 0))
        })

df_new = pd.DataFrame(new_snapshots)

# 3. Save to snapshots.csv
csv_path = 'data/snapshots.csv'
if os.path.exists(csv_path):
    df_existing = pd.read_csv(csv_path)
    df_combined = pd.concat([df_existing, df_new])
else:
    df_combined = df_new

df_combined.to_csv(csv_path, index=False)

# 4. Calculate Weekly Views
df_combined['snapshot_at'] = pd.to_datetime(df_combined['snapshot_at'])
latest_time = df_combined['snapshot_at'].max()
one_week_ago = latest_time - pd.Timedelta(days=7)

# Get the most recent snapshot (today)
df_latest = df_combined[df_combined['snapshot_at'] == latest_time].copy()

# Get the snapshot from ~7 days ago
df_old = df_combined[df_combined['snapshot_at'] <= one_week_ago]
if not df_old.empty:
    # Keep only the most recent snapshot from before 7 days ago for each video
    df_old = df_old.sort_values('snapshot_at').groupby('video_id').last().reset_index()
    # Merge the old views into the latest dataframe
    df_latest = df_latest.merge(df_old[['video_id', 'view_count']], on='video_id', how='left', suffixes=('', '_old'))
    df_latest['view_count_old'] = df_latest['view_count_old'].fillna(0)
else:
    # If we don't have 7 days of history yet, assume they started at 0
    df_latest['view_count_old'] = 0

# Calculate the difference
df_latest['weekly_views'] = df_latest['view_count'] - df_latest['view_count_old']

# Convert timestamp back to string so JSON can save it
df_latest['snapshot_at'] = df_latest['snapshot_at'].astype(str)

# 5. Generate JSON files
# Top 10 by Weekly Views
df_sorted_weekly = df_latest.sort_values(by='weekly_views', ascending=False)
top10 = df_sorted_weekly.head(10).to_dict(orient='records')

# Newest Releases
df_sorted_date = df_latest.sort_values(by='upload_date', ascending=False)
newest = df_sorted_date.head(20).to_dict(orient='records')

os.makedirs('data', exist_ok=True)
with open('data/top10.json', 'w') as f:
    json.dump(top10, f, indent=2)
    
with open('data/newest.json', 'w') as f:
    json.dump(newest, f, indent=2)

print("Successfully generated weekly top10.json and newest.json")
