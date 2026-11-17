import csv
import os
import time
from collections import Counter

import yt_dlp

from ytmeta import fetch_meta

CANDS = "data/candidates.csv"
TRACKS = "data/tracks.csv"
COLS = ["query", "channel_id", "channel_name", "handle", "subscribers", "status", "note"]
TCOLS = [
    "video_id", "video_name", "music_name", "channel_name", "channel_key",
    "channel_id", "artists", "offices", "published_at", "duration_sec", "type",
    "is_short", "is_long", "first_stat_date", "latest_views", "latest_likes",
    "discovered_via", "first_seen", "status",
]
MAX_ADD = 1500
PER_CHANNEL = 40
PROBE = 120
LONG_SEC = 900
MAX_DURATION = 1500

COVER_PAT = ["cover", "歌ってみた", "カバー", "covered by", "歌枠", "歌配信"]
ORIG_PAT = ["original", "オリジナル", "書き下ろし", "official mv",
            "music video", "lyric video", "debut song",
            "【mv】", "mv】", "official video", "ost", "【original】"]


def classify(title, channel):
    low = (title or "").lower()
    if any(p in low for p in COVER_PAT):
        return "cover"
    if any(p in low for p in ORIG_PAT):
        return "original"
    if channel and "- topic" in channel.lower():
        return "original"
    return "unknown"


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


def read_tracks():
    if not os.path.exists(TRACKS):
        return []
    with open(TRACKS, newline="", encoding="utf-8") as f:
        return [{k: r.get(k, "") for k in TCOLS} for r in csv.DictReader(f)]


def write_tracks(rows):
    os.makedirs("data", exist_ok=True)
    with open(TRACKS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TCOLS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in TCOLS})


def main():
    if not os.path.exists(CANDS):
        print("no candidates.csv")
        return

    with open(CANDS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    tracks = read_tracks()
    known = {r["video_id"] for r in tracks}

    counts = Counter(r.get("channel_id") or "" for r in tracks)
    approved = [r for r in rows if r.get("status") == "approved"]
    approved.sort(key=lambda r: counts.get(r["channel_id"], 0))
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

        meta = fetch_meta(vids)
        got = 0
        for vid in vids:
            if added >= MAX_ADD:
                break
            info = meta.get(vid)
            if not info or info["duration"] > MAX_DURATION:
                continue
            title = info["title"]
            tracks.append({
                "video_id": vid,
                "video_name": title,
                "music_name": title,
                "channel_name": info["channel"] or cand["channel_name"],
                "channel_key": info["channel"] or cand["channel_name"],
                "channel_id": cand["channel_id"],
                "artists": cand["query"],
                "offices": "",
                "published_at": info["published"],
                "duration_sec": info["duration"],
                "type": classify(title, info["channel"]),
                "is_short": str("#shorts" in title.lower() or info["duration"] <= 62),
                "is_long": str(info["duration"] > LONG_SEC),
                "first_stat_date": "",
                "latest_views": info["views"],
                "latest_likes": info["likes"],
                "discovered_via": f"roster:{cand['query']}",
                "first_seen": time.strftime("%Y-%m-%d"),
                "status": "active",
            })
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
