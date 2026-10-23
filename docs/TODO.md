# Known issues and to-do

Things found while reviewing the AI architecture (October 2026). None of them blocks the MVP; they are written
down so they are known, not because they must be fixed now.

## 1. Let the program do quantity arithmetic, not the model (optimization; fixes a bug)

**Today.** Quantities are stored as text (`qty_text`: "×3", "×2 pairs", "×2 双", "some"/"若干"). When the user says
"add 3 more batteries to box 1", the agent prompt tells the model to compute the final value itself and send it
(`AGENT` prompt: "Quantities are final values"; `add_items` / `update_item` take the final quantity). The model
can get the sum wrong, and nothing checks it.

**Bug on the ingest path.** `boxes_service.add_items` *overwrites* the quantity when an item with the same name is
already in the box. The ingest path has no idea of the existing quantity: box 1 holds "down jacket ×3", the user
says "put two down jackets in box 1", the confirm card shows ×2, and after confirming the box holds ×2, not ×5.

**Plan.**
- Give `add_items` (and `update_item`) a delta form, e.g. `qty_delta: int` or `mode: "add" | "set"`. The model says
  "+3"; the backend does the math.
- Reuse the parser that already exists for merges (`agent_destructive._merge_qty`: "×2 双" + "×1 双" → "×3 双").
  Fall back to the model's text only when no number parses ("some" / "若干").
- Ingest path: when an item already exists, the confirm card shows the current quantity and asks
  "set to ×2 or add to ×5?" (default: add).
- Add cases to `evals/tools.jsonl` and unit tests for the delta form and the ingest add/set choice.

## 2. RAG context cap is untested

`ask_router.MAX_CONTEXT_ITEMS = 400`: above 400 items only the boxes hit by search go to the model. The code path
exists but no test or eval reaches it (fixtures are far smaller). Add a test that builds > 400 items and checks
which boxes end up in the context.

## 3. Agent snapshot has no size limit

The agent system prompt embeds every box *and every item* (`agent_tools.box_brief`). There is no cap, so a large
inventory makes every agent call longer and more expensive. Options: cap like `/api/ask` does, or send boxes only
and let the model call `get_box` / `search_items` for items.

## 4. Speech misrecognition on the query / operation paths

When on-device speech returns wrong text (not empty text), there is no second pass. On the ingest path the user
can see and edit the text on the confirm card and re-parse. On the query and operation paths the text is sent
directly: a wrong query just needs asking again, destructive operations still stop at the confirm card, but a
non-destructive operation (e.g. move) runs. Consider echoing the recognised text with a short undo window, or
extending undo to non-destructive operations.

## 5. Indexes for large single-user inventories

Search filters by user (`boxes.user_id` and `items.box_id` are indexed), so each query only scans one user's
items; more users do not slow it down. There is no HNSW / IVFFlat index on `items.embedding` and no GIN trigram
index on `items.name`. Needed only if one user grows to many thousands of items. Note for that day: a global ANN
index followed by a per-user filter can lose recall (filtered vector search); prefer per-user partitioning or
filter-aware index settings.

## 6. Structured output on the gateway path

The gateway provider uses `response_format: {"type": "json_object"}` plus tolerant parsing and defaults; the
`claude -p` provider uses `--json-schema`. Try `json_schema` (strict) on the gateway first and fall back to
`json_object` where the hosting provider does not support it.
