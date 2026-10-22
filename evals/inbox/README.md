# Inbox

Case stubs exported from failed production runs by `evals/export.py` (one file per set and export run). Each
line carries the model's own answer as `expect` and a `_source` block saying which run, why it is here
(thumbs down, undone, error, step cap) and what the user said in their note.

Review, correct `expect`, drop the `_source` / `_review` keys and the `inbox-` id prefix, and move the line
into `evals/<set>.jsonl`. The files themselves are git-ignored: they contain what real users typed.
