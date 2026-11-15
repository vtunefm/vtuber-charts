import csv
import os
import re
import time
import requests
from googleapiclient.discovery import build

BASE = "https://old.vsing.info"
UA = {"User-Agent": "vtunefm-charts/0.1 (+github.com/vtunefm/vtuber-charts)"}
DELAY = 0.7

MAX_NEW_CHANNELS = 3
MAX_VIDEOS_PER_CHANNEL = 40

TRACKS = "data/tracks.csv"
CHANNELS = "data/channels.csv"

COLS = [
    "video_id", "video_name", "music_name", "channel_name", "channel_key",
    "artists", "offices", "published_at", "duration_sec", "type", "is_short",
    "first_stat_date", "latest_views", "latest_likes", "discovered_via",
    "first_seen", "status",
]

COVER_PAT = ["cover", "歌ってみた", "カバー", "covered by", "歌枠", "歌配信"]
ORIG_PAT = ["original", "オリジナル", "書き下ろし", "official mv", "debut song"]

API_KEY = os.environ.get("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=API_KEY) if API_KEY else None

TAG_RE = re.compile(r"#\S+")
BRACKET_RE = re.compile(r"[【】『』「」]")
SLASH_RE = re.compile(r"\s*[/／]\s*")
NOISE_RE = re.compile(r"(歌ってみた|covered by.*$|カバー|\bcover\b)", re.I)
BY_RE = re.compile(r"\bby\b", re.I)


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
    s = TAG_RE.sub(" ", name or "")
    s = BRACKET_RE.sub(" ", s)
    s = SLASH_RE.split(s)[0]
    s = NOISE_RE.sub(" ", s)
    s = BY_RE.sub(" ", s)
    s = s.replace('"', " ")
    s = re.sub(r"\s+", " ", s).strip(" -_·|,")
    if len(s) < 2:
        s = TAG_RE.sub(" ", fallback or "")
        s = re.sub(r"\s+", " ", BRACKET_RE.sub(" ", s)).strip(" -_·|,")
    return s


def channel_key(channel):
    if not channel:
        return ""
    first = SLASH_RE.split(channel)[0].strip()
    return first or channel.strip()


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


def read_tracks():
    if not os.path.exists(TRACKS):
        return []
    with open(TRACKS, newline="", encoding="utf-8") as f:
        return [{k: r.get(k, "") for k in COLS} for r in csv.DictReader(f)]


def write_tracks(rows):
    os.makedirs("data", exist_ok=True)
    with open(TRACKS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in COLS})


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
    members = [m for m in (data.get("memberdata") or []) if m.get("nickname")]
    duration = data.get("movietime") or 0

    artists = " / ".join(m["nickname"] for m in members)
    if not artists:
        seg = SLASH_RE.split(name)
        if len(seg) > 1:
            artists = seg[1].strip()

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
        "offices": " / ".join(m.get("office") or "" for m in members),
        "published_at": published.get(video_id, ""),
        "duration_sec": duration,
        "type": classify(name, channel),
        "is_short": is_short(name, duration),
        "first_stat_date": first_stat,
        "latest_views": views,
        "latest_likes": likes,
        "discovered_via": discovered_via,
        "first_seen": time.strftime("%Y-%m-%d"),
        "status": "active",
    }


def main():
    print(f"youtube client: {'ready' if youtube else 'MISSING KEY'}")
    print("selftest:", classify("【歌ってみた】X", "ch"), classify("X", "Foo - Topic"),
          repr(clean_song('"CRAZY" #cover by Seible Part1', "")))

    rows = read_tracks()
    known_ids = {r["video_id"] for r in rows}
    known_channels = {r["channel_key"] for r in rows if r["channel_key"]}

    feed = fetch_json(f"{BASE}/api/latest.json")
    if not feed:
        print("latest.json unavailable")
        return

    queue = [(i[0], "latest") for i in feed.get("index", []) if i and i[0] not in known_ids]
    print(f"{len(queue)} new candidate(s) from latest feed")

    published = fetch_published([v for v, _ in queue])
    new_channels = []

    while queue:
        video_id, via = queue.pop(0)
        if video_id in known_ids:
            continue
        row = video_row(video_id, via, published)
        time.sleep(DELAY)
        if not row:
            continue
        rows.append(row)
        known_ids.add(video_id)
        if row["channel_key"] and row["channel_key"] not in known_channels:
            known_channels.add(row["channel_key"])
            new_channels.append(row["channel_key"])

    print(f"{len(rows)} tracks after latest pass")

    for ch in new_channels[:MAX_NEW_CHANNELS]:
        ch_data = fetch_json(f"{BASE}/api/v4/ch/{requests.utils.quote(ch, safe='')}.json")
        time.sleep(DELAY)
        if not ch_data:
            print(f"channel expand FAILED: {ch}")
            continue
        vids = [v for v in (ch_data.get("videolist") or []) if v not in known_ids]
        print(f"expanding {ch}: {len(vids)} unseen video(s)")

        with open(CHANNELS, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                ch, ch_data.get("belongoffice") or "", len(vids), time.strftime("%Y-%m-%d"),
            ])

        batch = vids[:MAX_VIDEOS_PER_CHANNEL]
        pub = fetch_published(batch)
        pulled = 0
        for vid in batch:
            row = video_row(vid, f"channel:{ch}", pub)
            time.sleep(DELAY)
            if not row:
                continue
            row["offices"] = ch_data.get("belongoffice") or row["offices"]
            rows.append(row)
            known_ids.add(vid)
            pulled += 1
        print(f"expanded {ch}: +{pulled}")

    write_tracks(rows)
    shorts = sum(1 for r in rows if r["is_short"] is True)
    unknown = sum(1 for r in rows if r["type"] == "unknown")
    print(f"done. {len(rows)} tracks, {shorts} shorts, {unknown} unknown type")


if __name__ == "__main__":
    main()
