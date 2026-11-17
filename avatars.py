import csv
import os
import re
import time

from googleapiclient.discovery import build

API_KEY = os.environ.get("YOUTUBE_API_KEY")
if not API_KEY:
    raise SystemExit("missing YOUTUBE_API_KEY")

youtube = build("youtube", "v3", developerKey=API_KEY)

TRACKS = "data/tracks.csv"
CANDS = "data/candidates.csv"
OUT = "data/avatars.csv"
BATCH = 50

TCOLS = [
    "video_id", "video_name", "music_name", "channel_name", "channel_key",
    "channel_id", "artists", "offices", "published_at", "duration_sec", "type",
    "is_short", "is_long", "first_stat_date", "latest_views", "latest_likes",
    "discovered_via", "first_seen", "status",
]

SPLIT_RE = re.compile(r"\s*/\s*")
CH_SUFFIX_RE = re.compile(r"\s*ch\.?\s*$", re.I)
CH_PREFIX_RE = re.compile(r"^.*?\bch\.?\s+", re.I)


def variants(text):
    """Every spelling of a channel name we are willing to match on."""
    out = set()
    for part in SPLIT_RE.split(text or ""):
        p = part.strip().lower()
        if not p:
            continue
        out.add(p)
        out.add(CH_SUFFIX_RE.sub("", p).strip())
        out.add(CH_PREFIX_RE.sub("", p).strip())
    return {v for v in out if v}


def load_candidate_ids():
    """name variants -> channel_id, plus channel_ids worth fetching regardless."""
    by_name = {}
    wanted = set()
    if not os.path.exists(CANDS):
        return by_name, wanted

    with open(CANDS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = (row.get("channel_id") or "").strip()
            if not cid:
                continue
            for name in (row.get("channel_name"), row.get("handle")):
                for v in variants(name):
                    by_name.setdefault(v, cid)
            if (row.get("status") or "") in ("approved", "done"):
                wanted.add(cid)
    return by_name, wanted


def backfill_channel_ids(by_name):
    if not (os.path.exists(TRACKS) and by_name):
        return 0

    with open(TRACKS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    filled = 0
    for row in rows:
        if row.get("channel_id"):
            continue
        for source in (row.get("channel_name"), row.get("channel_key")):
            hit = next((by_name[v] for v in variants(source) if v in by_name), None)
            if hit:
                row["channel_id"] = hit
                filled += 1
                break

    if filled:
        with open(TRACKS, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=TCOLS)
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k, "") for k in TCOLS})

    return filled


def main():
    by_name, wanted = load_candidate_ids()
    print(f"{len(by_name)} known channel name(s), {len(wanted)} approved channel(s)")

    filled = backfill_channel_ids(by_name)
    print(f"backfilled {filled} channel_id(s)")

    if not os.path.exists(TRACKS):
        print("no tracks.csv")
        return

    with open(TRACKS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    ids = {r.get("channel_id") for r in rows if r.get("channel_id")}
    ids |= wanted
    ids = sorted(ids)
    print(f"{len(rows)} track(s), {len(ids)} channel(s) to cover")

    known = set()
    if os.path.exists(OUT):
        with open(OUT, newline="", encoding="utf-8") as f:
            known = {r["channel_id"] for r in csv.DictReader(f)}

    todo = [i for i in ids if i not in known]
    print(f"{len(todo)} avatar(s) to fetch of {len(ids)} channel(s)")

    os.makedirs("data", exist_ok=True)
    fresh = not os.path.exists(OUT)
    written = 0

    with open(OUT, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["channel_id", "avatar"])
        if fresh:
            w.writeheader()

        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            try:
                resp = youtube.channels().list(
                    part="snippet", id=",".join(chunk)
                ).execute()
            except Exception as e:
                print(f"batch failed: {e}")
                time.sleep(3)
                continue
            for item in resp.get("items", []):
                thumbs = item.get("snippet", {}).get("thumbnails", {})
                url = (
                    thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}
                ).get("url")
                if url:
                    w.writerow({"channel_id": item["id"], "avatar": url})
                    written += 1
            time.sleep(0.3)

    print(f"wrote {written} avatar row(s)")


if __name__ == "__main__":
    main()
