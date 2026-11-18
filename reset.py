import os
import shutil

DATA = "data"
TARGETS = ["tracks.csv", "chart.json", "newest.json"]
ARCHIVE = os.path.join(DATA, "archive")

removed = 0
for name in TARGETS:
    path = os.path.join(DATA, name)
    if os.path.exists(path):
        os.remove(path)
        print(f"removed {path}")
        removed += 1

if os.path.isdir(ARCHIVE):
    shutil.rmtree(ARCHIVE)
    print(f"removed {ARCHIVE}/")
    removed += 1

for keep in ("channels.csv", "avatars.csv", "snapshots.csv", "playlists.json", "aliases.csv"):
    path = os.path.join(DATA, keep)
    print(f"kept {path}" if os.path.exists(path) else f"absent {path}")

print(f"{removed} target(s) removed")
