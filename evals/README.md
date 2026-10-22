# Evals

Golden sets for the model layer, scored against the live provider the server uses. The question these answer
is the one the app's unit tests cannot: not "does the loop work when the model says X" but "does the model say X".

| Set | File | What it measures | Calls |
|---|---|---|---|
| routing | `routing.jsonl` | sentence → `ingest` / `query` / `operation` (the three-way split behind `/api/interpret`): accuracy, per-language accuracy, per-intent P/R/F1, confusion matrix | 60 |
| extraction | `extraction.jsonl` | ingest sentences → `box_label`, `items[].name`, `items[].qty_text`, `location_text`, `language`: field accuracy, item precision/recall, quantity accuracy, exact-case rate | 40 |

Half of each set is Chinese, half English. Planned next: retrieval (Recall@k, MRR over the vector search),
tool calling (expected tool sequence, arguments, confirm gate) and photo extraction once a labelled photo set exists.

## Run

```bash
cd <repo>
backend/.venv/bin/python evals/run.py                      # both sets, provider/model from backend/.env
backend/.venv/bin/python evals/run.py routing --model haiku  # one set, another model of the same provider
backend/.venv/bin/python evals/run.py --provider gateway --model kimi-k2.5
backend/.venv/bin/python evals/run.py --limit 5 --no-write  # smoke test, nothing recorded
```

Every run prints the summary and the failing cases, writes `results/<set>-<stamp>.json` (per case: input,
expected, model output, latency, tokens, prompt id) and appends one row to [`RESULTS.md`](RESULTS.md).
The prompt id is a hash of the prompt wording in `backend/app/services/llm.py`, so a row pins exactly
which prompt and model produced the numbers.

## Case format

One JSON object per line; `#` lines are comments.

```json
{"id": "x002", "lang": "en", "text": "Put two pairs of snow boots in box 4, garage left shelf",
 "known_labels": ["1", "2"],
 "expect": {"intent": "ingest", "box_label": "4",
            "items": [{"name": "snow boots", "qty_text": ["×2 pairs", "×2"]}],
            "location_text": ["garage left shelf", "garage, left shelf"]}}
```

- `known_labels` is what the user already has; it is passed to the model as context (optional).
- Any expected scalar may be a list of acceptable alternatives. Use it where two readings are both right
  ("down jackets" vs "down jacket"), not to paper over a wrong answer.
- Box labels compare through the app's own key (`backend/app/normalize.py`): `3`, `3号` and `Box 3` are equal.
- Quantities compare after normalising `x`/`×` and whitespace; names compare case-insensitively with edge
  punctuation stripped.

## Labelling rules

- `ingest` = things being put into a box, including "add X to box 1". `operation` = anything that changes
  existing boxes or items (location, rename, move, merge, delete, empty, code, GPS, undo). `query` = asking.
- "Box 7 is under the sink now" is an operation (location change); "I put the tent in box 3 in the basement"
  is ingest with a location.
- A plural with no number ("my winter scarves") is `some` / `若干`; "the Christmas lights" may be either.
- Units stay in the quantity ("×2 pairs"); the bare number is accepted where the unit is implied by the name.

## Scoring code

`backend/app/evals/score.py` (pure, unit-tested in `backend/tests/test_evals_score.py`) and
`backend/app/evals/harness.py` (runs the model, writes results). Validation of these files runs in CI
(`backend/tests/test_evals_sets.py`) so a malformed case fails the build, not the eval run.
