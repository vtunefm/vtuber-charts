import csv
import os
import time
from datetime import datetime, timedelta, timezone

import yt_dlp

from discover import (
    MAX_DURATION, RECENT_DAYS,
    fetch_published, read_tracks, to_int, video_row, write_tracks,
)

CANDS = "data/candidates.csv"
COLS = ["query", "channel_id", "channel_name", "handle", "subscribers", "status", "note"]
MAX_ADD = 40
PROBE = 60


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

    approved = [r for r in rows if r.get("status") == "approved"]
    print(f"{len(approved)} approved channel(s)")

    tracks = read_tracks()
    known = {r["video_id"] for r in tracks}
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=RECENT_DAYS)).isoformat()
    added = 0

    for cand in approved:
        if added >= MAX_ADD:
            break
        vids = [v for v in uploads(cand["channel_id"]) if v not in known]
        print(f"{cand['channel_name']}: {len(vids)} unseen")
        if not vids:
            cand["status"] = "done"
            continue

        published = fetch_published(vids)
        batch = [v for v in vids if (published.get(v) or "") >= cutoff]
        got = 0
        for vid in batch:
            if added >= MAX_ADD:
                break
            row = video_row(vid, f"roster:{cand['query']}", published)
            time.sleep(0.7)
            if not row or to_int(row["duration_sec"]) > MAX_DURATION:
                continue
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
