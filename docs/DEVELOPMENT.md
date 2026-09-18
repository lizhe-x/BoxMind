# Development notes

How BoxMind went from a two-intent prototype to a tool-calling agent, and the
decisions that were locked along the way. Written from the per-iteration delivery
reports of June 2026; the reports themselves are not in the repo.

## Timeline

| Iteration | Date | What changed |
|---|---|---|
| 0 | 2026-06-11 | PRD v1.0 and the high-fidelity HTML prototype ([docs/design](design/README.md)). |
| 1 | 2026-06-13 | Data model, CRUD, text intake with LLM extraction, streaming RAG answers, email-code login. Paywall removed: unlimited use, usage only logged. Server-side ASR wired through the gateway. |
| 2 | 2026-06-13 | Photo intake (vision model, per-item confidence), barcode / QR scan (ZXing in the browser), text-to-speech on answers. |
| 3 | 2026-06-13 | Media persistence: photos become box covers, voice notes are stored per box and replayable. Camera / scan entry points made consistent across screens. |
| 4 | 2026-06-14 | The intent classifier was replaced as the operation path by a **function-calling agent** over the app's own API, with confirm-before-destroy and single-step undo. Deployment collapsed to a single process. |
| 5 | 2026-09-17 | Open-source preparation: test suites, CI, docs. |

## Decision log

### Classifier as router, agent as executor

Iteration 1 shipped a single JSON-mode prompt that classified a sentence as `ingest`
or `query`. Every new operation ("rename box 3", "move the drill to box 5") would
have needed a new intent, new extraction fields and new handler code.

Iteration 4 kept the classifier but shrank its job to a three-way route:

- `ingest` → the structured confirm card (cheap, deterministic, no side effects until the user confirms);
- `query` → streaming RAG answer;
- `operation` → the agent.

The agent gets fifteen tools that map onto the service layer (`search_items`,
`create_box`, `add_items`, `move_items`, `rename_box`, `merge_boxes`, ...). The model
decides which to call and in what order; the loop feeds each result back and stops
after six steps. The system prompt embeds a compact snapshot of the user's boxes so
that references like "box 7", "Liam" or "the kitchen box" resolve without a lookup
round-trip and so that quantities can be computed ("add three more" → the tool
receives the final count).

Why not send everything through the agent? Ingest is the most frequent action and
benefits from a fixed UI (confirm card, "which box?" picker, marker reminder). The
classifier costs one small call and keeps that path predictable.

### The model never destroys data on its own

`delete_item`, `delete_box`, `empty_box` and `merge_boxes` are declared to the model
like any other tool, but the loop does not execute them. It returns a `confirm`
payload with a human-readable summary; the UI renders a red card; only an explicit
second request executes the action. Before executing, the affected boxes are
serialised into an undo snapshot (box fields, items, media ownership). `undo_last`
restores them with the same ids, so links in the UI stay valid. Undo is single-step
by design: one snapshot row per user.

Known limit: deleting a box cascades its media rows, so undoing a box deletion
restores items but not photos. Merging moves media rows instead, so undoing a merge
restores photos as well.

### Merge semantics

Same-named items have their quantities summed when the unit parses (`×2` + `×3`
→ `×5`, `×2 双` + `×1 双` → `×3 双`); otherwise the target's value wins. Source
photos and voice notes move to the target; if the target has no cover, the first
merged photo becomes it. Source boxes are deleted, so their barcodes stop resolving.

### Names, labels and duplicates

A box has a display `label` ("7号", "Liam") and a normalised `norm_label` used for
matching: "7号" = "7号箱" = "Box 7" = "七号" = "#7". Text labels are matched
case-insensitively with a trailing 箱 stripped. The agent auto-suffixes duplicates
(Liam → Liam2) and tells the model it did so, rather than failing the tool call.

### Every input path degrades

- Voice: browser Web Speech (on-device, real time) first; MediaRecorder → server ASR
  through the gateway second; typing last. Audio is captured alongside the live
  transcript so the note can be replayed later. Capture failures never block the
  transcript.
- Photo: an empty item list is a valid result, not an error.
- Media: photo and audio uploads happen after the ingest succeeds and are
  best-effort; a failed upload never rolls back the items.
- Gateway: any upstream error is surfaced as a readable 502 with the upstream text,
  so a closed model channel is diagnosable from the UI.

### Models are configuration

Chat, vision, ASR, TTS and embedding model names are settings, and the backend
speaks only the OpenAI-compatible surface (`/chat/completions` with tools and image
input, `/audio/transcriptions`, `/audio/speech`, `/embeddings`). Switching gateway
or model is a `.env` change. Embeddings default to a local fastembed model
(multilingual MiniLM, 384-d) so the RAG path has no external dependency and no per-
call cost.

### Single process in production

The backend serves the built frontend from `frontend/dist`, so one HTTPS endpoint
carries the app, the API and user media. The earlier setup (separate Vite preview
plus reverse proxy) was dropped after it proved fragile.

## Testing approach

Backend tests run against a real PostgreSQL + pgvector database (a throwaway
`boxmind_test`, created on demand) so vector search, cascades and undo snapshots are
exercised for real. Two things are faked: embeddings (deterministic hash vectors, so
exact names always match and nothing is downloaded) and the LLM gateway (a scripted
client that replays tool calls and records every request). This lets the agent loop
be tested turn by turn: which tools were called, what was fed back, when the loop
paused for confirmation, what happened on malformed arguments, and that the step cap
holds.

Frontend tests cover the store (routing of a sentence, the confirm-card flow, photo
intake selection, scan fallback) with the API module mocked, and the API client
(auth header handling, 401 → logout, the SSE parser across chunk boundaries).

See the `test` commands in the README and `.github/workflows/ci.yml`.
