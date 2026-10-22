# Evals

Golden sets for the model layer, scored against the live provider the server uses. The question these answer
is the one the app's unit tests cannot: not "does the loop work when the model says X" but "does the model say X",
and for retrieval "does the index find it".

| Set | File | What it measures | Runs through | Cases |
|---|---|---|---|---|
| routing | `routing.jsonl` | sentence → `ingest` / `query` / `operation` (the three-way split behind `/api/interpret`): accuracy, per-language accuracy, per-intent P/R/F1, confusion matrix | `llm.interpret` | 60 |
| extraction | `extraction.jsonl` | ingest sentences → `box_label`, `items[].name`, `items[].qty_text`, `location_text`, `language`: field accuracy, item precision/recall, quantity accuracy, exact-case rate | `llm.interpret` | 40 |
| retrieval | `retrieval.jsonl` | query → the items that should come back from the vector index: Recall@1/3/8, MRR, by language and by query type (exact, cross-lingual, synonym, category) | the agent's `search_items` tool over the fixture world | 50 |
| tools | `tools.jsonl` | instruction → which tools the agent executes, which destructive ones it hands to the confirm gate, with what arguments, and what the boxes look like afterwards: pass rate, tool / confirm / args / state accuracy, missed and spurious gates, steps per case | the whole agent loop (`agent.run`) on a fresh copy of the fixture world | 40 |

Half of each set is Chinese, half English. Still to come: photo extraction (needs a labelled photo set).

The fixture world is `fixtures/world.json`: 12 boxes, 60 items, item names in both languages so that
"把电钻移到5号箱" has to find an item called `drill`. Retrieval loads it once; the tools set loads a fresh copy
per case (own user, own session) so cases cannot affect each other.

## Run

```bash
cd <repo>
backend/.venv/bin/python evals/run.py                        # all four sets, provider/model from backend/.env
backend/.venv/bin/python evals/run.py routing --model haiku    # one set, another model of the same provider
backend/.venv/bin/python evals/run.py tools --provider gateway --model kimi-k2.5
backend/.venv/bin/python evals/run.py --limit 5 --no-write    # smoke test, nothing recorded
```

