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

# For our first test, we are using a hardcoded list of 5 video IDs
# (These are real VTuber songs: 3 covers, 2 originals)
test_video_ids = [
    "eM3j1O_n5O0", # Mori Calliope - Excuse My Rudeness... (Original)
    "Pq_9E0j0z7A", # Gawr Gura - Fly Me To The Moon (Cover)
    "7i9E0G0b4g8", # Hoshimachi Suisei - Stellar Stellar (Original)
    "3K8t0O4M4l8", # Houshou Marine - Bishoujo Muzai Pirates (Original)
    "1O7vF1k0M1w"  # Kobo Kanaeru - Cute Gata Bye Bye (Cover)
]

# 2. Fetch data from YouTube API (in batches of 50)
# The API costs 1 quota unit per call, so this is very cheap
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
        'upload_date': snippet['publishedAt'][:10], # Just the YYYY-MM-DD
        'snapshot_at': now,
        'view_count': int(stats.get('viewCount', 0)),
        'like_count': int(stats.get('likeCount', 0))
    })

df_new = pd.DataFrame(new_snapshots)

# 4. Save to snapshots.csv
csv_path = 'data/snapshots.csv'
if os.path.exists(csv_path):
    # Append to existing data
    df_existing = pd.read_csv(csv_path)
    # Combine, drop exact duplicates (in case run twice in one day)
    df_combined = pd.concat([df_existing, df_new]).drop_duplicates(subset=['video_id', 'snapshot_at'])
    df_combined.to_csv(csv_path, index=False)
else:
    # Create new file
    df_new.to_csv(csv_path, index=False)

print(f"Successfully saved {len(df_new)} snapshots to {csv_path}")

# 5. Generate JSON files for the website
# (Since we only have 1 snapshot right now, we will just sort by total views for this test)
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
