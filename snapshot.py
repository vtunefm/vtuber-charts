import csv
import os
import sys
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
TRIES = 4
COLS = ["video_id", "snapshot_at", "view_count", "like_count"]


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def fetch(chunk):
    for attempt in range(TRIES):
        try:
            return youtube.videos().list(
                part="statistics", id=",".join(chunk)
            ).execute()
        except Exception as e:
            if attempt == TRIES - 1:
                raise
            print(f"  retry {attempt + 1}: {str(e)[:120]}")
            time.sleep(3 * (attempt + 1))


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
    failed = 0

    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if fresh:
            w.writeheader()

        for i in range(0, len(ids), BATCH):
            chunk = ids[i:i + BATCH]
            try:
                resp = fetch(chunk)
            except Exception as e:
                failed += 1
                print(f"batch {i // BATCH} failed: {str(e)[:160]}")
                continue

            for item in resp.get("items", []):
                stats = item.get("statistics", {})
                w.writerow({
                    "video_id": item["id"],
                    "snapshot_at": now,
                    "view_count": as_int(stats.get("viewCount", 0)),
                    "like_count": as_int(stats.get("likeCount", 0)),
                })
                written += 1
            time.sleep(0.3)

    print(f"wrote {written} snapshot row(s), {failed} batch(es) failed")
    if written == 0:
        print("nothing written")
        sys.exit(1)


if __name__ == "__main__":
    main()
