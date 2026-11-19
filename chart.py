import csv
import json
import os
import re
from datetime import date, datetime, timedelta, timezone

MIN_GAIN = 1
MAX_ENTRIES = 100
MAX_FETCH = 5000
MIN_DURATION = 120
MAX_DURATION = 420
FRIDAY = 4

# Billboard's recurrent rule: (weeks on chart, position it must beat to survive).
RECURRENT = ((78, 5), (52, 10), (26, 25), (20, 50))

TRACKS = "data/tracks.csv"
SNAPSHOTS = "data/snapshots.csv"
AVATARS = "data/avatars.csv"
CHANNELS = "data/channels.csv"
OUT = "data/chart.json"
ARCHIVE = "data/archive"
HISTORY = "data/history"

CHANNEL = "https://www.youtube.com/channel/{}"

TITLE_TAIL_RE = re.compile(r"\s*[（(]?\s*(cover|カバー)\s*[)）]?\s*$", re.I)
ARTIST_SPLIT_RE = re.compile(r"\s*/\s*")
CH_SUFFIX_RE = re.compile(r"\s*ch\.?\s*$", re.I)
CH_PREFIX_RE = re.compile(r"^.*?\bch\.?\s+", re.I)
CH_HEAD_RE = re.compile(r"\bch\.?\b.*$", re.I)

# Offices and agencies. They take a credit only when they are the uploader —
# group songs are released on the company channel and nowhere else — and never
# as a trailing source tag on somebody's own video.
OFFICE_TAGS = {
    "hololive", "hololive en", "hololive id", "hololive dev_is", "holostars",
    "holostars en", "nijisanji", "nijisanji en", "nijisanji id", "nijisanji kr",
    "regloss", "flow glow", "vspo", "vsinger", "aogiri", "neo-porte",
    "phase connect", "idol corp", "prism project", "kizuna ai inc.",
}


def to_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


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


def choose_window():
    """Billboard-style tracking week: Friday 00:00 to Thursday 23:59 UTC.

    The boundary sits on the industry release day, so a Friday drop gets the
    whole window instead of the tail of it. On Friday the chart shows the week
    that closed yesterday; from Saturday it shows the new week to date.
    """
    today = datetime.now(timezone.utc).date()
    back = (today.weekday() - FRIDAY) % 7
    friday = today - timedelta(days=7 if back == 0 else back)
    thursday = friday + timedelta(days=6)
    end = min(today, thursday)
    return friday, end, end < thursday


def past_week_for(end):
    if not os.path.isdir(ARCHIVE):
        return None
    weeks = sorted(n[:-5] for n in os.listdir(ARCHIVE) if n.endswith(".json"))
    weeks = [w for w in weeks if w < end.isoformat()]
    return weeks[-1] if weeks else None


def load_week(week):
    path = os.path.join(ARCHIVE, f"{week}.json")
    if not week or not os.path.exists(path):
        return {}, {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}, {}
    return data.get("entries") or [], data.get("artists") or []


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
            ident = entry.get("video_id") or entry.get("channel_id") or entry.get("name")
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


def is_recurrent(entry):
    return any(
        entry["weeks_on_chart"] >= weeks and entry["rank"] > position
        for weeks, position in RECURRENT
    )


def rerank(items):
    for i, item in enumerate(items, start=1):
        item["rank"] = i
        item["peak"] = min(item["peak"], i)
        last = item.get("last_week")
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


def is_office(name):
    return (name or "").strip().lower() in OFFICE_TAGS


