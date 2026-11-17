import csv
import os
import time

from googleapiclient.discovery import build

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise SystemExit("missing YOUTUBE_API_KEY")

youtube = build("youtube", "v3", developerKey=API_KEY)

TRACKS = "data/tracks.csv"
CANDS = "data/candidates.csv"
OUT = "data/avatars.csv"
BATCH = 50

TCOLS = [
    "video_id", "video_name", "music_name", "channel_name", "channel_key",
    "channel_id", "artists", "offices", "published_at", "duration_sec", "type",
    "is_short", "is_long", "first_stat_date", "latest_views", "latest_likes",
    "discovered_via", "first_seen", "status",
]


def backfill_channel_ids():
    if not (os.path.exists(TRACKS) and os.path.exists(CANDS)):
        return 0

    with open(CANDS, newline="", encoding="utf-8") as f:
        by_name = {}
        for row in csv.DictReader(f):
            if row.get("channel_id") and row.get("channel_name"):
                by_name[row["channel_name"]] = row["channel_id"]

    with open(TRACKS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    filled = 0
    for row in rows:
        if row.get("channel_id"):
            continue
        cid = by_name.get(row.get("channel_name") or "") or by_name.get(row.get("channel_key") or "")
        if cid:
            row["channel_id"] = cid
            filled += 1

    if filled:
        with open(TRACKS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=TCOLS)
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k, "") for k in TCOLS})

    return filled


def main():
    filled = backfill_channel_ids()
    print(f"backfilled {filled} channel_id(s)")

    if not os.path.exists(TRACKS):
        print("no tracks.csv")
        return

    with open(TRACKS, newline="", encoding="utf-8") as f:
        ids = sorted({r.get("channel_id") for r in csv.DictReader(f) if r.get("channel_id")})

    known = set()
    if os.path.exists(OUT):
        with open(OUT, newline="", encoding="utf-8") as f:
            known = {r["channel_id"] for r in csv.DictReader(f)}

    todo = [i for i in ids if i not in known]
    print(f"{len(todo)} avatar(s) to fetch of {len(ids)} channel(s)")

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
                print(f"batch failed: {e}")
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
