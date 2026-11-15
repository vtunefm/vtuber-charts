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
MAX_ENTRIES = 10
MAX_FETCH = 200

TRACKS = "data/tracks.csv"
OUT = "data/chart.json"

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
    start = end - timedelta(days=5)
    return start, end


def parse_stats(data):
    stats = data.get("statisticsdata") or []
    if len(stats) < 3:
        return []
    dates, views = stats[1], stats[2]
    out = []
    for raw, count in zip(dates, views):
        m = DATE_RE.match(str(raw))
        if not m:
            continue
        try:
            out.append((date(int(m.group(1)), int(m.group(2)), int(m.group(3))), int(count)))
        except ValueError:
            continue
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

    entries = []
    for track in eligible[:MAX_FETCH]:
        data = fetch_json(f"{BASE}/api/v4/videoid/{track['video_id']}.json")
        time.sleep(DELAY)
        if not data:
            continue

        series = parse_stats(data)
        in_window = [(d, v) for d, v in series if start <= d <= end]
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
            "video_name": track.get("video_name"),
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
    chart = entries[:MAX_ENTRIES]

    for i, entry in enumerate(chart, start=1):
        entry["rank"] = i

    payload = {
        "week_start": start.isoformat(),
        "week_end": end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entry_count": len(chart),
        "entries": chart,
    }

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"wrote {len(chart)} entries to {OUT}")
    for e in chart:
        print(f"  #{e['rank']} {e['views_gained']:>8,} ({e['days_covered']}d) {e['title']}")


if __name__ == "__main__":
    main()