def title_variants(text):
    out = set()
    for part in ARTIST_SPLIT_RE.split(text or ""):
        p = part.strip().lower()
        if not p:
            continue
        out.add(p)
        out.add(CH_SUFFIX_RE.sub("", p).strip())
        out.add(CH_PREFIX_RE.sub("", p).strip())
        out.add(CH_HEAD_RE.sub("", p).strip())
    return {v for v in out if v}


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
    """channel_id -> canonical English name, plus every accepted spelling -> that name."""
    by_id, alias = {}, {}
    if not os.path.exists(CHANNELS):
        return by_id, alias
    with open(CHANNELS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = (row.get("channel_id") or "").strip()
            name = (row.get("name") or "").strip()
            if not cid or not name or row.get("status") != "ok":
                continue
            by_id[cid] = name
            alias[name.lower()] = name
            for v in title_variants(row.get("channel_title")):
                alias.setdefault(v, name)
    return by_id, alias


def carry_over(songs, artists_prev, end):
    """Hold last week's slots at zero so the grid survives the week rollover."""
    prev_week = past_week_for(end)
    if not prev_week:
        return 0, 0, None
    prev_entries, prev_artists = load_week(prev_week)

    have = {s["video_id"] for s in songs}
    added = 0
    for entry in prev_entries:
        vid = entry.get("video_id")
        if not vid or vid in have:
            continue
        carry = dict(entry)
        carry["views_gained"] = 0
        carry["days_covered"] = 0
        songs.append(carry)
        have.add(vid)
        added += 1

    return added, len(prev_artists), prev_week


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
        and (not to_int(t.get("duration_sec"))
             or MIN_DURATION <= to_int(t.get("duration_sec")) <= MAX_DURATION)
    ]
    print(f"{len(eligible)}/{len(tracks)} eligible after filters")

    deltas = snapshot_deltas()
    avatars = load_avatars()
    names_by_id, title_alias = load_channels()
    id_by_name = {n.lower(): i for i, n in names_by_id.items()}
    print(f"{len(avatars)} avatar(s) · {len(names_by_id)} known channel(s)")
    start, end, partial = choose_window()
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
            "artist_name": track.get("artist_name") or "",
            "channel": track.get("channel_name"),
            "channel_id": track.get("channel_id"),
            "channel_key": track.get("channel_key"),
            "office": track.get("offices"),
            "type": track.get("type"),
            "published_at": track.get("published_at"),
            "views_gained": gain,
            "days_covered": len(hits),
            "duration_sec": to_int(track.get("duration_sec")),
            "thumbnail": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        })

    print(f"qualified={len(songs)}")
    carried, prev_artist_count, prev_week = carry_over(songs, [], end)
    if carried:
        print(f"carried {carried} slot(s) over from {prev_week} at 0")

    entry_hist = history("entries", end.isoformat())
    artist_hist = history("artists", end.isoformat())
    past_week = past_week_for(end)

    def entry_last(entry):
        rec = entry_hist.get(entry["video_id"], {}).get("by_week", {})
        return rec.get(past_week) if past_week else None

    songs.sort(key=lambda e: (-e["views_gained"], entry_last(e) or 999,
                              e.get("published_at") or ""))
    ranked_songs = songs[:MAX_ENTRIES]

    artists = {}
    unresolved = set()
    splits = 0
    for song in songs:
        names = split_artists(song["artists"])
        owner_id = song.get("channel_id") or ""
        owner_name = names_by_id.get(owner_id) or song.get("artist_name") or ""

        if len(names) <= 1:
            credits = {owner_id or owner_name.lower(): (owner_name, owner_id)}
        else:
            credits = {}
            for name in names:
                low = name.lower()
                cid = id_by_name.get(low, "")
                if not cid:
                    hit = title_alias.get(low)
                    if hit:
                        cid = id_by_name.get(hit.lower(), "")
                        name = hit

                if is_office(name):
                    # Office counts only as the uploader. As a trailing source tag
                    # it would take a share off the actual artist.
                    if (cid and cid == owner_id) or low == owner_name.lower():
                        credits[cid or owner_name.lower()] = (name, cid or owner_id)
                    continue

                if not cid:
                    unresolved.add(name)
                credits[cid or name.lower()] = (name, cid)

            if not credits:
                credits[owner_id or owner_name.lower()] = (owner_name, owner_id)
            elif len(credits) > 1:
                splits += 1

        share = song["views_gained"] / max(1, len(credits))

        for name, cid in credits.values():
            if not name:
                continue
            key = cid or name.lower()
            rec = artists.setdefault(key, {
                "name": name, "display": name, "gain": 0.0, "count": 0,
                "top": song, "top_share": share, "channel_id": cid,
                "channel_url": "", "picture": "",
            })
            if cid and not rec["channel_url"]:
                rec["channel_url"] = CHANNEL.format(cid)
                rec["picture"] = avatars.get(cid, "")
            rec["gain"] += share
            rec["count"] += 1
            if song["views_gained"] > rec["top"]["views_gained"]:
                rec["top"] = song
                rec["top_share"] = share

    # Carry last week's artists in at zero too, so the artist grid holds shape.
    for entry in (load_week(past_week)[1] if past_week else []):
        key = entry.get("channel_id") or (entry.get("name") or "").lower()
        if not key or key in artists:
            continue
        artists[key] = {
            "name": entry.get("name") or "", "display": entry.get("display") or "",
            "gain": 0.0, "count": 0, "top": None, "top_share": 0.0,
            "channel_id": entry.get("channel_id") or "",
            "channel_url": entry.get("channel_url") or "",
            "picture": entry.get("picture") or "",
            "fallback": entry.get("top_video") or {},
        }

    merged = 0
    for key in [k for k, r in artists.items() if not r["channel_id"]]:
        rec = artists[key]
        twin = next(
            (k for k, r in artists.items()
             if r["channel_id"] and r["name"].lower() == rec["name"].lower()),
            None,
        )
        if not twin:
            continue
        target = artists[twin]
        target["gain"] += rec["gain"]
        target["count"] += rec["count"]
        if rec["top"] and (not target["top"]
                           or rec["top"]["views_gained"] > target["top"]["views_gained"]):
            target["top"] = rec["top"]
            target["top_share"] = rec["top_share"]
        del artists[key]
        merged += 1

    office_rows = sum(1 for r in artists.values() if is_office(r["name"]))
    print(f"merged {merged} name-only duplicate(s) · {splits} collab(s) split · "
          f"{office_rows} office channel(s)")

    pictured = sum(1 for r in artists.values() if r["picture"])
    linked = sum(1 for r in artists.values() if r["channel_url"])
    print(f"artist pictures {pictured}/{len(artists)} · channels {linked}/{len(artists)}")
    if unresolved:
        print(f"{len(unresolved)} unresolved credit(s): " + ", ".join(sorted(unresolved)))

    artist_rows = []
    for rec in artists.values():
        top = rec["top"]
        fallback = rec.get("fallback") or {}
        artist_rows.append({
            "name": rec["name"],
            "display": rec["display"] or rec["name"],
            "channel_id": rec["channel_id"],
            "channel_url": rec["channel_url"],
            "picture": rec["picture"] or (top["thumbnail"] if top
                                          else fallback.get("thumbnail", "")),
            "office": top.get("office") if top else "",
            "office_channel": is_office(rec["name"]),
            "views_gained": int(round(rec["gain"])),
            "video_count": rec["count"],
            "top_video": {
                "video_id": top["video_id"] if top else fallback.get("video_id", ""),
                "title": top["title"] if top else fallback.get("title", ""),
                "thumbnail": top["thumbnail"] if top else fallback.get("thumbnail", ""),
                "views_gained": int(round(rec["top_share"])),
            },
        })

    def artist_last(entry):
        ident = entry["channel_id"] or entry["name"]
        rec = artist_hist.get(ident, {}).get("by_week", {})
        return rec.get(past_week) if past_week else None

    artist_rows.sort(key=lambda a: (-a["views_gained"], -a["video_count"],
                                    artist_last(a) or 999, a["name"]))
    ranked_artists = artist_rows[:MAX_ENTRIES]

    apply_history(ranked_songs, entry_hist, past_week, lambda e: e["video_id"])
    apply_history(ranked_artists, artist_hist, past_week,
                  lambda a: a["channel_id"] or a["name"])

    pruned = [e for e in ranked_songs if not is_recurrent(e)]
    if len(pruned) != len(ranked_songs):
        print(f"recurrent rule removed {len(ranked_songs) - len(pruned)} song(s)")
        ranked_songs = pruned
        rerank(ranked_songs)

    payload = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "chart_date": (end + timedelta(days=2)).isoformat(),
        "partial": partial,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entries": ranked_songs,
        "artists": ranked_artists,
    }

    os.makedirs(ARCHIVE, exist_ok=True)
    with open(os.path.join(ARCHIVE, f"{end.isoformat()}.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": ranked_songs, "artists": ranked_artists}, f,
                  ensure_ascii=False, indent=2)

    if not partial:
        os.makedirs(HISTORY, exist_ok=True)
        with open(os.path.join(HISTORY, f"{end.isoformat()}.json"), "w",
                  encoding="utf-8") as f:
            json.dump({
                "week_start": start.isoformat(),
                "week_end": end.isoformat(),
                "chart_date": payload["chart_date"],
                "generated_at": payload["generated_at"],
                "top10": ranked_songs[:10],
            }, f, ensure_ascii=False, indent=2)
        print(f"wrote top-10 record for {end.isoformat()}")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"songs={len(ranked_songs)} artists={len(ranked_artists)}")


if __name__ == "__main__":
    main()
