import csv
import os
import time
import requests

BASE = "https://old.vsing.info"
UA = {"User-Agent": "vtunefm-charts/0.1 (+github.com/vtunefm/vtuber-charts)"}
DELAY = 0.7

MAX_NEW_CHANNELS = 3
MAX_VIDEOS_PER_CHANNEL = 40

TRACKS = "data/tracks.csv"
CHANNELS = "data/channels.csv"

COLS = [
    "video_id", "video_name", "music_name", "channel_name", "artists", "offices",
    "duration_sec", "type", "is_short", "first_stat_date", "latest_views",
    "latest_likes", "discovered_via", "first_seen", "status",
]

COVER_PAT = ["cover", "歌ってみた", "カバー", "covered by", "歌枠", "歌配信"]
ORIG_PAT = ["original", "オリジナル", "書き下ろし", "official mv", "debut song"]


def fetch_json(url, tries=3):
    for attempt in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(1.5 * (attempt + 1))
    return None


def classify(name):
    low = (name or "").lower()
    if any(p in low for p in COVER_PAT):
        return "cover"
    if any(p in low for p in ORIG_PAT):
        return "original"
    return "unknown"


def is_short(name, duration):
    low = (name or "").lower()
    if "#shorts" in low or "/shorts" in low:
        return True
    return bool(duration) and duration <= 62


def load_known():
    ids, channels = set(), set()
    if os.path.exists(TRACKS):
        with open(TRACKS, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ids.add(row["video_id"])
                channels.add(row["channel_name"])
    return ids, channels


def ensure_headers():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(TRACKS):
        with open(TRACKS, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=COLS).writeheader()
    if not os.path.exists(CHANNELS):
        with open(CHANNELS, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(
                f, fieldnames=["channel_name", "office", "video_count", "expanded_at"]
            ).writeheader()


def append_row(path, row):
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=list(row.keys())).writerow(row)


def video_row(video_id, discovered_via):
    data = fetch_json(f"{BASE}/api/v4/videoid/{video_id}.json")
    if not data:
        return None

    name = data.get("videoname") or ""
    members = data.get("memberdata") or []
    stats = data.get("statisticsdata") or []
    first_stat = ""
    views = likes = ""

    if stats and isinstance(stats[0], list) and stats[0]:
        first_stat = stats[0][0]
        if len(stats[0]) > 1:
            views = stats[0][1]
        if len(stats[0]) > 2:
            likes = stats[0][2]

    duration = data.get("movietime") or 0

    return {
        "video_id": video_id,
        "video_name": name,
        "music_name": data.get("musicname") or "",
        "channel_name": data.get("channelname") or "",
        "artists": " / ".join(m.get("nickname") or "" for m in members),
        "offices": " / ".join(m.get("office") or "" for m in members),
        "duration_sec": duration,
        "type": classify(name),
        "is_short": is_short(name, duration),
        "first_stat_date": first_stat,
        "latest_views": views,
        "latest_likes": likes,
        "discovered_via": discovered_via,
        "first_seen": time.strftime("%Y-%m-%d"),
        "status": "active",
    }


def main():
    ensure_headers()
    known_ids, known_channels = load_known()

    feed = fetch_json(f"{BASE}/api/latest.json")
    if not feed:
        print("latest.json unavailable")
        return

    queue = []
    for item in feed.get("index", []):
        if item and item[0] not in known_ids:
            queue.append((item[0], "latest"))

    print(f"{len(queue)} new candidate(s) from latest feed")

    added = 0
    new_channels = []

    while queue:
        video_id, via = queue.pop(0)
        if video_id in known_ids:
            continue
        row = video_row(video_id, via)
        time.sleep(DELAY)
        if not row:
            continue
        append_row(TRACKS, row)
        known_ids.add(video_id)
        added += 1
        ch = row["channel_name"]
        if ch and ch not in known_channels:
            known_channels.add(ch)
            new_channels.append((ch, row["offices"]))

    print(f"added {added} track(s)")

    for ch, office in new_channels[:MAX_NEW_CHANNELS]:
        ch_data = fetch_json(f"{BASE}/api/v4/ch/{requests.utils.quote(ch, safe='')}.json")
        time.sleep(DELAY)
        if not ch_data:
            continue
        vids = ch_data.get("videolist") or []
        append_row(CHANNELS, {
            "channel_name": ch,
            "office": ch_data.get("belongoffice") or office,
            "video_count": len(vids),
            "expanded_at": time.strftime("%Y-%m-%d"),
        })
        pulled = 0
        for vid in vids[:MAX_VIDEOS_PER_CHANNEL]:
            if vid in known_ids:
                continue
            row = video_row(vid, f"channel:{ch}")
            time.sleep(DELAY)
            if not row:
                continue
            append_row(TRACKS, row)
            known_ids.add(vid)
            pulled += 1
        print(f"expanded {ch}: +{pulled}")

    print(f"done. tracks now contain {len(known_ids)} ids")


if __name__ == "__main__":
    main()
