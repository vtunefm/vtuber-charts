# VTune FM Charts — State of the Build

Last updated: 2026-11-19

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

- Friday–Thursday only, Billboard-style. Not a bug, not negotiable. The boundary
  is the industry release day so late-week drops are not gutted by the reset.
- The panel is curated and roster-driven. Nothing enters the chart that is not
  in `roster.csv`.
- Whole files over fragments. Fragments have landed in the wrong place more
  than once.
- The YouTube API key lives in the `YOUTUBE_API_KEY` GitHub secret. Never ask
  for it and never put it in a file.
- English-facing. Japanese names are secondary, shown as the sub-line.
- No `days_live` field. The gap against YouTube's counter is source lag and is
  already labelled.
- `created_at`, `subs.csv` and `artist_channels.csv` are capture-only. Nothing
  ranks or filters on them yet. Do not gate eligibility on any of them.

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
| `artist_channels.py` | Derives one canonical channel per artist from the highest-subscriber `status: ok` row. Never overwrites an existing value, so hand fixes survive. |
| `ingest.py` | Pulls uploads for `status: ok` channels via `ytmeta.py`. Least-covered first, `MAX_ADD` / `PER_CHANNEL` capped, partners detected from titles. |
| `ytmeta.py` | Batched `videos.list` metadata. |
| `snapshot.py` | Records `view_count` per track into `snapshots.csv`, and `subscribers` per channel into `subs.csv`. |
| `chart.py` | Builds `chart.json`. Window selection, gains, history, artist dedupe, collab split, avatar and channel resolution. Also writes `archive/<week>.json` every run and `history/<week>.json` when a week closes. |
| `newest.py` | Builds the newest feed. |
| `avatars.py` | Backfills blank `channel_id`s, then fetches channel avatars into `avatars.csv`. |
| `playlists.py` | Episode playlist cards. |
| `ui.py` | All rendering and CSS. |
| `app.py`, `pages/*` | Streamlit surfaces. `pages/3_Past_Weeks.py` renders `data/history` and is sidebar-only. |
| `reset.py` | Deletes `tracks.csv`, `chart.json`, `newest.json` and `archive/`. Keeps channels, avatars, snapshots, playlists, aliases, subs, artist_channels and season. |

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
| `sync.yml` | manual | Resolves roster handles, then derives `artist_channels.csv`. Run before any add. |
| `add.yml` | manual | `sync` → `artist_channels` → `ingest` → `avatars` → `snapshot` → `chart` → `newest` → `playlists` → `snapshot`, one job. |
| `ingest.yml` | manual | `hit MAX_ADD, stopping` means run it again |
| `snapshot.yml` | daily 05:00, 11:00, 17:00, 23:00 UTC + manual | Also rebuilds the chart, so the page tracks each reading |
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
- `channels.csv` — `name, handle, channel_id, channel_title, created_at,
  subscribers, status`. Only `status: ok` rows are ingested, credited, given
  avatars and linked. Rewritten from `roster.csv` on every `sync.py` run, so
  `created_at` repopulates itself — no backfill script is needed.
- `aliases.csv` — `japanese,english` pairs. **Currently missing from the repo.**
  See open item 1.
- `avatars.csv` — `channel_id,avatar`, `s800` profile pictures.
- `subs.csv` — `channel_id, read_at, subscribers`, appended by `snapshot.py`
  four times daily. Append-only, never edit. Starts empty and has no backfill,
  so the history exists only from the first snapshot after this landed.
- `artist_channels.csv` — `name, canonical_channel_id`, one row per artist.
  Derived by `artist_channels.py`; hand-editable, and a hand value is never
  overwritten.
- `season.json` — `{"start", "end"}` award-season bounds. Season start is a
  Monday so it lands on a chart-window boundary.
- `chart.json`, `archive/` — build output. Regenerated every run.
- `history/` — frozen Top 10 per closed week. Written once, never rewritten.

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
- **Genre is a constant.** The column carries `vtuber` and nothing else. No
  taxonomy, no lexicon, no classifier. A finer split is a later fill-in.
- **No subscriber tiers.** Award brackets were considered and dropped; raw
  subscriber counts are captured in `subs.csv` for normalisation instead.
- **Recurrent rule, Billboard's.** Below #50 after 20 weeks, #25 after 26, #10
  after 52, #5 after 78. Keeps the chart from calcifying. Songs only for now;
  the artist chart has no age rule yet.

## Awards — agreed shape, not built

Category set settled 2026-11-19. Nothing here is implemented.

Music: Top Song — Original, Top Song — Cover, Biggest Debut, Longest Run, Most
Weeks at #1, Biggest Climb, Sleeper/Breakout, Most Consistent, Engagement,
Collaboration of the Year, Most Covered Song, Steepest Fall.

Artist: Top Artist of the Year, Rookie of the Year, Comeback of the Year,
Office/Label of the Year.

Rules: nominations derive from data, wins come from a panel or public vote.
One slot per artist per category, non-negotiable. Every award publishes its
metric and window so a disputed result can be audited. Most Improved waits for a
second season. Genre awards wait for a genre column.

## Open items

1. **`data/aliases.csv` is missing.** `reset.py` lists it as a keep-target and
   would print `absent`; `ingest.py` opens it behind an `os.path.exists` guard,
   so partner detection silently loses its non-English half. Rebuild it from the
   `unresolved credit(s)` log line.
2. **Offices still chart.** `is_office()` now drops office names as trailing
   tags, but an office is still credited when it is the uploader — FLOW GLOW
   charts, and `Hatsuboshi Gakuen` sits at #1 without being in `OFFICE_TAGS` at
   all. Decide whether offices are excluded outright or moved to their own
   block, and whether group channels count as artists.
3. **`unknown` type rate** — roughly 25% of tracks land `unknown` and are
   excluded. `classify()` needs widening; it is the single biggest distortion
   against small channels. It also makes a quarter of the catalogue ineligible
   for the two song awards.
4. **Catalogue size still decides the artist chart.** Rank is a raw sum, so a
   65-video channel beats a 9-video one on volume alone. A per-artist cap on
   credited videos (best ~12) is agreed in principle, not built.
5. **`playlists.py`** takes the first `Ep N` match in a 40-item scan instead of
   the highest, and can return duplicate thumbnails.
6. **No `prune.py`.** Removal of non-roster tracks is still done by hand on
   `tracks.csv`.
7. **Stale copy in `app.py`** — the About tab claims a 500-view floor (`MIN_GAIN`
   is 1) and the Artist Top 10 caption still says "highest-gaining video shown".
   The collab-division line has landed. `pages/2_Artist_Top_100.py` was
   corrected; `app.py` was not.
8. **`docs/` and the tree disagree** in a few places by design — see the retired
   block. Delete retired files when nothing needs them.
9. **`pages/3_Past_Weeks.py` has no entry point.** It is sidebar-only and
   unlinked from `app.py`.
10. **Season bounds are provisional.** `season.json` reads 2027-01-04 →
    2027-12-31. Confirm the year before award work starts.
11. **`subs.csv` growth.** ~500 rows four times daily, roughly 730k rows a year.
    Second-largest file in `data/` within weeks. Watch the commit size.
12. **Cosmetic list** — empty. Add to it as it comes up.

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
- `channels.csv` is rewritten from scratch every `sync.py` run. Anything that
  depends on it — `created_at`, `subs.csv`, `artist_channels.csv` — needs `sync`
  to have run first.
