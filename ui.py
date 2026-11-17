def artist_row(entry, total):
    top = entry["top_video"]
    url = WATCH.format(top["video_id"])
    alt = entry["name"] if entry.get("name") != entry.get("display") else ""
    sub = f"{html.escape(alt)} · {html.escape(top['title'] or '')}" if alt else html.escape(top["title"] or "")
    return (
        f"<div class='chartrow' style='animation-delay:{delay(entry['rank'], total):.2f}s'>"
        f"<div class='rank'>{entry['rank']}</div>"
        f"<div class='thumb avatar'><a href='{url}' target='_blank' rel='noopener'>"
        f"<img src='{entry['picture']}' alt=''></a></div>"
        f"<div><div class='song'>{html.escape(entry.get('display') or entry['name'])}</div>"
        f"<div class='who'>{sub}</div></div>"
        f"<div>{stats_line(entry)}</div>"
        f"<div><div class='gain'>+{entry['views_gained']:,}</div>"
        f"<div class='who' style='text-align:right'>{entry['video_count']} vids</div></div>"
        f"</div>"
    )
