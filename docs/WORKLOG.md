# Worklog

Newest first. One entry per session: what changed, why, what broke, what is next.
Settled entries get folded into `STATE.md` and deleted from here.

---

## 2026-11-17 — vsong removed, charts rebuilt on own snapshots, artist identity fixed

The big one. This session ended the dependency the whole pipeline was standing on.

**vsong dropped.** A log showed every Hololive EN track 404ing against the
vsong API and the retry backoff burning a 30-minute workflow timeout. Replaced
with the YouTube Data API for metadata (`ytmeta.py`, batched `videos.list`) and
our own snapshots for gains. `ingest.py` rewritten onto `ytmeta.py`. `chart.py`
rewritten to read `snapshots.csv` deltas only — no external view source remains.
`discover.yml`, `siblings.yml` and `collect.yml` deleted; their scripts are still
in the tree and now unreferenced.

**Cold-start window fixed.** The chart wanted 9–14 Nov while the first snapshot
was 17 Nov, so nothing could ever qualify. `choose_window()` now falls back to
week-to-date and sets `partial: true` instead of emitting an empty chart. Cold
start is handled by the fallback, not by inventing data.

**Artist identity.** Avatars were rendering as circular video stills, then — after
a first fix — as the *wrong* still. The first attempt keyed avatars by name
variants and let every `candidates.csv` row compete, including rejected clip
channels, then fell back to the uploader's channel. On a Marine/Korone collab
Marine got Korone's face. Replaced with containment matching against
`done`/`approved` channels only, highest subscribers first, Topic channels last,
and the uploader used only when the artist *is* the uploader. Artist rows now
carry `channel_url`, link to the channel instead of the video, and show no song
title. `avatars.yml` rebuilds the chart in the same run so pictures cannot drift
from `chart.json` again.

**Housekeeping.** `docs/STATE.md` written, `docs/README.md` added. Two false
claims in the first STATE draft corrected against the tree: `newest.py` has no
original/cover split, and `autopick.py` runs inside `resolve.yml` rather than as
a manual step.

**Still broken / open:**
- `prune.py` and `reset.py` are not in the repo, only described. Cleanup has to
  be done by hand on `tracks.csv` until they exist.
- `app.py` About tab still claims a 500-view floor when `MIN_GAIN` is 1, and the
  Artist Top 10 caption still says "highest-gaining video shown."
- `classify()` leaves ~25% of tracks `unknown`, which excludes them from the
  chart.
- Artist picture and link coverage is capped by roster depth, not by code. Watch
  the `artist pictures N/M · channels N/M` line in the chart log.

**Next:** `app.py` copy edits, then widening `classify()`.
