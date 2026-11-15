import os
import json
import pandas as pd
from datetime import datetime, timezone
from googleapiclient.discovery import build

# 1. Setup
API_KEY = os.environ.get("YOUTUBE_API_KEY")
youtube = build('youtube', 'v3', developerKey=API_KEY)
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

# A list of REAL VTuber videos (Originals and Covers)
video_ids = [
    "vJ3d8wH5G4Y", # Hoshimachi Suisei - Stellar Stellar
    "eM3j1O_n5O0", # Mori Calliope - Excuse My Rudeness
    "k1BneeJTDcU", # Gawr Gura - REFLECT
    "7i9E0G0b4g8", # Hoshimachi Suisei - GHOST
    "3K8t0O4M4l8", # Houshou Marine - Bishoujo Muzai Pirates
    "1O7vF1k0M1w", # Kobo Kanaeru - Cute Gata Bye Bye
    "R8t0X3h2m1A", # Houshou Marine - Unison
    "Yq6F9R_e7o0", # Mori Calliope - End of a Life
    "K1n8s9s2u4o", # Kobo Kanaeru - Help!!
    "4m1z6e1x7y8"  # Tokoyami Towa - ERROR
]

print(f"Fetching stats for {len(video_ids)} videos...")

# 2. Fetch data from YouTube API in batches of 50
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

if df_new.empty:
    print("No data returned. Videos might be invalid or private.")
    exit(0)

# 3. Save to snapshots.csv
csv_path = 'data/snapshots.csv'
if os.path.exists(csv_path):
    df_existing = pd.read_csv(csv_path)
    df_combined = pd.concat([df_existing, df_new])
else:
    df_combined = df_new

df_combined.to_csv(csv_path, index=False)
print(f"Successfully saved data to {csv_path}")

# 4. Generate JSON files for the website
# Keep only the most recent snapshot for each video
df_latest = df_combined.sort_values('snapshot_at').drop_duplicates('video_id', keep='last')

# Top 10 by total views
df_sorted_views = df_latest.sort_values(by='view_count', ascending=False)
top10 = df_sorted_views.head(10).to_dict(orient='records')

# Newest Releases
df_sorted_date = df_latest.sort_values(by='upload_date', ascending=False)
newest = df_sorted_date.head(20).to_dict(orient='records')

os.makedirs('data', exist_ok=True)
with open('data/top10.json', 'w') as f:
    json.dump(top10, f, indent=2)
    
with open('data/newest.json', 'w') as f:
    json.dump(newest, f, indent=2)

print("Successfully generated top10.json and newest.json")
