import csv
import json
import os
from datetime import datetime, timezone

TRACKS = "data/tracks.csv"
OUT = "data/newest.json"
LIMIT = 20


def main():
    if not os.path.exists(TRACKS):
        print("no tracks.csv")
        return

    with open(TRACKS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    fresh = [
        r for r in rows
        if r.get("published_at")
        and r.get("status", "active") == "active"
        and r.get("is_short") != "True"
        and r.get("is_long") != "True"
    ]
    fresh.sort(key=lambda r: r["published_at"], reverse=True)

    entries = [{
        "video_id": r["video_id"],
        "title": r.get("music_name") or r.get("video_name"),
        "artists": r.get("artists"),
        "channel": r.get("channel_name"),
        "office": r.get("offices"),
        "type": r.get("type"),
        "published_at": r["published_at"],
        "thumbnail": f"https://i.ytimg.com/vi/{r['video_id']}/hqdefault.jpg",
    } for r in fresh[:LIMIT]]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entry_count": len(entries),
        "entries": entries,
    }

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"wrote {len(entries)} entries to {OUT}")


if __name__ == "__main__":
    main()
