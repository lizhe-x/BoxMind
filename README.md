# BoxMind

**An AI-native inventory assistant for boxes, storage units, garages, and closets.**

[![CI](https://github.com/lizhe-x/BoxMind/actions/workflows/ci.yml/badge.svg)](https://github.com/lizhe-x/BoxMind/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.11](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![React 19](https://img.shields.io/badge/react-19-149ECA?logo=react&logoColor=white)
![PostgreSQL 17 + pgvector](https://img.shields.io/badge/postgres-17%20%2B%20pgvector-336791?logo=postgresql&logoColor=white)

BoxMind lets you **record, find, and reorganize physical inventory using natural language**.

Say what went into a box by voice, text, photo, or barcode. Later ask *"Where is the tent?"* and get an answer with the relevant box. For operations such as *"move the headlamps from box 5 to box 7"* or *"merge the kitchen boxes"*, an LLM function-calling agent operates the application's own API.

The core idea is simple:

> **The model proposes actions; the application enforces the rules.**

Tool schemas, database validation, confirmation gates, snapshots, undo, and tests keep the model inside a bounded execution environment.

Built solo as an MVP in June 2026.

<p align="center">
  <img src="docs/screenshots/home.png" width="230" alt="Home: one big talk button">
  <img src="docs/screenshots/entry-confirm.png" width="230" alt="Structured confirm card after one sentence">
  <img src="docs/screenshots/ask.png" width="230" alt="Streaming answer with a tappable box card">
  <img src="docs/screenshots/agent-confirm.png" width="230" alt="Agent pauses for confirmation before a destructive merge">
</p>

## Why this project

BoxMind is less about building a chatbot and more about exploring **reliable AI application architecture**.

- **Interpretation** — LLMs understand natural language and choose tools.
- **Execution** — typed backend tools perform the actual operations.
- **Validation** — every tool validates arguments against current database state.
- **Safety** — destructive operations require explicit confirmation.
- **Recovery** — snapshots make destructive operations undoable.
- **Retrieval** — pgvector provides semantic search across inventory.
- **Verification** — the orchestration layer is tested without requiring a real LLM.

This keeps the model replaceable without making the application dependent on model behavior.

## What it can do

| Capability | Implementation |
|---|---|
| Natural-language operations | Function-calling agent with 15 typed tools |
| Safe destructive actions | Confirmation + database snapshots + undo |
| Structured intake | One sentence → structured box/item data → confirmation |
| Semantic search | Multilingual MiniLM embeddings + PostgreSQL/pgvector |
| Photo intake | Vision model extracts items and confidence |
| Voice input | Browser Web Speech + server ASR fallback |
| Barcode / QR | Browser-side ZXing |
| Streaming answers | Server-Sent Events (SSE) |
| Read-aloud | TTS |
| Media | Photos and voice notes per box |
| Localization | English / Chinese |
| Export | JSON / CSV |
| Authentication | Email verification-code login |

## Agent architecture

```text
User
 │
 ▼
React 19 PWA
 │
 ▼
FastAPI
 ├── intent router: ingest / query / operation
 ├── function-calling agent
 ├── confirmation gate
 └── typed tool executors
 │
 ├──────────────► OpenAI-compatible model gateway
 │
 ▼
PostgreSQL 17 + pgvector
```

A typical operation follows:

```text
Natural-language request
        │
        ▼
Intent classification
        │
        ▼
LLM proposes typed tool calls
        │
        ├── non-destructive → validate → execute
        │
        └── destructive → summarize → user confirms
                                      │
                                      ▼
                               snapshot → execute
                                      │
                                      ▼
                                     undo
```

### The classifier is a router, not the application brain

A small JSON-mode call routes requests to ingest, query, or operation. Common intake remains deterministic; the agent handles the long tail of natural-language operations.

### Destructive operations are a two-step protocol

The model can propose delete, empty, or merge operations, but those actions do not execute immediately. The backend returns a human-readable confirmation request. After explicit confirmation, affected data is snapshotted before execution.

### The database remains authoritative

The model receives compact context to resolve references such as "box 7" or "the kitchen box", but every tool validates against current database state. The model can be wrong; it cannot bypass the application's state and validation rules.

The trace behind the screenshots above, end to end: *"Move the power drill from box 4 to box 2, then merge Kitchen spare into box 5"* → the router returns `operation` → the model emits `move_items` and `merge_boxes` in one turn → the move runs immediately, the merge comes back as a confirmation card → the user confirms → the affected boxes are snapshotted, the merge executes → *"undo"* restores them with the same ids. The full decision log, including the move from a two-intent classifier to this agent, is in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

<p align="center">
  <img src="docs/screenshots/agent-done.png" width="230" alt="Agent reports the executed merge">
  <img src="docs/screenshots/boxes.png" width="230" alt="Box list">
  <img src="docs/screenshots/box-detail.png" width="230" alt="Box detail with items, location and media">
</p>

## Testing

The AI orchestration is deliberately tested without depending on an external model.

| Suite | Count | Coverage |
|---|---:|---|
| Backend pytest | 163 | Real PostgreSQL + pgvector, FastAPI, cascades, snapshots, undo, agent loop, malformed arguments, confirmation flow |
| Frontend Vitest | 47 | State machine, routing, confirmation flow, camera/scan fallback, localization, API client and SSE parsing |

The LLM gateway is replaced by a scripted client that records requests and replays tool calls. Embeddings use deterministic test vectors.

```bash
cd backend
pip install -r requirements-dev.txt
ruff check app tests
pytest

cd frontend
npm ci
npm run lint
npm test
npm run build
```

CI runs both suites on every push: [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Run locally

```bash
docker compose up -d

cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env           # set BOXMIND_LLM_API_KEY at minimum
uvicorn app.main:app --port 8001

cd ../frontend
npm install
npm run dev                    # http://localhost:5173, /api proxied to :8001
```

Signing in without a mail server: leave `BOXMIND_SMTP_HOST` empty and the login screen shows the verification code it would have emailed (dev mode). The first backend start downloads the embedding model (about 500 MB) once. For production, `npm run build` and start the backend; it serves `frontend/dist` itself, so one process carries the app, the API and user media.

## Configuration

All settings are environment variables prefixed `BOXMIND_`, documented in [backend/.env.example](backend/.env.example). Model names (`LLM_MODEL`, `VISION_MODEL`, `ASR_MODEL`, `TTS_MODEL`, `EMBEDDING_MODEL`) are configuration, not code; any OpenAI-compatible gateway works. The default points at [getbot.me](https://api.getbot.me), a gateway I also run.

Before exposing an instance:

- `BOXMIND_JWT_SECRET` has a development default. Set it.
- Dev-mode login (empty SMTP host) returns verification codes from the API. Configure SMTP for anything reachable by others.
- CORS allows localhost and private-network origins only; the intended deployment serves frontend and API from the same origin.
- Secrets, TLS certificates and user media are git-ignored.

Data created before the English default (Chinese box names such as 5号箱) can be re-localised in place. It is a dry run unless `--apply` is given, and it never touches text the user typed:

```bash
cd backend && python -m app.maintenance.relabel --lang en --apply
```

## Stack

**Backend:** Python 3.11, FastAPI, SQLAlchemy 2, PostgreSQL 17, pgvector, fastembed, PyJWT

**Frontend:** React 19, TypeScript, Vite, zustand, PWA, ZXing

**AI:** LLM function calling, vision, ASR, TTS, multilingual embeddings, RAG

**Infrastructure:** Docker, GitHub Actions

Approximately 6K lines of application code plus 2K lines of tests.

## Status

MVP / single-user application.

Current limitations:

- Single user per account; no sharing
- Single-step undo
- Photo recognition depends on the vision model and input quality
- Server-side ASR depends on the configured gateway
- PWA rather than a native mobile application

## Documentation

- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — iteration timeline and decision log: why the classifier became a router, the confirm-before-destroy protocol, merge semantics, how language is handled, the testing approach.
- [docs/design/](docs/design/README.md) — the PRD v1.0 and the high-fidelity HTML prototype the app was built from, with a table of where the implementation deviates.
- [docs/screenshots/](docs/screenshots/) — the images used above, captured from the running app.

<p align="center">
  <img src="docs/screenshots/prototype.png" width="230" alt="The HTML prototype the implementation was built from"><br>
  <sub>The pre-implementation prototype.</sub>
</p>

## License

MIT