import csv
import os
import time
import urllib.parse

import yt_dlp

ROSTER = "roster.txt"
CANDS = "data/candidates.csv"
COLS = ["query", "channel_id", "channel_name", "handle", "subscribers", "status", "note"]
PER_RUN = 10
PER_QUERY = 5

CHANNEL_FILTER = "&sp=EgIQAg%253D%253D"


def channel_search(query):
    url = (
        "https://www.youtube.com/results?search_query="
        + urllib.parse.quote(query)
        + CHANNEL_FILTER
    )
    opts = {"extract_flat": True, "quiet": True, "playlistend": PER_QUERY}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        print(f"search failed [{query}]: {e}")
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
    return out[:PER_QUERY]


def main():
    if not os.path.exists(ROSTER):
        print("no roster.txt")
        return

    with open(ROSTER, encoding="utf-8") as f:
        names = [n.strip() for n in f if n.strip() and not n.startswith("#")]

    os.makedirs("data", exist_ok=True)
    seen = set()
    if os.path.exists(CANDS):
        with open(CANDS, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                seen.add(row["query"].lower())

    todo = [n for n in names if n.lower() not in seen][:PER_RUN]
    print(f"{len(todo)} name(s) to resolve, {len(names) - len(todo)} already done or queued")

    fresh = not os.path.exists(CANDS)
    with open(CANDS, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if fresh:
            w.writeheader()
        for name in todo:
            found = channel_search(name)
            print(f"{name}: {len(found)} candidate(s)")
            for row in found:
                w.writerow(row)
            time.sleep(1.0)

    print("review data/candidates.csv — set status to approved on the right row")


if __name__ == "__main__":
    main()
