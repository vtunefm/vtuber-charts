import csv
import json
import os
import re
import time
from datetime import date, datetime, timedelta, timezone

import requests

BASE = "https://old.vsing.info"
UA = {"User-Agent": "vtunefm-charts/0.1 (+github.com/vtunefm/vtuber-charts)"}
DELAY = 0.7
MIN_GAIN = 1
MAX_ENTRIES = 100
MAX_FETCH = 200

TRACKS = "data/tracks.csv"
OUT = "data/chart.json"
ARCHIVE = "data/archive"

DATE_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})$")
TITLE_TAIL_RE = re.compile(r"\s*(cover|カバー)\s*$", re.I)
ARTIST_SPLIT_RE = re.compile(r"\s*/\s*")


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


def window():
    today = datetime.now(timezone.utc).date()
    days_back = (today.weekday() - 5) % 7
    end = today - timedelta(days=days_back)
    return end - timedelta(days=5), end


def parse_stats(data):
    stats = data.get("statisticsdata") or []
    if len(stats) < 3:
        return []
    dates, views = stats[1], stats[2]
    if not dates or not views:
        return []

    total = 0
    try:
        total = int(stats[0][1])
    except (IndexError, TypeError, ValueError):
        total = 0

    cumulative = False
    try:
        if total and abs(int(views[-1]) - total) <= max(2, total * 0.001):
            cumulative = True
    except (IndexError, TypeError, ValueError):
        pass

    out, prev = [], 0
    for raw, count in zip(dates, views):
        m = DATE_RE.match(str(raw))
        if not m:
            continue
        try:
            day = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            value = int(count)
        except ValueError:
            continue
        out.append((day, value if not cumulative else max(0, value - prev)))
        prev = value
    return out


def past_week_for(end):
    if not os.path.isdir(ARCHIVE):
        return None
    weeks = sorted(n[:-5] for n in os.listdir(ARCHIVE) if n.endswith(".json"))
    weeks = [w for w in weeks if w < end.isoformat()]
    return weeks[-1] if weeks else None


def history(key, exclude=None):
    records = {}
    if not os.path.isdir(ARCHIVE):
        return records
    for name in sorted(os.listdir(ARCHIVE)):
        if not name.endswith(".json"):
            continue
        week = name[:-5]
        if week == exclude:
            continue
        try:
            with open(os.path.join(ARCHIVE, name), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for entry in data.get(key, []):
            ident = entry.get("video_id") or entry.get("name")
            if not ident:
                continue
            rec = records.setdefault(ident, {"peak": 999, "by_week": {}})
            rec["peak"] = min(rec["peak"], entry["rank"])
            rec["by_week"][week] = entry["rank"]
    return records


def apply_history(items, records, past_week, ident):
    for i, item in enumerate(items, start=1):
        item["rank"] = i
        key = ident(item)
        rec = records.get(key, {"peak": i, "by_week": {}})
        last = rec["by_week"].get(past_week) if past_week else None
        item["last_week"] = last
        item["peak"] = min(rec["peak"], i)
        item["weeks_on_chart"] = len(rec["by_week"]) + 1
        if last is None:
            item["movement"] = "new"
        elif i < last:
            item["movement"] = "up"
        elif i > last:
            item["movement"] = "down"
        else:
            item["movement"] = "same"


def split_artists(value):
    return [a.strip() for a in ARTIST_SPLIT_RE.split(value or "") if a.strip()]


def main():
    start, end = window()
    print(f"window: {start} .. {end}")

    if not os.path.exists(TRACKS):
        print("no tracks.csv")
        return

    with open(TRACKS, newline="", encoding="utf-8") as f:
        tracks = list(csv.DictReader(f))

    eligible = [
        t for t in tracks
        if t.get("is_short") != "True"
        and t.get("is_long") != "True"
        and t.get("type") != "unknown"
        and t.get("status", "active") == "active"
    ]
    print(f"{len(eligible)}/{len(tracks)} eligible after filters")

    songs = []
    for track in eligible[:MAX_FETCH]:
        data = fetch_json(f"{BASE}/api/v4/videoid/{track['video_id']}.json")
        time.sleep(DELAY)
        if not data:
            continue

        in_window = [(d, v) for d, v in parse_stats(data) if start <= d <= end]
        if not in_window:
            continue
        gain = sum(v for _, v in in_window)
        if gain < MIN_GAIN:
            continue

        pictures = {
            m["nickname"]: m["pictureurl"]
            for m in (data.get("memberdata") or [])
            if m.get("nickname") and m.get("pictureurl")
        }

        songs.append({
            "video_id": track["video_id"],
            "title": TITLE_TAIL_RE.sub(
                "", track.get("music_name") or track.get("video_name") or ""
            ).strip(),
            "artists": TITLE_TAIL_RE.sub("", track.get("artists") or "").strip(),
            "pictures": pictures,
            "channel": track.get("channel_name"),
            "office": track.get("offices"),
            "type": track.get("type"),
            "published_at": track.get("published_at"),
            "views_gained": gain,
            "days_covered": len(in_window),
            "thumbnail": f"https://i.ytimg.com/vi/{track['video_id']}/hqdefault.jpg",
        })

    songs.sort(key=lambda e: (-e["views_gained"], e["published_at"] or ""))
    ranked_songs = songs[:MAX_ENTRIES]

    artists = {}
    for song in songs:
        names = set(split_artists(song["artists"])) or {song.get("channel") or ""}
        for name in names:
            if not name:
                continue
            rec = artists.setdefault(name, {"gain": 0, "count": 0, "top": song, "picture": ""})
            rec["gain"] += song["views_gained"]
            rec["count"] += 1
            if not rec["picture"]:
                rec["picture"] = song["pictures"].get(name, "")
            if song["views_gained"] > rec["top"]["views_gained"]:
                rec["top"] = song

    artist_rows = [
        {
            "name": name,
            "picture": rec.get("picture") or rec["top"]["thumbnail"],
            "office": rec["top"].get("office"),
            "views_gained": rec["gain"],
            "video_count": rec["count"],
            "top_video": {
                "video_id": rec["top"]["video_id"],
                "title": rec["top"]["title"],
                "thumbnail": rec["top"]["thumbnail"],
                "views_gained": rec["top"]["views_gained"],
            },
        }
        for name, rec in artists.items()
    ]
    artist_rows.sort(key=lambda a: -a["views_gained"])
    ranked_artists = artist_rows[:MAX_ENTRIES]

    for song in ranked_songs:
        song.pop("pictures", None)

    past_week = past_week_for(end)
    apply_history(ranked_songs, history("entries", end.isoformat()), past_week, lambda e: e["video_id"])
    apply_history(ranked_artists, history("artists", end.isoformat()), past_week, lambda a: a["name"])

    payload = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entries": ranked_songs,
        "artists": ranked_artists,
    }

    os.makedirs(ARCHIVE, exist_ok=True)
    with open(os.path.join(ARCHIVE, f"{end.isoformat()}.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": ranked_songs, "artists": ranked_artists}, f, ensure_ascii=False, indent=2)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"songs={len(ranked_songs)} artists={len(ranked_artists)}")
    for e in ranked_songs[:5]:
        print(f"  song #{e['rank']} {e['views_gained']:>8,} {e['title']}")
    for a in ranked_artists[:5]:
        print(f"  artist #{a['rank']} {a['views_gained']:>8,} {a['name']} ({a['video_count']} vids)")


if __name__ == "__main__":
    main()
