import csv
import os
import re
import time
from collections import Counter

import requests
from googleapiclient.discovery import build

BASE = "https://old.vsing.info"
UA = {"User-Agent": "vtunefm-charts/0.1 (+github.com/vtunefm/vtuber-charts)"}
DELAY = 0.7

MAX_NEW_CHANNELS = 3
MAX_VIDEOS_PER_CHANNEL = 40
LONG_SEC = 900
MAX_DURATION = 1500

TRACKS = "data/tracks.csv"
CHANNELS = "data/channels.csv"

COLS = [
    "video_id", "video_name", "music_name", "channel_name", "channel_key",
    "artists", "offices", "published_at", "duration_sec", "type", "is_short",
    "is_long", "first_stat_date", "latest_views", "latest_likes",
    "discovered_via", "first_seen", "status",
]

COVER_PAT = ["cover", "歌ってみた", "カバー", "covered by", "歌枠", "歌配信"]
ORIG_PAT = ["original", "オリジナル", "書き下ろし", "official mv",
            "music video", "lyric video", "debut song"]

API_KEY = os.environ.get("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=API_KEY) if API_KEY else None

TAG_RE = re.compile(r"#\S+")
LONE_HASH_RE = re.compile(r"#(?=\s|$)")
BRACKET_RE = re.compile(r"[【】『』「」]")
SLASH_RE = re.compile(r"\s*[/／]\s*")
NOISE_RE = re.compile(r"(歌ってみた|covered by.*$|カバー|\bcover\b)", re.I)
BY_RE = re.compile(r"\bby\b", re.I)
QUOTE_SONG_RE = re.compile(r"[｢「]([^｣」]{1,60})[｣」]")
OFFICE_STRIP_RE = re.compile(r"【[^】]*】")


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


def clean_song(name, fallback):
    m = QUOTE_SONG_RE.search(name or "")
    if m and "LIVE" in (name or "").upper():
        return m.group(1).strip()
    for src in (name, fallback):
        s = TAG_RE.sub(" ", src or "")
        s = LONE_HASH_RE.sub(" ", s)
        s = BRACKET_RE.sub(" ", s)
        s = SLASH_RE.split(s)[0]
        s = NOISE_RE.sub(" ", s)
        s = BY_RE.sub(" ", s)
        s = s.replace('"', " ")
        s = re.sub(r"\s+", " ", s).strip(" -_·|,")
        if len(s) >= 2:
            return s
    return (name or "").strip()


def channel_key(channel):
    if not channel:
        return ""
    first = SLASH_RE.split(channel)[0].strip()
    return first or channel.strip()


def channel_candidates(channel, key):
    out = [key]
    alt = OFFICE_STRIP_RE.sub("", channel or "").strip()
    if alt and alt not in out:
        out.append(alt)
    return [c for c in out if c]


def classify(name, channel):
    low = (name or "").lower()
    if any(p in low for p in COVER_PAT):
        return "cover"
    if any(p in low for p in ORIG_PAT):
        return "original"
    if channel and "- topic" in channel.lower():
        return "original"
    return "unknown"


def is_short(name, duration):
    low = (name or "").lower()
    if "#shorts" in low or "/shorts" in low:
        return True
    return bool(duration) and duration <= 62


def to_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def normalize_row(row):
    name = row.get("video_name", "")
    dur = to_int(row.get("duration_sec"))
    row["is_short"] = str(is_short(name, dur))
    row["is_long"] = str(dur > LONG_SEC)
    if row.get("type") in ("", "unknown"):
        row["type"] = classify(name, row.get("channel_name", ""))
    song = row.get("music_name", "")
    if len(song) < 2 or song.endswith("#") or song.startswith("#"):
        row["music_name"] = clean_song(song, name)
    return row


def read_tracks():
    if not os.path.exists(TRACKS):
        return []
    with open(TRACKS, newline="", encoding="utf-8") as f:
        return [normalize_row({k: r.get(k, "") for k in COLS}) for r in csv.DictReader(f)]


def write_tracks(rows):
    os.makedirs("data", exist_ok=True)
    with open(TRACKS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in COLS})


