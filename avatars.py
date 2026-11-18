import csv
import os
import time

from googleapiclient.discovery import build

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise SystemExit("missing YOUTUBE_API_KEY")

youtube = build("youtube", "v3", developerKey=API_KEY)

CHANNELS = "data/channels.csv"
TRACKS = "data/tracks.csv"
OUT = "data/avatars.csv"
BATCH = 50
TCOLS = [
    "video_id", "video_name", "music_name", "artist_name", "channel_name",
    "channel_key", "channel_id", "artists", "offices", "published_at",
    "duration_sec", "type", "is_short", "is_long", "first_stat_date",
    "latest_views", "latest_likes", "discovered_via", "first_seen", "status",
]


def main():
    ids = set()
    if os.path.exists(CHANNELS):
        with open(CHANNELS, newline="", encoding="utf-8") as f:
            ids |= {
                r["channel_id"] for r in csv.DictReader(f)
                if r.get("status") == "ok" and r.get("channel_id")
            }
    if os.path.exists(TRACKS):
        with open(TRACKS, newline="", encoding="utf-8") as f:
            ids |= {r["channel_id"] for r in csv.DictReader(f) if r.get("channel_id")}

    ids = sorted(ids)
    print(f"{len(ids)} channel(s) to cover")

    known = set()
    if os.path.exists(OUT):
        with open(OUT, newline="", encoding="utf-8") as f:
            known = {r["channel_id"] for r in csv.DictReader(f)}

    todo = [i for i in ids if i not in known]
    print(f"{len(todo)} avatar(s) to fetch")

    os.makedirs("data", exist_ok=True)
    fresh = not os.path.exists(OUT)
    written = 0

    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["channel_id", "avatar"])
        if fresh:
            w.writeheader()

        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            try:
                resp = youtube.channels().list(
                    part="snippet", id=",".join(chunk)
                ).execute()
            except Exception as e:
                print(f"batch failed: {str(e)[:120]}")
                time.sleep(3)
                continue
            for item in resp.get("items", []):
                thumbs = item.get("snippet", {}).get("thumbnails", {})
                url = (
                    thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}
                ).get("url")
                if url:
                    w.writerow({"channel_id": item["id"], "avatar": url})
                    written += 1
            time.sleep(0.3)

    print(f"wrote {written} avatar row(s)")


if __name__ == "__main__":
    main()
