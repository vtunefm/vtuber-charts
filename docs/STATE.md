```markdown
# VTune FM Charts — State of the Build

Last updated: 2026-11-17

Read this before touching anything. It exists so a fresh session does not
re-litigate settled decisions or re-break fixed bugs.

## What this is

The charts site for VTune FM, a VTuber music radio show. Live at
`vtuber-charts.streamlit.app`, source at `vtunefm/vtuber-charts`.

Three surfaces, per the original brief:

- **Music Top 100** — a Billboard-style weekly chart. Monday–Saturday window,
  Sunday is the scheduling day and is deliberately outside the window.
- **Newest Original Releases** / **Newest Cover Releases** — a newest feed
  capped at 10, bucketed Today / Yesterday with a Recent fallback.
- **Artist Top 100** — one entry per artist, deduped, collab gains credited to
  every credited artist, avatar and channel link, never a duplicate slot.

The long game is an awards show. The chart is the credibility engine for it.

## Non-negotiables

- Monday–Saturday only. Not a bug, not negotiable.
- The panel is curated. Open discovery was tried and abandoned; only channels
  that went through `resolve` → `autopick` → manual review are eligible.
- Whole files over fragments. Fragments have landed in the wrong place more
  than once.
- The YouTube API key lives in the `YOUTUBE_API_KEY` GitHub secret. Never ask
  for it and never put it in a file.
- English-facing. Japanese names are secondary, shown as the sub-line.
- No `days_live` field. The gap against YouTube's counter is source lag and is
  already labelled.

## Architecture

vsong is gone. It 404'd every EN track, and its retry backoff blew a 30-minute
timeout. Everything now runs on the YouTube Data API plus our own snapshots.

Data flow:

```
roster.txt ──> resolve.py ──> candidates.csv ──> autopick.py ──> manual review
                                                                    │
                                                                    v
                                                              ingest.py
                                                                    │
                                                                    v
                                                              tracks.csv
                                                                    │
                                        snapshot.py ──> snapshots.csv │
                                                                    v
                                                                 chart.py
                                                                    │
                                                                    v
                                                               chart.json
                                                                    │
                                                          Streamlit pages
```

`chart.py` derives gains **only** from deltas between our own snapshots. There
is no external view source. A track needs two snapshots to produce a gain, so
new ingestion is invisible on the chart until the next snapshot lands.

## Files

| File | Role |
|---|---|
| `roster.txt` | Curated name list, one per line. Alias after a slash when the channel is named differently: `Momosuzu Nene / 桃鈴ねね`. |
| `add_vtubers.txt` | The operator's loop for adding names. Follow it. |
| `resolve.py` | Resolves roster names to channels, 30 names per run, 3 candidates each, pending sorted to the top. |
| `autopick.py` | Auto-approves exact matches, rejects junk via `JUNK_RE`. Recomputes from scratch every run. |
| `ingest.py` | Pulls uploads for approved channels via `ytmeta.py`. Least-covered first, `MAX_ADD` / `PER_CHANNEL` capped. |
| `ytmeta.py` | Batched `videos.list` metadata. Replaced all vsong metadata. |
| `snapshot.py` | Records `view_count` per track into `snapshots.csv`. |
| `chart.py` | Builds `chart.json`. Window selection, gains, history, artist dedupe, avatar and channel resolution. |
| `newest.py` | Builds the newest feed. |
| `avatars.py` | Backfills blank `channel_id`s, then fetches channel avatars into `avatars.csv`. |
| `playlists.py` | Episode playlist cards. |
| `ui.py` | All rendering and CSS. |
| `app.py`, `pages/*` | Streamlit surfaces. |

`prune.py` and `reset.py` **do not exist in the repo.** The loop in
`add_vtubers.txt` assumes they do not, but if a cleanup is needed you will have
to write them. `prune` was meant to be a one-pass removal of non-roster tracks;
`reset` flips candidate statuses back to pending.

## Workflows

| Workflow | Trigger | Notes |
|---|---|---|
| `resolve.yml` | daily + manual | 30 names per run |
| `ingest.yml` | manual | `hit MAX_ADD, stopping` means run it again |
| `snapshot.yml` | daily 23:50 UTC + manual | |
| `chart.yml` | Sundays 09:00 UTC + manual | |
| `newest.yml` | daily + manual | |
| `avatars.yml` | daily 06:00 UTC + manual | Also rebuilds the chart, so pictures cannot drift from `chart.json` |
| `playlists.yml` | daily + manual | |

`discover.yml`, `siblings.yml` and `collect.yml` were deleted; their scripts
remain. `prune.yml` and `reset.yml` were never created.

## Data files

- `tracks.csv` — the source of truth. Filtering this is how you clean up;
  deleting `chart.json` or `archive/` alone changes nothing.
- `snapshots.csv` — raw `view_count` readings. Never edit.
- `candidates.csv` — `query` holds the canonical roster name, `status` is
  `pending` / `approved` / `done` / `rejected`. Only `done` and `approved`
  channels are used for artist identity, avatars and links.
- `avatars.csv` — `channel_id,avatar`, `s800` profile pictures.
- `chart.json`, `archive/` — build output. Regenerated every run.

## Settled decisions

- One combined Billboard. `type` is retained as a column but does not split the
  chart.
- No recency cutoff on ingestion. Gain-based charts let old songs re-enter.
- `choose_window()` falls back to week-to-date with `partial: true` when no
  snapshot lands inside the completed window. Cold start is handled by the
  fallback, not by fabricating data.
- Artist identity resolves by containment against `done`/`approved` channels,
  highest subscribers first, Topic channels last. The uploader's channel is
  used **only** when the artist *is* the uploader. Name-variant matching alone
  caused Marine to inherit Korone's face on a collab.
- Artist rows link to the channel, not the video, and show no song title.

## Open items

1. **`unknown` type rate** — roughly 25% of tracks land `unknown` and are
   excluded from the chart. `classify()` needs widening.
2. **Artist ceiling** — the artist chart has been capped near 58 by pool depth,
   not by code. Watch whether it moves as ingestion spreads.
3. **Avatar and link coverage** — an artist with no `done`/`approved` row has no
   face and no channel link and falls back to the video thumbnail. The roster is
   the ceiling. Check the `artist pictures N/M · channels N/M` line in the chart
   log.
4. **No `prune.py` / `reset.py`.**
5. **Cosmetic list** — empty. Add to it as it comes up.

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
```
