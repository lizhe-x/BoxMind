"""Per-request trace of the model layer.

Every model-backed request (interpret, agent, ask, recognize) opens a Trace that records which model and
prompt wording produced the result, which tools ran with what arguments, how many model round-trips it took,
how long it took and how it ended. The eval harness (`evals/`) reads traces to score tool-call sequences and
confirm-gate behaviour; production tracing persists them (see docs/IOS_PLAN.md and the eval README).

Traces are tied to the current task via contextvars, so callers deep in the stack can add to them without
threading a parameter through every function.
"""
from __future__ import annotations

import contextvars
import hashlib
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field


def prompt_id(text: str) -> str:
    """Short content hash of a prompt: pins the exact wording that produced a result."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:10]


@dataclass
class ToolCall:
    name: str
    args: dict
    ok: bool
    ms: int
    error: str | None = None


@dataclass
class Trace:
    kind: str                      # interpret | agent | ask | recognize
    model: str = ""
    prompts: dict[str, str] = field(default_factory=dict)   # prompt name -> prompt_id
    input: str = ""
    lang: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    confirm: list[str] = field(default_factory=list)        # destructive tools handed to the confirm gate
    steps: int = 0                 # model round-trips
    tokens: int = 0
    outcome: str = ""              # ok | message | confirm | step_cap | error
    error: str | None = None
    output: dict = field(default_factory=dict)
    latency_ms: int = 0
    _t0: float = field(default_factory=time.monotonic, repr=False, compare=False)

    def tool(self, name: str, args: dict, result: dict | None, ms: int, error: str | None = None) -> None:
        ok = error is None and bool((result or {}).get("ok", True))
        self.tool_calls.append(ToolCall(name=name, args=args, ok=ok, ms=ms, error=error or (result or {}).get("error")))

    def finish(self, outcome: str, **output) -> Trace:
        self.outcome = outcome
        self.output.update(output)
        self.latency_ms = int((time.monotonic() - self._t0) * 1000)
        return self

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("_t0", None)
        return d


_current: contextvars.ContextVar[Trace | None] = contextvars.ContextVar("boxmind_trace", default=None)
_sink: contextvars.ContextVar[list[Trace] | None] = contextvars.ContextVar("boxmind_trace_sink", default=None)


def start(kind: str, **fields) -> Trace:
    """Open a trace for the current task; it also lands in the enclosing `collect()` list, if any."""
    t = Trace(kind=kind, **fields)
    _current.set(t)
    sink = _sink.get()
    if sink is not None:
        sink.append(t)
    return t


def current() -> Trace | None:
    return _current.get()


@contextmanager
def collect() -> Iterator[list[Trace]]:
    """Collect every trace started inside the block (same task or tasks created inside it)."""
    traces: list[Trace] = []
    token = _sink.set(traces)
    try:
        yield traces
    finally:
        _sink.reset(token)


def ms_since(t0: float) -> int:
    return int((time.monotonic() - t0) * 1000)
