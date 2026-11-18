# Worklog

Newest first. One entry per session: what changed, why, what broke, what is next.
Settled entries get folded into `STATE.md` and deleted from here.

---

## 2026-11-18 — clean-slate reset, collab split, cleanup audit

The duplicates from yesterday came back on the first sync, and the alias patching
that was meant to fix them was losing ground. `OFFICE_RE` stripping and a
`japanese→english` alias table still left twelve artists doubled, because the
credit strings carried names that no channel title could match.

**Reset instead of patching.** `reset.py` deletes `tracks.csv`, `chart.json`,
`newest.json` and `archive/` while keeping `channels.csv`, `avatars.csv`,
`snapshots.csv`, `playlists.json` and `aliases.csv`. `reset.yml` wraps it. Ran
it, then Add Roster Batch twice. The rebuilt `tracks.csv` came back with English
names throughout, uniform `roster:` tagging and collab credits in the
`uploader/partner` form — the partner-detection regression that motivated the
reset was fixed by adding `load_name_index()` and `partners()` to `ingest.py`.

**Snapshot, then chart.** Snapshots were an hour stale against a file that had
just been rebuilt, so Snapshot Views ran before Build Weekly Chart. Chart
published 100/100.

**Duplicate artists were still there.** Marine at #3 and #11, twenty names
doubled, every one an id-keyed row next to a name-keyed row. Cause: `CH_PREFIX_RE`
in `title_variants()` strips everything *before* `Ch.` and keeps the office, so
`Mori Calliope Ch. hololive-EN` yielded `hololive-en` and never `mori calliope`.
Collab credits could not resolve, fell back to a name key, and opened a second
slot.

**Collab gain is now split.** Agreed with the operator: two credited artists take
0.5 each, four take 0.25. Shipped alongside the dedupe — `CH_HEAD_RE`, a direct
canonical-name→id index, office stripping before the divisor, credit dedupe,
divisor floor of 1, whole-number `video_count`, share rather than raw figure in
`top_video`, and a merge pass for anything that still keys on a name. Verified
live: Marine's top video reads 20,078 against a raw 40,157, duplicates gone.

**Cleanup audit.** Mapped every file. `resolve.py`, `autopick.py`, `resolve.yml`,
`discover.py`, `siblings.py` and `collect.py` are dead — the first pair replaced
by `roster.csv` + `sync.py`, the second pair still pointed at `old.vsing.info`,
the last writing a `top10.json` nothing reads. `roster.txt` is dead to the
pipeline but `app.py` still counts its lines. `docs/` rewritten against the tree.

**Still broken / open:**
- `data/aliases.csv` is missing from the repo. `ingest.py` guards it with
  `os.path.exists`, so it fails silently and partner detection loses its
  Japanese half. Highest priority.
- `is_office()` only fires on unresolved names, so offices that resolve to a
  channel id still chart — `hololive` at #4, plus EN, ID, ReGLOSS, NIJISANJI EN.
  The check has to move ahead of resolution.
- No per-artist video cap, so catalogue size still decides the artist chart.
- `app.py` copy still wrong in three places, now including the missing note that
  collab gain is divided.
- `classify()`, `playlists.py` `Ep N` bug, `prune.py` all untouched.

**Next:** rebuild `aliases.csv`, then move the office check ahead of resolution.
