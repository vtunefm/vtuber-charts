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
CANDS = "data/candidates.csv"
OUT = "data/chart.json"
ARCHIVE = "data/archive"

CHANNEL = "https://www.youtube.com/channel/{}"

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


def choose_window(deltas):
    today = datetime.now(timezone.utc).date()
    days_back = (today.weekday() - 5) % 7
    end = today - timedelta(days=days_back)
    start = end - timedelta(days=5)

    days = {d for per_day in deltas.values() for d in per_day}
    if not days or any(start <= d <= end for d in days):
        return start, end, False

    latest = max(days)
    monday = latest - timedelta(days=latest.weekday())
    return monday, latest, True


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


def load_channels():
    """Curated channels only — rejected clip channels never enter this index."""
    index = []
    if not os.path.exists(CANDS):
        return index
    with open(CANDS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("status") or "") not in ("done", "approved"):
                continue
            cid = (row.get("channel_id") or "").strip()
            name = (row.get("channel_name") or "").strip().lower()
            if not cid or not name:
                continue
            index.append({
                "id": cid,
                "name": name,
                "subs": to_int(row.get("subscribers")),
                "topic": name.endswith("- topic"),
            })
    return index


def find_channel(name, index):
    key = (name or "").strip().lower()
    if len(key) < 3:
        return None
    hits = [c for c in index if key in c["name"]]
    if not hits:
        return None
    hits.sort(key=lambda c: (c["topic"], -c["subs"]))
    return hits[0]


def resolve_artist(name, song, index, avatars):
    """Own channel first; the uploader only when this artist is the uploader."""
    hit = find_channel(name, index)
    if hit:
        cid = hit["id"]
    else:
        cid = ""
        channel = (song.get("channel") or "").lower()
        key = (name or "").lower()
        if key and (key in channel or (song.get("channel_key") or "").lower() == key):
            cid = song.get("channel_id") or ""
    url = CHANNEL.format(cid) if cid else ""
    return cid, url, avatars.get(cid, "")


def main():
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
    index = load_channels()
    print(f"{len(avatars)} avatar(s) known · {len(index)} curated channel(s)")
    start, end, partial = choose_window(deltas)
    print(f"window: {start} .. {end} (partial={partial}) · snapshot tracks={len(deltas)}")

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
            "channel_key": track.get("channel_key"),
            "office": track.get("offices"),
            "type": track.get("type"),
            "published_at": track.get("published_at"),
            "views_gained": gain,
            "days_covered": len(hits),
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        })

    print(f"qualified={len(songs)}")
    if not songs:
        print("no gains yet — needs two snapshot runs on the same tracks")

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
                "top": song, "channel_id": "", "channel_url": "", "picture": "",
            })
            if not rec["channel_id"]:
                cid, url, pic = resolve_artist(name, song, index, avatars)
                rec["channel_id"] = cid
                rec["channel_url"] = url
                rec["picture"] = pic
            rec["gain"] += song["views_gained"]
            rec["count"] += 1
            if song["views_gained"] > rec["top"]["views_gained"]:
                rec["top"] = song

    pictured = sum(1 for rec in artists.values() if rec["picture"])
    linked = sum(1 for rec in artists.values() if rec["channel_url"])
    print(f"artist pictures {pictured}/{len(artists)} · channels {linked}/{len(artists)}")

    artist_rows = [
        {
            "name": rec["name"],
            "display": rec["display"],
            "channel_id": rec["channel_id"],
            "channel_url": rec["channel_url"],
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
        "partial": partial,
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
