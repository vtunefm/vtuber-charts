# VTune FM Charts — State of the Build

Last updated: 2026-11-18

Read this before touching anything. It exists so a fresh session does not
re-litigate settled decisions or re-break fixed bugs. Read the repo tree too —
this file says what should be true, the tree says what is. When they disagree,
the tree wins and this file gets fixed.

## What this is

The charts site for VTune FM, a VTuber music radio show. Live at
`vtuber-charts.streamlit.app`, source at `vtunefm/vtuber-charts`.

Three surfaces, per the original brief:

- **Music Top 100** — a Billboard-style weekly chart. Monday–Saturday window,
  Sunday is the scheduling day and is deliberately outside the window.
- **Newest Releases** — one feed capped at 10, bucketed Today / Yesterday with a
  Recent fallback. The original brief called for separate Original and Cover
  feeds; the build has not split them.
- **Artist Top 100** — one entry per artist, deduped, collab gains divided
  between credited artists, avatar and channel link, never a duplicate slot.

The long game is an awards show. The chart is the credibility engine for it.

## Non-negotiables

- Monday–Saturday only. Not a bug, not negotiable.
- The panel is curated and roster-driven. Nothing enters the chart that is not
  in `roster.csv`.
- Whole files over fragments. Fragments have landed in the wrong place more
  than once.
- The YouTube API key lives in the `YOUTUBE_API_KEY` GitHub secret. Never ask
  for it and never put it in a file.
- English-facing. Japanese names are secondary, shown as the sub-line.
- No `days_live` field. The gap against YouTube's counter is source lag and is
  already labelled.

## Architecture

vsong is gone. It 404'd every EN track and its retry backoff blew a 30-minute
timeout. Everything runs on the YouTube Data API plus our own snapshots.

Data flow:

    roster.csv ──> sync.py ──> channels.csv ──> ingest.py ──> tracks.csv
                                       (status ok)                    │
                                                                      v
    reset.py ──> clears tracks.csv, chart.json, newest.json, archive/
                                                                      │
                                          snapshot.py ──> snapshots.csv
                                                                      v
                                                                  chart.py
                                                                      │
                                                                      v
                                                    chart.json + archive/<week>.json
                                                                      │
                                                              Streamlit pages

`chart.py` derives gains **only** from deltas between our own snapshots. There
is no external view source. A track needs two snapshots to produce a gain, so
new ingestion is invisible on the chart until the next snapshot lands.

`ingest.py` writes `artists` as `uploader/partner`, partner names detected by
containment against channel names, titles and `aliases.csv`. `PER_CHANNEL` and
`MAX_ADD` are **per-run** caps and re-runs stack, so a channel swept twice can
carry far more than 40 rows. That is expected.

## Files

| File | Role |
|---|---|
| `roster.csv` | Source of truth for the panel. `name` is the English display name, `handle` is the `@handle`. |
| `sync.py` | Resolves each `@handle` through `channels.list?forHandle` into `data/channels.csv` with `status` `ok` / `missing` / `blank`. |
| `ingest.py` | Pulls uploads for `status: ok` channels via `ytmeta.py`. Least-covered first, `MAX_ADD` / `PER_CHANNEL` capped, partners detected from titles. |
| `ytmeta.py` | Batched `videos.list` metadata. |
| `snapshot.py` | Records `view_count` per track into `snapshots.csv`. |
| `chart.py` | Builds `chart.json`. Window selection, gains, history, artist dedupe, collab split, avatar and channel resolution. |
| `newest.py` | Builds the newest feed. |
| `avatars.py` | Backfills blank `channel_id`s, then fetches channel avatars into `avatars.csv`. |
| `playlists.py` | Episode playlist cards. |
| `ui.py` | All rendering and CSS. |
| `app.py`, `pages/*` | Streamlit surfaces. |
| `reset.py` | Deletes `tracks.csv`, `chart.json`, `newest.json` and `archive/`. Keeps channels, avatars, snapshots, playlists, aliases. |

### Retired, still in the tree, unreferenced

| File | Why it is dead |
|---|---|
| `resolve.py`, `autopick.py`, `resolve.yml` | The candidate-review path. Superseded by `roster.csv` + `sync.py`. |
| `discover.py`, `siblings.py` | Both target `old.vsing.info`. Both write a `tracks.csv` schema that predates `artist_name`, so running either corrupts the current file. |
| `collect.py` | Writes `data/top10.json`, which nothing reads. Also the only `pandas` user. |
| `roster.txt` | Old Japanese name list. `app.py` still counts its lines for the About panel size, so it cannot be deleted until that block reads `roster.csv`. |
| `add_vtubers.txt` | Documents the retired resolve → approve → ingest loop. |
| `data/candidates.csv`, `data/roster_state.json`, `data/songs.csv`, `confirmed_exists_no_id.csv`, `needs_sorted.csv` | Resolve-pipeline artifacts. |

## Workflows

