import csv
import os
import sys
import time

from googleapiclient.discovery import build

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise SystemExit("missing YOUTUBE_API_KEY")

youtube = build("youtube", "v3", developerKey=API_KEY)

ROSTER = "roster.csv"
OUT = "data/channels.csv"
COLS = ["name", "handle", "channel_id", "channel_title", "subscribers", "status"]


def to_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def read_roster():
    rows = []
    seen = set()
    with open(ROSTER, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # header is literally `0name, youtube_handle`
        for rec in reader:
            if len(rec) < 2:
                continue
            name = (rec[0] or "").strip()
            handle = (rec[1] or "").strip()
            if not name:
                continue
            if handle and not handle.startswith("@"):
                handle = "@" + handle
            key = handle.lower()
            if handle and key in seen:
                print(f"duplicate handle skipped: {name} {handle}")
                continue
            if handle:
                seen.add(key)
            rows.append({"name": name, "handle": handle})
    return rows


def resolve(handle):
    for attempt in range(4):
        try:
            resp = youtube.channels().list(
                part="snippet,statistics", forHandle=handle
            ).execute()
        except Exception as e:
            if attempt == 3:
                raise
            print(f"  retry {attempt + 1}: {str(e)[:100]}")
            time.sleep(2 * (attempt + 1))
            continue
        items = resp.get("items") or []
        if not items:
            return None
        item = items[0]
        sn = item.get("snippet", {})
        return {
            "channel_id": item["id"],
            "channel_title": sn.get("title", ""),
            "created_at": (sn.get("publishedAt") or "")[:10],
            "subscribers": to_int(item.get("statistics", {}).get("subscriberCount")),
        }


def main():
    if not os.path.exists(ROSTER):
        print("no roster.csv")
        return

    rows = read_roster()
    print(f"{len(rows)} roster row(s)")
    os.makedirs("data", exist_ok=True)

    resolved = missing = blank = 0
    out = []

    for row in rows:
        if not row["handle"]:
            print(f"no handle: {row['name']}")
            out.append({**row, "channel_id": "", "channel_title": "", "subscribers": 0, "status": "blank"})
            blank += 1
            continue
        try:
            hit = resolve(row["handle"])
        except Exception as e:
            print(f"failed {row['name']} {row['handle']}: {str(e)[:100]}")
            hit = None
        if not hit:
            print(f"unresolved: {row['name']} {row['handle']}")
            out.append({**row, "channel_id": "", "channel_title": "", "subscribers": 0, "status": "missing"})
            missing += 1
            continue
        out.append({**row, **hit, "status": "ok"})
        resolved += 1
        time.sleep(0.1)

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for row in out:
            w.writerow({k: row.get(k, "") for k in COLS})

    print(f"resolved {resolved}, unresolved {missing}, no handle {blank}")
    if not resolved:
        sys.exit(1)


if __name__ == "__main__":
    main()
