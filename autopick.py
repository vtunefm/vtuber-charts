import csv
import os
import re
import unicodedata

CANDS = "data/candidates.csv"
COLS = ["query", "channel_id", "channel_name", "handle", "subscribers", "status", "note"]

STRIP_RE = re.compile(r"[\s\-_.·・「」『』【】()（）]+")


def norm(value):
    value = unicodedata.normalize("NFKC", value or "").lower()
    return STRIP_RE.sub("", value)


def main():
    if not os.path.exists(CANDS):
        print("no candidates.csv")
        return

    with open(CANDS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    groups = {}
    for row in rows:
        if row.get("status") == "pending":
            groups.setdefault(row["query"], []).append(row)

    picked = left = 0
    for query, group in groups.items():
        key = norm(query)
        if len(key) < 4:
            left += 1
            continue

        match = None
        for row in group:
            if key in norm(row["channel_name"]):
                match = row
                break

        if not match:
            left += 1
            continue

        match["status"] = "approved"
        match["note"] = (match["note"] + " auto").strip()
        picked += 1
        for row in group:
            if row is not match:
                row["status"] = "rejected"

    with open(CANDS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    print(f"auto-approved {picked} · {left} name(s) need a human")
    if left:
        print("review the remaining 'pending' rows and approve one each")


if __name__ == "__main__":
    main()
