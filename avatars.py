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


def to_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def load_channels():
    index = []
    if not os.path.exists(CANDS):
        return index
    with open(CANDS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("status") or "") not in ("done", "approved"):
                continue
            cid = (row.get("channel_id") or "").strip()
            name = (row.get("channel_name") or "").strip().lower()
            if not cid or not name:
                continue
            index.append({
                "id": cid,
                "name": name,
                "subs": to_int(row.get("subscribers")),
                "topic": name.endswith("- topic"),
            })
    return index


def best_channel(track_name, index):
    """Longest curated channel name that matches this track's channel."""
    key = (track_name or "").strip().lower()
    if len(key) < 3:
        return None
    best = None
    for c in index:
        if c["name"] in key or key in c["name"]:
            if best is None or len(c["name"]) > len(best["name"]):
                best = c
    return best


def backfill_channel_ids(index):
    if not (os.path.exists(TRACKS) and index):
        return 0

    with open(TRACKS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    filled = 0
    for row in rows:
        if row.get("channel_id"):
            continue
        hit = best_channel(row.get("channel_name") or row.get("channel_key"), index)
        if hit:
            row["channel_id"] = hit["id"]
            filled += 1

    if filled:
        with open(TRACKS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=TCOLS)
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k, "") for k in TCOLS})

    return filled


def main():
    index = load_channels()
    wanted = {c["id"] for c in index}
    print(f"{len(index)} curated channel(s)")

    filled = backfill_channel_ids(index)
    print(f"backfilled {filled} channel_id(s)")

    if not os.path.exists(TRACKS):
        print("no tracks.csv")
        return

    with open(TRACKS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    ids = {r.get("channel_id") for r in rows if r.get("channel_id")}
    ids |= wanted
    ids = sorted(ids)
    print(f"{len(rows)} track(s), {len(ids)} channel(s) to cover")

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
