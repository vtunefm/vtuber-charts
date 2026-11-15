import json
import os
import re

import yt_dlp

CHANNEL = "https://www.youtube.com/@vtunefm-q105/playlists"
OUT = "data/playlists.json"
EP_RE = re.compile(r"^ep\s*\d+", re.I)
H2H_RE = re.compile(r"heart[\s-]*2[\s-]*heart", re.I)
H2H_FALLBACK = {"id": "PL9qLUw9u1phYWWrxcw147cRqmpRXFa-7w", "title": "Heart-2-Heart"}


def flat(url, limit=None):
    opts = {"extract_flat": True, "quiet": True}
    if limit:
        opts["playlistend"] = limit
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def first_thumb(playlist_id):
    try:
        playlist = flat(f"https://www.youtube.com/playlist?list={playlist_id}", 1)
    except Exception as e:
        print(f"thumb failed {playlist_id}: {e}")
        return ""
    entries = playlist.get("entries") or []
    vid = entries[0].get("id") if entries else None
    return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg" if vid else ""


def main():
    try:
        info = flat(CHANNEL, 40)
    except Exception as e:
        print(f"scrape failed: {e}")
        return

    latest = h2h = None
    for entry in info.get("entries") or []:
        title = (entry.get("title") or "").strip()
        if latest is None and EP_RE.match(title):
            latest = {"id": entry["id"], "title": title}
        if h2h is None and H2H_RE.search(title):
            h2h = {"id": entry["id"], "title": title}

    if h2h is None:
        h2h = dict(H2H_FALLBACK)

    for item in (latest, h2h):
        if item:
            item["thumb"] = first_thumb(item["id"])

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"latest_episode": latest, "heart2heart": h2h}, f, ensure_ascii=False, indent=2)

    print(f"latest={latest}")
    print(f"heart2heart={h2h}")


if __name__ == "__main__":
    main()