| Workflow | Trigger | Notes |
|---|---|---|
| `sync.yml` | manual | Resolves roster handles. Run before any add. |
| `add.yml` | manual | `sync` → `ingest` → `avatars` → `snapshot` → `chart` → `newest` → `playlists` → `snapshot`, one job. |
| `ingest.yml` | manual | `hit MAX_ADD, stopping` means run it again |
| `snapshot.yml` | daily 23:50 UTC + manual | |
| `chart.yml` | Sundays 09:00 UTC + manual | |
| `newest.yml` | daily 10:00 UTC + manual | |
| `avatars.yml` | daily 06:00 UTC + manual | Also rebuilds the chart, so pictures cannot drift from `chart.json` |
| `playlists.yml` | daily 11:00 UTC + manual | |
| `reset.yml` | manual | Destructive. Leaves a chart with nothing in it until the next add + snapshot + chart. |

Every job shares `concurrency: group: data-commit` and a five-attempt
`git pull --rebase --autostash` retry loop.

## Data files

- `tracks.csv` — the source of truth. Filtering this is how you clean up;
  deleting `chart.json` or `archive/` alone changes nothing.
- `snapshots.csv` — raw `view_count` readings. Never edit.
- `channels.csv` — `name, handle, channel_id, channel_title, subscribers, status`.
  Only `status: ok` rows are ingested, credited, given avatars and linked.
- `aliases.csv` — `japanese,english` pairs. **Currently missing from the repo.**
  See open item 1.
- `avatars.csv` — `channel_id,avatar`, `s800` profile pictures.
- `chart.json`, `archive/` — build output. Regenerated every run.

## Settled decisions

- One combined Billboard. `type` is retained as a column but does not split the
  chart.
- No recency cutoff on ingestion. Gain-based charts let old songs re-enter.
- `choose_window()` falls back to week-to-date with `partial: true` when no
  snapshot lands inside the completed window. Cold start is handled by the
  fallback, not by fabricating data.
- **Collab gain is divided evenly between credited artists.** Two credited
  artists take 0.5 each, four take 0.25. Rules that make the division honest:
  office tags are stripped before the divisor is counted, duplicate credits are
  collapsed first, the divisor floors at 1, `video_count` stays a whole 1 per
  video, and `top_video.views_gained` reports the artist's share rather than the
  raw video figure. The music chart keeps raw gain — the two surfaces are
  deliberately different numbers for the same video.
- **Artist identity keys on `channel_id`, never on the name.** A name-keyed row
  is a fallback and is folded into its id-keyed twin before ranking.
- Artist rows link to the channel, not the video, and show no song title.
- The artist chart aggregates over **all** qualifying songs, not the top 100, so
  a video outside the music chart still feeds its artists' totals.

## Open items

1. **`data/aliases.csv` is missing.** `reset.py` lists it as a keep-target and
   would print `absent`; `ingest.py` opens it behind an `os.path.exists` guard,
   so partner detection silently loses its non-English half. Rebuild it from the
   `unresolved credit(s)` log line.
2. **Offices still chart.** `hololive` sits at #4, `hololive EN` at #21,
   `ReGLOSS` at #50, `hololive ID` at #72, `NIJISANJI EN` at #83. `is_office()`
   only fires when a name fails to resolve, and these all resolve to real
   channel ids. Move the office check ahead of resolution, then decide whether
   offices should be dropped entirely or kept in a separate block.
3. **`unknown` type rate** — roughly 25% of tracks land `unknown` and are
   excluded. `classify()` needs widening; it is the single biggest distortion
   against small channels.
4. **Catalogue size still decides the artist chart.** Rank is a raw sum, so a
   65-video channel beats a 9-video one on volume alone. A per-artist cap on
   credited videos (best ~12) is agreed in principle, not built.
5. **`playlists.py`** takes the first `Ep N` match in a 40-item scan instead of
   the highest, and can return duplicate thumbnails.
6. **No `prune.py`.** Removal of non-roster tracks is still done by hand on
   `tracks.csv`.
7. **Stale copy in `app.py`** — the About tab claims a 500-view floor
   (`MIN_GAIN` is 1), the Artist Top 10 caption still says "highest-gaining
   video shown", and there is no line explaining that collab gain is divided.
   `pages/2_Artist_Top_100.py` was corrected; `app.py` was not.
8. **`docs/` and the tree disagree** in a few places by design — see the retired
   block. Delete retired files when nothing needs them.
9. **Cosmetic list** — empty. Add to it as it comes up.

## Gotchas

- CSV booleans never equal `True` as strings. `normalize_row()` re-derives flags
  on every load for this reason.
- `st.page_link` throws `StreamlitPageNotFoundError` after a page is added
  because the running app's page registry is stale. Manage app → Reboot.
- A run that prints `0 new candidate(s)` usually means nothing was queued, not
  that nothing matched.
- The 21-day recency filter is gone. Do not re-add it.
- YouTube `- Topic` channels classify as `original`. Topic channels are
  acceptable avatars but lose to main channels on subscriber count.
- `chart.py` logs `merged N name-only duplicate(s) · M collab(s) split`. If
  `merged` climbs, resolution is regressing. If `M` is 0 on a week with collabs,
  the split is not firing.
- `reset.yml` is destructive and does not re-ingest. After a reset, run Add
  Roster Batch, then Snapshot Views, then Build Weekly Chart — in that order.
  Charting first ranks on flat deltas.
- A reset also drops `archive/`, so every entry comes back `NEW` with no
  movement. It self-corrects once one archive exists.
