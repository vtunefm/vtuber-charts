import csv
import os
import time
from datetime import datetime, timedelta, timezone
from collections import Counter

import requests

from discover import (
    BASE, DELAY, MAX_DURATION, RECENT_DAYS,
    fetch_json, fetch_published, read_tracks, to_int, video_row, write_tracks,
)

SONGS = "data/songs.csv"
MAX_SONGS = 8
MAX_NEW_VIDEOS = 40
SONG_COLS = ["music_name", "artist", "video_count", "expanded_at"]


def load_done():
    if not os.path.exists(SONGS):
        return set()
    with open(SONGS, newline="", encoding="utf-8") as f:
        return {r.get("music_name", "") for r in csv.DictReader(f)}


def log_song(name, artist, count):
    os.makedirs("data", exist_ok=True)
    fresh = not os.path.exists(SONGS)
    with open(SONGS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SONG_COLS)
        if fresh:
            w.writeheader()
        w.writerow({
            "music_name": name,
            "artist": artist,
            "video_count": count,
            "expanded_at": time.strftime("%Y-%m-%d"),
        })


def main():
    rows = read_tracks()
    known = {r["video_id"] for r in rows}
    done = load_done()

    counts = Counter()
    for r in rows:
        name = (r.get("music_name") or "").strip()
        if len(name) < 2 or name in done:
            continue
        if r.get("type") not in ("cover", "original"):
            continue
        if r.get("is_short") == "True":
            continue
        counts[name] += 1

    songs = [name for name, _ in counts.most_common()]

    print(f"{len(songs)} song(s) eligible for sibling expansion")
    added = 0

    for name in list(songs)[:MAX_SONGS]:
        data = fetch_json(f"{BASE}/api/v4/music/{requests.utils.quote(name, safe='')}.json")
        time.sleep(DELAY)
        if not data:
            print(f"music lookup failed: {name}")
            continue

        vids = [v for v in (data.get("videolist") or []) if v not in known]
        log_song(name, data.get("artist") or "", len(vids))
        print(f"{name}: {len(vids)} unseen cover(s)")
        if not vids:
            continue

        cutoff = (datetime.now(timezone.utc).date() - timedelta(days=RECENT_DAYS)).isoformat()
        probe = vids[:60]
        pub = fetch_published(probe)
        batch = [v for v in probe if (pub.get(v) or "") >= cutoff]
        batch = batch[: max(0, MAX_NEW_VIDEOS - added)]

        for vid in batch:
            row = video_row(vid, f"song:{name}", pub)
            time.sleep(DELAY)
            if not row or to_int(row["duration_sec"]) > MAX_DURATION:
                continue
            rows.append(row)
            known.add(vid)
            added += 1
        print(f"  +{len(batch)} added")

    write_tracks(rows)
    print(f"done. {len(rows)} tracks (+{added})")


if __name__ == "__main__":
    main()
