import csv
import os

CHANNELS = "data/channels.csv"
OUT = "data/artist_channels.csv"
COLS = ["name", "canonical_channel_id"]


def to_int(value):
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def existing():
    if not os.path.exists(OUT):
        return {}
    with open(OUT, newline="", encoding="utf-8") as f:
        return {(r.get("name") or "").strip(): (r.get("canonical_channel_id") or "").strip()
                for r in csv.DictReader(f) if r.get("name")}


def main():
    if not os.path.exists(CHANNELS):
        print("no channels.csv — run sync.py first")
        return

    best = {}
    with open(CHANNELS, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = (row.get("channel_id") or "").strip()
            name = (row.get("name") or "").strip()
            if not cid or not name or row.get("status") != "ok":
                continue
            subs = to_int(row.get("subscribers"))
            if name not in best or subs > best[name][0]:
                best[name] = (subs, cid)

    keep = existing()
    os.makedirs("data", exist_ok=True)
    written = filled = 0
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for name in sorted(best):
            chosen = keep.get(name) or best[name][1]
            filled += 0 if keep.get(name) else 1
            w.writerow({"name": name, "canonical_channel_id": chosen})
            written += 1
        for name, cid in sorted(keep.items()):
            if name not in best:
                w.writerow({"name": name, "canonical_channel_id": cid})
                written += 1

    print(f"{written} artist row(s), {filled} newly derived, {len(keep)} preserved")


if __name__ == "__main__":
    main()
