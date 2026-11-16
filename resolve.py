import csv
import json
import os
import time
import urllib.parse

import yt_dlp

ROSTER = "roster.txt"
CANDS = "data/candidates.csv"
STATE = "data/roster_state.json"
COLS = ["query", "channel_id", "channel_name", "handle", "subscribers", "status", "note"]
PER_RUN = 30
PER_QUERY = 3

CHANNEL_FILTER = "&sp=EgIQAg%253D%253D"


def channel_search(query):
    url = (
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote(query)
        + CHANNEL_FILTER
    )
    opts = {"extract_flat": True, "quiet": True, "playlistend": PER_QUERY * 2}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"channel search failed [{query}]: {e}")
        return []

    out = []
    for entry in info.get("entries") or []:
        if not entry:
            continue
        cid = entry.get("channel_id") or entry.get("id")
        if not cid:
            continue
        out.append({
            "query": query,
            "channel_id": cid,
            "channel_name": entry.get("channel") or entry.get("title") or "",
            "handle": entry.get("url") or "",
            "subscribers": entry.get("channel_follower_count") or "",
            "status": "pending",
            "note": "",
        })
    return out


def video_fallback(query):
    opts = {"extract_flat": True, "quiet": True, "playlistend": 10}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch10:{query}", download=False)
    except Exception as e:
        print(f"fallback failed [{query}]: {e}")
        return []

    out, seen = [], set()
    for entry in info.get("entries") or []:
        if not entry:
            continue
        cid = entry.get("channel_id") or entry.get("uploader_id")
        if not cid or cid in seen:
            continue
        seen.add(cid)
        out.append({
            "query": query,
            "channel_id": cid,
            "channel_name": entry.get("channel") or entry.get("uploader") or "",
            "handle": "",
            "subscribers": "",
            "status": "pending",
            "note": "via video search",
        })
    return out


def main():
    if not os.path.exists(ROSTER):
        print("no roster.txt")
        return

    with open(ROSTER, encoding="utf-8") as f:
        names = [n.strip() for n in f if n.strip() and not n.startswith("#")]

    os.makedirs("data", exist_ok=True)

    attempted = set()
    if os.path.exists(STATE):
        try:
            with open(STATE, encoding="utf-8") as f:
                attempted = set(json.load(f).get("attempted", []))
        except Exception:
            attempted = set()

    todo = [n for n in names if n.lower() not in attempted][:PER_RUN]
    print(f"{len(todo)} to resolve · {len(attempted)} already attempted · {len(names)} total")

    fresh = not os.path.exists(CANDS)
    with open(CANDS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if fresh:
            w.writeheader()

        for name in todo:
            found = channel_search(name)
            if not found:
                found = video_fallback(name)
            uniq, seen_ids = [], set()
            for row in found:
                if row["channel_id"] in seen_ids:
                    continue
                seen_ids.add(row["channel_id"])
                uniq.append(row)
            uniq = uniq[:PER_QUERY]

            print(f"{name}: {len(uniq)} candidate(s)")
            for row in uniq:
                w.writerow(row)
            attempted.add(name.lower())
            time.sleep(1.0)

    with open(STATE, "w", encoding="utf-8") as f:
        json.dump({"attempted": sorted(attempted)}, f)

    print("review data/candidates.csv — set status to approved on the right rows")


if __name__ == "__main__":
    main()
