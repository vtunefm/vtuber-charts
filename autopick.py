import csv
import os
import re
import unicodedata

CANDS = "data/candidates.csv"
COLS = ["query", "channel_id", "channel_name", "handle", "subscribers", "status", "note"]

STRIP_RE = re.compile(r"[\s\-_.·・「」『』【】()（）]+")
JUNK_RE = re.compile(
    r"(clip|clips|切り抜き|翻訳|translat|moments|highlights|reacts|fan ?ch)", re.I
)


def norm(value):
    return STRIP_RE.sub("", unicodedata.normalize("NFKC", value or "").lower())


def main():
    if not os.path.exists(CANDS):
        print("no candidates.csv")
        return

    with open(CANDS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    groups = {}
    for row in rows:
        if "manual" in (row.get("note") or ""):
            continue
        row["status"] = "pending"
        groups.setdefault(row["query"], []).append(row)

    kept = left = 0
    for query, group in groups.items():
        keys = [k for k in (norm(p) for p in re.split(r"[/|]", query)) if len(k) >= 4]
        if not keys:
            left += 1
            continue

        hits = [
            r for r in group
            if any(k in norm(r["channel_name"]) for k in keys)
        ]
        real = [r for r in hits if not JUNK_RE.search(r["channel_name"])]

        if not real:
            left += 1
            continue

        for row in real:
            row["status"] = "approved"
            if "auto" not in row["note"]:
                row["note"] = (row["note"] + " auto").strip()
            kept += 1
        for row in hits:
            if row["status"] != "approved":
                row["status"] = "rejected"

    with open(CANDS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"approved {kept} · {left} name(s) need a human")


if __name__ == "__main__":
    main()
