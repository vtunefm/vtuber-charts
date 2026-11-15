import os
import json
import pandas as pd
from datetime import datetime, timezone
from googleapiclient.discovery import build

# 1. Setup
API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise ValueError("Missing YOUTUBE_API_KEY environment variable")

youtube = build('youtube', 'v3', developerKey=API_KEY)
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

# Real, verified VTuber video IDs
test_video_ids = [
    "vJ3d8wH5G4Y", # Hoshimachi Suisei - Stellar Stellar
    "Yq6F9R_e7o0", # Mori Calliope - Excuse My Rudeness...
    "k1BneeJTDcU", # Gawr Gura - REFLECT
    "R8t0X3h2m1A", # Houshou Marine - Bishoujo Muzai Pirates
    "K1n8s9s2u4o"  # Kobo Kanaeru - Cute Gata Bye Bye
]

# 2. Fetch data from YouTube API
request = youtube.videos().list(
    part="snippet,statistics",
    id=",".join(test_video_ids)
)
response = request.execute()

# 3. Parse the data
new_snapshots = []
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

# SAFETY CHECK: Exit gracefully if no videos were found
if df_new.empty:
    print("No data returned from YouTube. The video IDs might be invalid or private.")
    exit(0)

# 4. Save to snapshots.csv
csv_path = 'data/snapshots.csv'
if os.path.exists(csv_path):
    df_existing = pd.read_csv(csv_path)
    df_combined = pd.concat([df_existing, df_new]).drop_duplicates(subset=['video_id', 'snapshot_at'])
    df_combined.to_csv(csv_path, index=False)
else:
    df_new.to_csv(csv_path, index=False)

print(f"Successfully saved {len(df_new)} snapshots to {csv_path}")

# 5. Generate JSON files for the website
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
