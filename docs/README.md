# Reading order

Start here. A fresh session needs context before it touches anything.

1. Newest three entries in `docs/WORKLOG.md` — what just happened and why.
2. `docs/STATE.md` — what is true: architecture, decisions, open items, gotchas.
3. The repo tree — what is actually on disk.

When the tree and the docs disagree, the tree wins. Fix the doc before you
build on the disagreement.

Write a worklog entry at the end of every session, newest on top. Fold settled
entries into `STATE.md` and delete them; never let the two restate each other.

`STATE.md` is not a wishlist. Anything in its Files or Workflows tables must be
something you could actually run today. Retired things go in the retired block,
with the reason.