def recently_expanded():
    if not os.path.exists(CHANNELS):
        return set()
    now = time.time()
    out = set()
    with open(CHANNELS, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = r.get("channel_name", "")
            stamp = r.get("expanded_at", "")
            if stamp == time.strftime("%Y-%m-%d"):
                out.add(name)
            elif r.get("office") == "__failed" and stamp:
                try:
                    if now - time.mktime(time.strptime(stamp, "%Y-%m-%d")) < 7 * 86400:
                        out.add(name)
                except ValueError:
                    pass
    return out


def fetch_published(ids):
    out = {}
    if not youtube or not ids:
        return out
    for i in range(0, len(ids), 50):
        try:
            resp = youtube.videos().list(
                part="snippet", id=",".join(ids[i:i + 50])
            ).execute()
            for item in resp.get("items", []):
                out[item["id"]] = item["snippet"].get("publishedAt", "")[:10]
        except Exception as e:
            print(f"publishedAt lookup failed: {e}")
    print(f"publishedAt resolved for {len(out)}/{len(ids)}")
    return out


def video_row(video_id, discovered_via, published):
    data = fetch_json(f"{BASE}/api/v4/videoid/{video_id}.json")
    if not data:
        return None

    name = data.get("videoname") or ""
    channel = data.get("channelname") or ""
    duration = data.get("movietime") or 0
    members = data.get("memberdata") or []

    artists = " / ".join(m["nickname"] for m in members if m.get("nickname"))
    if not artists:
        seg = SLASH_RE.split(name)
        if len(seg) > 1:
            artists = seg[1].strip()
    artists = re.sub(r"\s*(cover|カバー)\s*$", "", artists, flags=re.I).strip()

    offices = " / ".join(m["office"] for m in members if m.get("office"))

    stats = data.get("statisticsdata") or []
    first_stat = views = likes = ""
    if stats and isinstance(stats[0], list) and stats[0]:
        first_stat = stats[0][0]
        views = stats[0][1] if len(stats[0]) > 1 else ""
        likes = stats[0][2] if len(stats[0]) > 2 else ""

    return {
        "video_id": video_id,
        "video_name": name,
        "music_name": clean_song(data.get("musicname") or "", name),
        "channel_name": channel,
        "channel_key": channel_key(channel),
        "artists": artists,
        "offices": offices,
        "published_at": published.get(video_id, ""),
        "duration_sec": duration,
        "type": classify(name, channel),
        "is_short": str(is_short(name, duration)),
        "is_long": str(duration > LONG_SEC),
        "first_stat_date": first_stat,
        "latest_views": views,
        "latest_likes": likes,
        "discovered_via": discovered_via,
        "first_seen": time.strftime("%Y-%m-%d"),
        "status": "active",
    }


def main():
    print(f"youtube client: {'ready' if youtube else 'MISSING KEY'}")
    print("selftest:",
          classify("【歌ってみた】X", "ch"),
          classify("X", "Foo - Topic"),
          repr(clean_song("｢天誅｣ 2nd LIVE TOUR「緑一色」 #緑仙 #live", "")),
          repr(clean_song('"CRAZY" #', "")))

    rows = read_tracks()
    known_ids = {r["video_id"] for r in rows}
    known_channels = {r["channel_key"] for r in rows if r["channel_key"]}

    feed = fetch_json(f"{BASE}/api/latest.json")
    published = {}
    if feed:
        queue = [(i[0], "latest") for i in feed.get("index", []) if i and i[0] not in known_ids]
        print(f"{len(queue)} new candidate(s) from latest feed")
        published = fetch_published([v for v, _ in queue])
        while queue:
            video_id, via = queue.pop(0)
            if video_id in known_ids:
                continue
            row = video_row(video_id, via, published)
            time.sleep(DELAY)
            if not row or to_int(row["duration_sec"]) > MAX_DURATION:
                continue
            rows.append(row)
            known_ids.add(video_id)
            known_channels.add(row["channel_key"])
    else:
        print("latest.json unavailable")

    print(f"{len(rows)} tracks after latest pass")

    skip = recently_expanded()
    counts = Counter(r["channel_key"] for r in rows)
    full_names = {}
    for r in rows:
        full_names.setdefault(r["channel_key"], r["channel_name"])

    candidates = [
        c for c in known_channels
        if c and c not in skip
    ]
    candidates.sort(key=lambda c: counts.get(c, 0))
    print(f"{len(candidates)} channel(s) eligible for expansion, {len(skip)} expanded today")

    for key in candidates[:MAX_NEW_CHANNELS]:
        ch_data = None
        resolved = None
        for cand in channel_candidates(full_names.get(key, key), key):
            ch_data = fetch_json(f"{BASE}/api/v4/ch/{requests.utils.quote(cand, safe='')}.json")
            time.sleep(DELAY)
            if ch_data:
                resolved = cand
                print(f"channel resolved via '{cand}'")
                break
            print(f"channel candidate failed: {cand}")
        if not ch_data:
            with open(CHANNELS, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([key, "__failed", 0, time.strftime("%Y-%m-%d")])
            continue
        if resolved != key:
            for r in rows:
                if r["channel_key"] == key:
                    r["channel_key"] = resolved
            key = resolved

        vids = [v for v in (ch_data.get("videolist") or []) if v not in known_ids]
        print(f"expanding {key}: {len(vids)} unseen video(s)")

        with open(CHANNELS, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                key, ch_data.get("belongoffice") or "", len(vids),
                time.strftime("%Y-%m-%d"),
            ])

        batch = vids[:MAX_VIDEOS_PER_CHANNEL]
        pub = fetch_published(batch)
        pulled = 0
        for vid in batch:
            row = video_row(vid, f"channel:{key}", pub)
            time.sleep(DELAY)
            if not row or to_int(row["duration_sec"]) > MAX_DURATION:
                continue
            row["offices"] = ch_data.get("belongoffice") or row["offices"]
            rows.append(row)
            known_ids.add(vid)
            pulled += 1
        print(f"expanded {key}: +{pulled}")

    write_tracks(rows)
    print(f"done. {len(rows)} tracks, "
          f"{sum(1 for r in rows if r['is_short'] == 'True')} shorts, "
          f"{sum(1 for r in rows if r['is_long'] == 'True')} long, "
          f"{sum(1 for r in rows if r['type'] == 'unknown')} unknown")


if __name__ == "__main__":
    main()
