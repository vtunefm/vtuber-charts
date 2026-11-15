import json
import os
import re

import yt_dlp

CHANNEL = "https://www.youtube.com/@vtunefm-q105/playlists"
OUT = "data/playlists.json"
EP_RE = re.compile(r"^ep\s*\d+", re.I)
H2H_RE = re.compile(r"heart[\s-]*2[\s-]*heart", re.I)
H2H_FALLBACK = {"id": "PL9qLUw9u1phYWWrxcw147cRqmpRXFa-7w", "title": "Heart-2-Heart"}

MIN_VIDEOS = 12
MAX_PROBE = 8


def flat(url, limit=None):
    opts = {"extract_flat": True, "quiet": True}
    if limit:
        opts["playlistend"] = limit
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def main():
    try:
        info = flat(CHANNEL, 40)
    except Exception as e:
        print(f"scrape failed: {e}")
        return

    candidates = []
    h2h = None
    for entry in info.get("entries") or []:
        title = (entry.get("title") or "").strip()
        if h2h is None and H2H_RE.search(title):
            h2h = {"id": entry["id"], "title": title}
        if EP_RE.match(title) and "bonus" not in title.lower():
            candidates.append({"id": entry["id"], "title": title})

    latest_ep = None
    for cand in candidates[:MAX_PROBE]:
        try:
            playlist = flat(f"https://www.youtube.com/playlist?list={cand['id']}")
        except Exception as e:
            print(f"probe failed {cand['id']}: {e}")
            continue
        count = len(playlist.get("entries") or [])
        print(f"{cand['title']}: {count} videos")
        if count >= MIN_VIDEOS:
            latest_ep = cand
            break

    if h2h is None:
        h2h = H2H_FALLBACK

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"latest_episode": latest_ep, "heart2heart": h2h}, f, ensure_ascii=False, indent=2)

    print(f"episode={latest_ep} heart2heart={h2h}")


if __name__ == "__main__":
    main()
