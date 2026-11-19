import os
import re

from googleapiclient.discovery import build

API_KEY = os.environ.get("YOUTUBE_API_KEY")
youtube = build("youtube", "v3", developerKey=API_KEY) if API_KEY else None

DUR_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def parse_duration(iso):
    m = DUR_RE.fullmatch(iso or "")
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def fetch_meta(ids):
    out = {}
    if not youtube:
        return out
    for i in range(0, len(ids), 50):
        try:
            resp = youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(ids[i:i + 50]),
            ).execute()
        except Exception as e:
            print(f"meta batch failed: {e}")
            continue
        for item in resp.get("items", []):
            sn = item.get("snippet", {})
            st = item.get("statistics", {})
            out[item["id"]] = {
                "title": sn.get("title", ""),
                "channel": sn.get("channelTitle", ""),
                "channel_id": sn.get("channelId", ""),
                "published": (sn.get("publishedAt") or "")[:10],
                "duration": parse_duration(item.get("contentDetails", {}).get("duration")),
                "views": int(st.get("viewCount", 0)),
                "likes": int(st.get("likeCount", 0)),
                "description": (sn.get("description") or "")[:1200],
            }
    return out