Every run prints the summary and the failing cases (for tools, with the agent's reply), writes
`results/<set>-<stamp>.json` (per case: input, expected, model output or trace, latency, tokens, prompt id)
and appends one row to [`RESULTS.md`](RESULTS.md), then regenerates the comparison matrix at the top of that
file (latest run per set × model × prompt version; `evals/run.py --report` rebuilds it alone).

## Prompt versions

Every prompt lives in `backend/app/services/prompts.py` with a name, a version and a content hash; traces and
result rows record `interpret v2 (212ab1240e)`, so a row pins exactly which wording and model produced the
numbers. Editing a prompt without bumping its version fails `backend/tests/test_prompts.py`, and the CHANGELOG in
that file says what changed and why, with the eval finding that motivated it. The loop is:

1. a run shows a failure pattern → 2. edit the prompt, bump the version, add the changelog line →
3. re-run the affected sets → 4. the matrix shows the old and new columns side by side.

Model comparison here means `claude -p` with different models (sonnet, haiku, opus) on the same prompt
version; the gateway provider takes `--provider gateway --model <id>` once it has a funded key.

The DB-backed sets (retrieval, tools) need PostgreSQL + pgvector like the server. They use a dedicated database
`boxmind_eval` next to the configured one (created on demand, emptied at the start of each run; override with
`BOXMIND_EVAL_DATABASE_URL`) and the real embedding model from `backend/.env`.

## Case format

One JSON object per line; `#` lines are comments. Any expected scalar may be a list of acceptable alternatives:
use it where two readings are both right ("down jackets" vs "down jacket"), not to paper over a wrong answer.

```json
{"id": "x002", "lang": "en", "text": "Put two pairs of snow boots in box 4, garage left shelf",
 "known_labels": ["1", "2"],
 "expect": {"intent": "ingest", "box_label": "4",
            "items": [{"name": "snow boots", "qty_text": ["×2 pairs", "×2"]}],
            "location_text": ["garage left shelf", "garage, left shelf"]}}

{"id": "q35", "lang": "zh", "tag": "category", "text": "露营用品",
 "expect": {"items": ["tent", "sleeping bag", "camping stove", "lantern", "防潮垫", "折叠椅"]}}

{"id": "t15", "lang": "en", "text": "Move the tent to box 7 and then delete box 1",
 "expect": {"tools": ["move_items"], "confirm": ["delete_box"],
            "args": {"move_items": {"from_box": "1", "to_box": "7", "item_names": ["tent"]}, "delete_box": {"box": "1"}},
            "state": [{"box": "7", "has": ["tent"]}, {"box": "1", "exists": true, "lacks": ["tent"]}]}}
```

- `known_labels` (routing, extraction): what the user already has, passed to the model as context.
- `tag` (retrieval): `exact` (query is the item name), `cross` (other language than the item), `synonym`, `category`.
- `tools` (tools set): the write tools that must run, as a multiset; `search_items` / `get_box` are free. Omit it
  when either of two tools is acceptable (quantity changes can go through `update_item` or `add_items`) and
  let `state` decide. `confirm`: the destructive tools expected at the gate, `[]` means none. `args`: a subset
  of the arguments of the first call of that tool (executed or gated). `state`: box assertions after the run:
  `has` (names, or `{name, qty}`), `lacks`, `exists`, `location`, `location_contains`, `barcode`, `gps`.
- Box labels compare through the app's own key (`backend/app/normalize.py`): `3`, `3号` and `Box 3` are equal.
  Quantities compare after normalising `x`/`×` and whitespace; names compare case-insensitively with edge
  punctuation stripped.

## Labelling rules

- `ingest` = things being put into a box, including "add X to box 1". `operation` = anything that changes
  existing boxes or items (location, rename, move, merge, delete, empty, code, GPS, undo). `query` = asking.
- "Box 7 is under the sink now" is an operation (location change); "I put the tent in box 3 in the basement"
  is ingest with a location.
- A plural with no number ("my winter scarves") is `some` / `若干`; "the Christmas lights" may be either.
- Units stay in the quantity ("×2 pairs"); the bare number is accepted where the unit is implied by the name.
- Tools: a reference that matches two items ("the batteries" with `AA batteries` and `AAA batteries` in
  different boxes) must produce a question, not a move: `tools: []`. "Add 3 more" means the final quantity
  is old + 3. Destructive tools must never execute directly: a case where they do shows up as a missed gate.

## What the first runs found

Recorded in `RESULTS.md`; the point of the sets is that these were found by numbers, not by chance:

- extraction, interpret v1: Chinese bare nouns without a measure word ("帐篷放在3号箱", "旧手机") come back as
  `若干` instead of `×1` on both sonnet and haiku; all four sonnet failures are this one rule. interpret v2 adds
  the rule "a single named item is ×1; `some` is for plurals and bulk words": exact-case rate sonnet 0.90 → 0.95,
  haiku 0.82 → 0.88, opus 0.95. The two remaining sonnet/opus misses (充电线, 旧相册 as ×1) are nouns that are
  plural by sense only, a judgment call the label makes one way; haiku additionally writes units in English
  ("×1 set", "×1 pair") inside Chinese sentences, a candidate for v3.
- routing: 60/60 on sonnet, haiku and opus, both prompt versions. The three-way split is not where the risk is.
- retrieval, hybrid search: with a trigram floor of 0.1 the trigram leg added noise ("printer" pulled in
  "decanter" through a shared "ter") and R@1 fell 0.52 → 0.47; at 0.3 it adds only real substring / typo hits
  and the set scores exactly as vector-only (R@8 0.80), so the win is the one the unit tests show
  ("鼠标在哪" finds 鼠标), not a number on this set. Hybrid stays the default at 0.3.
- retrieval, embedding models (same set, same world): MiniLM-L12 R@8 0.80 (en 0.94 / zh 0.66);
  mpnet-base 0.82 (en 0.90 / zh 0.74, cross 0.83 but R@1 0.40 and synonym 0.81); multilingual-e5-large through
  fastembed 0.52 with prefixes and 0.44 without, which is far below the model's reputation and points at the
  ONNX export or pooling in that runtime rather than the model; to be checked with sentence-transformers before
  it is judged. Decision: keep MiniLM; the Chinese → English single-word gap is still open and is the next
  retrieval change to measure (`app/maintenance/reembed.py` switches the server when a model wins).
- tools: sonnet and opus 40/40, haiku 39/40 (it asks which "灯" is meant instead of moving the lantern, which is
  a defensible reading); opus is also the fastest at p50 5.3 s per case against sonnet 9.6 s.
- retrieval: the multilingual MiniLM index is near-perfect within a language (exact 1.00, en 0.94) but weak
  across languages for single words (zh → en 0.66: 电钻 → drill, 卷尺 → tape measure, 投影仪 → projector are
  all missed). This is the measured case for hybrid retrieval.
- tools, first run 0.85: three cases where the model reported `undo_last` / `add_items` as "unavailable". The
  trace showed zero tool calls and the raw CLI result showed three turns: the `claude -p` provider's model was
  trying to invoke the listed functions as native tools. Fixed by rewording the action protocol in
  `llm_claude.py` (not a prompt-quality change; a protocol bug). Second run 1.00.
- tools: `add_items` with an empty item list created the box before validating the list, leaving a stray box
  behind when the model probed with `items: []`. Fixed in `agent_tools.py` with a regression test.

## Production traces and the way back

Every model-backed request (`/api/agent`, `/api/interpret`, `/api/ask`, `/api/recognize`) persists its trace as
a row in `agent_runs` (`backend/app/services/runs.py`): model, prompt version, tool calls with arguments and
results, steps, latency, outcome, error. The response carries the `run_id`, and two signals attach to it:

- explicit: `POST /api/runs/{id}/feedback {"value": 1 | -1, "note"?}` (thumbs up / down);
- implicit: when the user confirms a destructive action the snapshot taken before it records the run that
  proposed it, and an undo marks that run `undone`. Undo is a thumbs down the user did not have to type.

`GET /api/runs?failed=true` lists a user's thumbs-down, undone, errored and step-capped runs. Then:

```bash
backend/.venv/bin/python evals/export.py --since 7d     # → evals/inbox/<stamp>-<set>.jsonl
```

turns those runs into case stubs for the matching set (interpret → routing or extraction, agent → tools), with
the model's own answer prefilled as `expect` and a `_review` note. A human corrects the expectation and moves
the line into the set; stubs are never merged automatically, because a failed run is evidence that the model's
answer is wrong, so its answer cannot be the label. That closes the loop the sets exist for:
production failure → new eval case → prompt change → re-run → deploy.

## Retrieval: hybrid search and embedding models

`backend/app/services/search.py` fuses pgvector cosine neighbours with pg_trgm trigram matches by reciprocal
rank fusion (`BOXMIND_SEARCH_MODE=hybrid|vector`); the agent's `search_items` tool and `/api/ask` both use it.
The retrieval set runs under either mode (`--search vector`) and under any fastembed model
(`--embedding <id> --dim <n> [--prefixes e5]`; the eval database is rebuilt at the new dimension).
Switching the server's model is `python -m app.maintenance.reembed --apply` after changing `backend/.env`.

## Scoring code

`backend/app/evals/score.py` (pure, unit-tested in `backend/tests/test_evals_score.py` and
`test_evals_retrieval_tools.py`), `backend/app/evals/world.py` (fixture world loader and state reader) and
`backend/app/evals/harness.py` (runs the model, writes results). Validation of the golden files runs in CI
(`backend/tests/test_evals_sets.py`) so a malformed case or a reference to an item that is not in the world
fails the build, not the eval run.
