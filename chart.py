import csv
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

MIN_GAIN = 1
MAX_ENTRIES = 100
MAX_FETCH = 5000

TRACKS = "data/tracks.csv"
SNAPSHOTS = "data/snapshots.csv"
AVATARS = "data/avatars.csv"
OUT = "data/chart.json"
ARCHIVE = "data/archive"

TITLE_TAIL_RE = re.compile(r"\s*[（(]?\s*(cover|カバー)\s*[)）]?\s*$", re.I)
ARTIST_SPLIT_RE = re.compile(r"\s*/\s*")
ROMAJI_CUT_RE = re.compile(r"\s*(?:Ch\.|【|/|｜|\|).*$")


def to_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def has_latin(text):
    return any("a" <= ch.lower() <= "z" for ch in text or "")


def display_name(name, channel):
    base = ROMAJI_CUT_RE.sub("", channel or "").strip()
    return base if base and has_latin(base) else name


def window():
    today = datetime.now(timezone.utc).date()
    days_back = (today.weekday() - 5) % 7
    end = today - timedelta(days=days_back)
    return end - timedelta(days=5), end


def snapshot_deltas():
    gains = {}
    if not os.path.exists(SNAPSHOTS):
        return gains
    series = {}
    with open(SNAPSHOTS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vid = row.get("video_id")
            stamp = row.get("snapshot_at") or ""
            if not vid or len(stamp) < 10:
                continue
            series.setdefault(vid, []).append((stamp, to_int(row.get("view_count"))))
    for vid, points in series.items():
        points.sort()
        per_day = {}
        for (_, prev), (stamp, cur) in zip(points, points[1:]):
            try:
                day = date.fromisoformat(stamp[:10])
            except ValueError:
                continue
            per_day[day] = per_day.get(day, 0) + max(0, cur - prev)
        if per_day:
            gains[vid] = per_day
    return gains


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
            ident = entry.get("video_id") or entry.get("display") or entry.get("name")
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


def load_avatars():
    out = {}
    if not os.path.exists(AVATARS):
        return out
    with open(AVATARS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("channel_id") and row.get("avatar"):
                out[row["channel_id"]] = row["avatar"]
    return out


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

    deltas = snapshot_deltas()
    avatars = load_avatars()
    print(f"snapshot coverage: {len(deltas)} · avatars: {len(avatars)}")

    songs = []
    for track in eligible[:MAX_FETCH]:
        vid = track["video_id"]
        per_day = deltas.get(vid)
        if not per_day:
            continue
        hits = [(d, v) for d, v in per_day.items() if start <= d <= end]
        if not hits:
            continue
        gain = sum(v for _, v in hits)
        if gain < MIN_GAIN:
            continue

        artists_raw = (track.get("artists") or "").strip()
        credited = {a.lower() for a in split_artists(artists_raw)}
        title = TITLE_TAIL_RE.sub("", track.get("music_name") or "").strip()
        if (
            not title
            or title.lower() in credited
            or title.lower() == (track.get("channel_key") or "").lower()
        ):
            title = TITLE_TAIL_RE.sub("", track.get("video_name") or "").strip()

        songs.append({
            "video_id": vid,
            "title": title,
            "artists": artists_raw,
            "channel": track.get("channel_name"),
            "channel_id": track.get("channel_id"),
            "office": track.get("offices"),
            "type": track.get("type"),
            "published_at": track.get("published_at"),
            "views_gained": gain,
            "days_covered": len(hits),
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        })

    print(f"qualified={len(songs)}")
    if not songs:
        print("no gains yet — needs at least two snapshot runs")

    songs.sort(key=lambda e: (-e["views_gained"], e["published_at"] or ""))
    ranked_songs = songs[:MAX_ENTRIES]

    alias = {}
    for song in songs:
        names = split_artists(song["artists"])
        if len(names) == 1:
            alias.setdefault(names[0], display_name(names[0], song.get("channel")))

    artists = {}
    for song in songs:
        names = set(split_artists(song["artists"])) or {song.get("channel") or ""}
        for name in names:
            if not name:
                continue
            disp = alias.get(name) or display_name(name, song.get("channel")) or name
            rec = artists.setdefault(disp, {
                "name": name, "display": disp, "gain": 0, "count": 0,
                "top": song, "picture": avatars.get(song.get("channel_id") or "", ""),
            })
            rec["gain"] += song["views_gained"]
            rec["count"] += 1
            if not rec["picture"]:
                rec["picture"] = avatars.get(song.get("channel_id") or "", "")
            if song["views_gained"] > rec["top"]["views_gained"]:
                rec["top"] = song

    artist_rows = [
        {
            "name": rec["name"],
            "display": rec["display"],
            "picture": rec["picture"] or rec["top"]["thumbnail"],
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
        for rec in artists.values()
    ]
    artist_rows.sort(key=lambda a: -a["views_gained"])
    ranked_artists = artist_rows[:MAX_ENTRIES]

    past_week = past_week_for(end)
    apply_history(ranked_songs, history("entries", end.isoformat()), past_week, lambda e: e["video_id"])
    apply_history(ranked_artists, history("artists", end.isoformat()), past_week, lambda a: a["display"])

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


if __name__ == "__main__":
    main()
