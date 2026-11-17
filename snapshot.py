import csv
import os
import time
from datetime import datetime, timezone

from googleapiclient.discovery import build

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise SystemExit("missing YOUTUBE_API_KEY")

youtube = build("youtube", "v3", developerKey=API_KEY)

TRACKS = "data/tracks.csv"
OUT = "data/snapshots.csv"
BATCH = 50
COLS = ["video_id", "snapshot_at", "view_count", "like_count"]


def main():
    if not os.path.exists(TRACKS):
        print("no tracks.csv")
        return

    with open(TRACKS, newline="", encoding="utf-8") as f:
        ids = [
            r["video_id"] for r in csv.DictReader(f)
            if r.get("status", "active") == "active" and r.get("video_id")
        ]

    print(f"{len(ids)} track(s) to snapshot")
    os.makedirs("data", exist_ok=True)
    fresh = not os.path.exists(OUT)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    written = 0

    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if fresh:
            w.writeheader()

        for i in range(0, len(ids), BATCH):
            chunk = ids[i:i + BATCH]
            try:
                resp = youtube.videos().list(
                    part="statistics", id=",".join(chunk)
                ).execute()
            except Exception as e:
                print(f"batch {i // BATCH} failed: {e}")
                time.sleep(3)
                continue

            for item in resp.get("items", []):
                stats = item.get("statistics", {})
                w.writerow({
                    "video_id": item["id"],
                    "snapshot_at": now,
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                })
                written += 1
            time.sleep(0.3)

    print(f"wrote {written} snapshot row(s)")


if __name__ == "__main__":
    main()
