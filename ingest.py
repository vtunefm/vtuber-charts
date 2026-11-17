import csv
import os
import time
from collections import Counter

import yt_dlp

from discover import MAX_DURATION, fetch_published, read_tracks, to_int, video_row, write_tracks

CANDS = "data/candidates.csv"
COLS = ["query", "channel_id", "channel_name", "handle", "subscribers", "status", "note"]
MAX_ADD = 1500
PER_CHANNEL = 40
PROBE = 120


def uploads(channel_id):
    url = f"https://www.youtube.com/channel/{channel_id}/videos"
    opts = {"extract_flat": True, "quiet": True, "playlistend": PROBE}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"channel failed {channel_id}: {e}")
        return []
    return [e["id"] for e in (info.get("entries") or []) if e and e.get("id")]


def main():
    if not os.path.exists(CANDS):
        print("no candidates.csv")
        return

    with open(CANDS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    tracks = read_tracks()
    known = {r["video_id"] for r in tracks}

    counts = Counter(r.get("channel_key") or "" for r in tracks)
    approved = [r for r in rows if r.get("status") == "approved"]
    approved.sort(key=lambda r: counts.get(r["channel_name"], 0))
    print(f"{len(approved)} approved channel(s), least-covered first")

    added = 0
    seen_channels = set()

    for cand in approved:
        if added >= MAX_ADD:
            print("hit MAX_ADD, stopping")
            break
        if cand["channel_id"] in seen_channels:
            cand["status"] = "done"
            continue
        seen_channels.add(cand["channel_id"])

        vids = [v for v in uploads(cand["channel_id"]) if v not in known][:PER_CHANNEL]
        print(f"{cand['channel_name']}: {len(vids)} unseen")
        if not vids:
            cand["status"] = "done"
            continue

        published = fetch_published(vids)
        got = 0
        for vid in vids:
            if added >= MAX_ADD:
                break
            row = video_row(vid, f"roster:{cand['query']}", published)
            time.sleep(0.5)
            if not row or to_int(row["duration_sec"]) > MAX_DURATION:
                continue
            row["channel_id"] = cand["channel_id"]
            row["offices"] = row["offices"] or cand["channel_name"]
            tracks.append(row)
            known.add(vid)
            added += 1
            got += 1
        print(f"  +{got}")
        if got:
            cand["status"] = "done"

    write_tracks(tracks)
    with open(CANDS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    print(f"done. {len(tracks)} tracks (+{added})")


if __name__ == "__main__":
    main()
