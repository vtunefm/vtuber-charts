import json
import os
import re

import yt_dlp

CHANNEL = "https://www.youtube.com/@vtunefm-q105/playlists"
OUT = "data/playlists.json"
EP_RE = re.compile(r"^ep\s*\d+", re.I)
H2H_RE = re.compile(r"heart[\s-]*2[\s-]*heart", re.I)


def main():
    opts = {"extract_flat": True, "quiet": True, "playlistend": 40}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(CHANNEL, download=False)
    except Exception as e:
        print(f"scrape failed: {e}")
        return

    latest_ep = h2h = None
    for entry in info.get("entries") or []:
        title = (entry.get("title") or "").strip()
        if not latest_ep and EP_RE.match(title):
            latest_ep = {"id": entry["id"], "title": title}
        if not h2h and H2H_RE.search(title):
            h2h = {"id": entry["id"], "title": title}

    if not latest_ep and not h2h:
        print("no matching playlists")
        return

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"latest_episode": latest_ep, "heart2heart": h2h}, f, ensure_ascii=False, indent=2)

    print(f"episode={latest_ep} heart2heart={h2h}")


if __name__ == "__main__":
    main()
