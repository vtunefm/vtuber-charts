import csv
import os
import re
import time
from collections import Counter

import yt_dlp

from ytmeta import fetch_meta

CHANNELS = "data/channels.csv"
ALIASES = "data/aliases.csv"
TRACKS = "data/tracks.csv"
TCOLS = [
    "video_id", "video_name", "music_name", "artist_name", "channel_name",
    "channel_key", "channel_id", "artists", "offices", "published_at",
    "duration_sec", "type", "is_short", "is_long", "first_stat_date",
    "latest_views", "latest_likes", "discovered_via", "first_seen", "status",
]
MAX_ADD = 4000
PER_CHANNEL = 40
PROBE = 120
MIN_DURATION = 120
MAX_DURATION = 420
MIN_NAME = 4

# Cover markers first — they win over everything. Then original markers.
# Then neutral markers, which admit a video without deciding its type.
COVER_RE = re.compile(
    r"\bcover|カバー|歌ってみた|歌枠|歌配信|\bcovered by", re.I
)
ORIG_RE = re.compile(
    r"\boriginal|オリジナル|書き下ろし|\bmv\b|【mv】|\bofficial video"
    r"|\bmusic video|\blyric video|\bdebut song|\bost\b",
    re.I,
)
NEUTRAL_RE = re.compile(r"\bft\.?\b|\bfeat\b|\bver\.?\b|\bversion\b", re.I)


def classify(title, channel):
    low = title or ""
    if COVER_RE.search(low):
        return "cover"
    if ORIG_RE.search(low):
        return "original"
    if NEUTRAL_RE.search(low):
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
        print(f"channel failed {channel_id}: {str(e)[:100]}")
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


def load_name_index(channels):
    """Every spelling we accept in a title -> canonical English name."""
    index = {}
    for ch in channels:
        for source in (ch["name"], ch.get("channel_title")):
            key = (source or "").strip().lower()
            if len(key) >= MIN_NAME:
                index.setdefault(key, ch["name"])
    if os.path.exists(ALIASES):
        with open(ALIASES, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                jp = (row.get("japanese") or "").strip().lower()
                en = (row.get("english") or "").strip()
                if jp and en and len(jp) >= MIN_NAME:
                    index.setdefault(jp, en)
    return index


def partners(title, uploader, index):
    low = (title or "").lower()
    found = []
    for key, name in index.items():
        if name == uploader or name in found:
            continue
        if key in low:
            found.append(name)
    return found


def main():
    if not os.path.exists(CHANNELS):
        print("no channels.csv — run sync.py first")
        return

    with open(CHANNELS, newline="", encoding="utf-8") as f:
        channels = [
            r for r in csv.DictReader(f)
            if r.get("status") == "ok" and r.get("channel_id")
        ]

    index = load_name_index(channels)
    tracks = read_tracks()
    known = {r["video_id"] for r in tracks}
    counts = Counter(r.get("channel_id") or "" for r in tracks)
    channels.sort(key=lambda r: counts.get(r["channel_id"], 0))
    print(f"{len(channels)} resolved channel(s), least-covered first, "
          f"{len(index)} title alias(es)")

    added = 0
    seen = set()
    dropped_short = dropped_long = dropped_type = 0

    for ch in channels:
        if added >= MAX_ADD:
            print("hit MAX_ADD, stopping")
            break
        cid = ch["channel_id"]
        if cid in seen:
            continue
        seen.add(cid)

        vids = [v for v in uploads(cid) if v not in known]
        print(f"{ch['name']}: {len(vids)} unseen")
        if not vids:
            continue

        meta = fetch_meta(vids)
        got = 0
        for vid in vids:
            if added >= MAX_ADD or got >= PER_CHANNEL:
                break
            info = meta.get(vid)
            if not info:
                continue
            dur = info["duration"]
            if dur and dur < MIN_DURATION:
                dropped_short += 1
                continue
            if dur > MAX_DURATION:
                dropped_long += 1
                continue

            title = info["title"]
            kind = classify(title, info["channel"])
            if kind == "unknown":
                dropped_type += 1
                continue

            extra = partners(title, ch["name"], index)
            credits = "/".join([ch["name"]] + extra)
            tracks.append({
                "video_id": vid,
                "video_name": title,
                "music_name": title,
                "artist_name": ch["name"],
                "channel_name": info["channel"] or ch.get("channel_title", ""),
                "channel_key": ch.get("channel_title", ""),
                "channel_id": cid,
                "artists": credits,
                "offices": "",
                "published_at": info["published"],
                "duration_sec": dur,
                "type": kind,
                "is_short": str("#shorts" in title.lower() or 0 < dur <= MIN_DURATION),
                "is_long": str(dur > MAX_DURATION),
                "first_stat_date": "",
                "latest_views": info["views"],
                "latest_likes": info["likes"],
                "discovered_via": f"roster:{ch['name']}",
                "first_seen": time.strftime("%Y-%m-%d"),
                "status": "active",
            })
            known.add(vid)
            added += 1
            got += 1
        print(f"  +{got}")

    write_tracks(tracks)
    print(f"done. {len(tracks)} tracks (+{added})")
    print(f"dropped: {dropped_short} under {MIN_DURATION}s, "
          f"{dropped_long} over {MAX_DURATION}s, {dropped_type} unclassifiable")


if __name__ == "__main__":
    main()
