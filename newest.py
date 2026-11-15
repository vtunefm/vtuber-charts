import csv
import json
import os
import re
from datetime import datetime, timedelta, timezone

TRACKS = "data/tracks.csv"
OUT = "data/newest.json"
LIMIT = 10

TITLE_TAIL_RE = re.compile(r"\s*(cover|カバー)\s*$", re.I)
ARTIST_JUNK_RE = re.compile(r"\s*【[^】]*$")


def build(r):
    artists = TITLE_TAIL_RE.sub("", ARTIST_JUNK_RE.sub("", r.get("artists") or "")).strip()
    return {
        "video_id": r["video_id"],
        "title": TITLE_TAIL_RE.sub("", r.get("music_name") or r.get("video_name") or "").strip(),
        "artists": artists or (r.get("channel") or ""),
        "office": r.get("offices"),
        "type": r.get("type"),
        "published_at": r["published_at"],
        "thumbnail": f"https://i.ytimg.com/vi/{r['video_id']}/hqdefault.jpg",
    }


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

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    buckets = {"today": [], "yesterday": [], "earlier": []}

    for r in fresh:
        stamp = r["published_at"]
        if stamp == today.isoformat():
            buckets["today"].append(build(r))
        elif stamp == yesterday.isoformat():
            buckets["yesterday"].append(build(r))
        else:
            buckets["earlier"].append(build(r))

    for key in buckets:
        buckets[key] = buckets[key][:LIMIT]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "today": buckets["today"],
        "yesterday": buckets["yesterday"],
        "earlier": buckets["earlier"],
    }

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"today {len(buckets['today'])}, yesterday {len(buckets['yesterday'])}, "
          f"earlier {len(buckets['earlier'])}")


if __name__ == "__main__":
    main()
