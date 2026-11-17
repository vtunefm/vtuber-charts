import csv
import os
import time

from googleapiclient.discovery import build

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise SystemExit("missing YOUTUBE_API_KEY")

youtube = build("youtube", "v3", developerKey=API_KEY)

TRACKS = "data/tracks.csv"
OUT = "data/avatars.csv"
BATCH = 50


def main():
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
    print(f"{len(todo)} channel avatar(s) to fetch")

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
                url = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url")
                if url:
                    w.writerow({"channel_id": item["id"], "avatar": url})
                    written += 1
            time.sleep(0.3)

    print(f"wrote {written} avatar row(s)")


if __name__ == "__main__":
    main()
