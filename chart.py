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
MIN_GAIN = 500
MAX_ENTRIES = 20
MAX_FETCH = 200

TRACKS = "data/tracks.csv"
OUT = "data/chart.json"
ARCHIVE = "data/archive"

DATE_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2})$")
TITLE_TAIL_RE = re.compile(r"\s*(cover|カバー)\s*$", re.I)


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


def history():
    records = {}
    if not os.path.isdir(ARCHIVE):
        return records
    for name in sorted(os.listdir(ARCHIVE)):
        if not name.endswith(".json"):
            continue
        week = name[:-5]
        try:
            with open(os.path.join(ARCHIVE, name), encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        for entry in data.get("entries", []):
            rec = records.setdefault(entry["video_id"], {"peak": 999, "by_week": {}})
            rec["peak"] = min(rec["peak"], entry["rank"])
            rec["by_week"][week] = entry["rank"]
    return records


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

    entries = []
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

        entries.append({
            "video_id": track["video_id"],
            "title": TITLE_TAIL_RE.sub(
                "", track.get("music_name") or track.get("video_name") or ""
            ).strip(),
            "artists": TITLE_TAIL_RE.sub("", track.get("artists") or "").strip(),
            "channel": track.get("channel_name"),
            "office": track.get("offices"),
            "type": track.get("type"),
            "published_at": track.get("published_at"),
            "views_gained": gain,
            "days_covered": len(in_window),
            "thumbnail": f"https://i.ytimg.com/vi/{track['video_id']}/hqdefault.jpg",
        })

    entries.sort(key=lambda e: (-e["views_gained"], e["published_at"] or ""))
    ranked = entries[:MAX_ENTRIES]

    records = history()
    prior_weeks = [w for w in records.get("__weeks__", [])]
    past_week = None
    if os.path.isdir(ARCHIVE):
        past = sorted(n[:-5] for n in os.listdir(ARCHIVE) if n.endswith(".json"))
        past = [w for w in past if w < end.isoformat()]
        past_week = past[-1] if past else None

    for i, entry in enumerate(ranked, start=1):
        entry["rank"] = i
        rec = records.get(entry["video_id"], {"peak": i, "by_week": {}})
        last = rec["by_week"].get(past_week) if past_week else None
        entry["last_week"] = last
        entry["peak"] = min(rec["peak"], i)
        entry["weeks_on_chart"] = len(rec["by_week"]) + 1
        if last is None:
            entry["movement"] = "new"
        elif i < last:
            entry["movement"] = "up"
        elif i > last:
            entry["movement"] = "down"
        else:
            entry["movement"] = "same"

    payload = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entry_count": len(ranked),
        "entries": ranked,
    }

    os.makedirs(ARCHIVE, exist_ok=True)
    with open(os.path.join(ARCHIVE, f"{end.isoformat()}.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": ranked}, f, ensure_ascii=False, indent=2)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"wrote {len(ranked)} entries")
    for e in ranked:
        print(f"  #{e['rank']} {e['movement']:<4} LW={e['last_week']} PK={e['peak']} "
              f"{e['weeks_on_chart']}w  {e['views_gained']:>8,}  {e['title']}")


if __name__ == "__main__":
    main()
