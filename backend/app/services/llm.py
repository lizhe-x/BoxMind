import json
import re
from collections.abc import AsyncIterator

import httpx

from ..config import settings
from ..i18n import lang_name, tr

_INTERPRET_SYSTEM = """You are the parsing engine of BoxMind, an app that remembers what is stored in which box.
The user says one sentence. Classify it and extract structure. Output exactly one JSON object and nothing else:

{{
  "intent": "ingest" | "query" | "operation",
  "box_label": string | null,      // box label/name as the user said it ("1", "1号", "A2", "red box"); null if none
  "items": [{{"name": string, "qty_text": string}}],   // items when intent=ingest, otherwise []
  "location_text": string | null,  // where the box is, e.g. "garage, left shelf, second tier"; null if not said
  "language": "zh" | "en" | "es"   // the language of this sentence
}}

Rules:
- ingest = putting things into a box: "box 1 has three down jackets" → intent=ingest, box_label="1"
- query = asking / looking for / counting: "where are my snow boots", "what is in box 3", "how many boxes do I have"
- everything else that changes boxes or items → operation (only intent matters, other fields may be empty):
  change location ("box 7 is under the kitchen sink"), rename ("call box 3 the tool box"), merge ("merge 6 into 7"),
  delete a box or item ("remove the pliers"), move ("move the drill to box 5"), empty, bind a code,
  record the current GPS position, undo / revert / restore.
- qty_text format: "×3", "×2 pairs", "×1 bag"; use "{some}" when the quantity is unclear
- box_label: normalise numeric labels to the bare number ("box 1" / "1号箱" / "一号" → "1");
  keep letter or word labels as written, dropping a trailing "box"/"箱"
- keep item names in the user's own words, do not translate them
- a location mentioned in an ingest sentence goes to location_text, not into items"""

_VISION_SYSTEM = """You are BoxMind's photo intake engine. The user photographed an open storage box. Identify the items
inside and, if visible, read the handwritten label on the box. Output exactly one JSON object and nothing else:

{{
  "box_label": string | null,   // handwritten label on the box, e.g. "2", "A2"; null if not visible
  "items": [
    {{"name": string, "qty_text": string, "confidence": "high" | "medium" | "low"}}
  ]
}}

Rules:
- only list physical items you can actually see; one line per kind of item; item names in {lang}
- qty_text format "×3", "×2 pairs"; use "{some}" when unsure
- confidence: clearly visible → high, partly visible → medium, a guess → low
- if nothing recognisable is in the photo, items is an empty array"""

_ANSWER_SYSTEM = """You are BoxMind's assistant. You help the user find things stored in their boxes.
Below is all of the user's box data as JSON.

Rules:
- answer in the language the question was asked in (Chinese → Chinese, English → English, Spanish → Spanish); keep
  item names exactly as they were recorded
- match meaning across languages: a question about "snow boots" matches an item recorded as "雪地靴";
  "warm clothes" matches "down jacket"
- be specific: which box, how many, the location description, when it was last updated; for aggregate questions
  (how many boxes, which boxes have no location) count from the data
- if there is no record, say so and suggest the item may never have been recorded
- conversational, at most 2–3 sentences, plain text only: no lists, no markdown, no bold
- the "relevance hints" come from vector search and are only hints; the full data is authoritative"""


class LLM:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        self._url = f"{settings.llm_base_url}/chat/completions"

    async def interpret(self, text: str, known_labels: list[str], lang: str | None = None) -> dict:
        hint = f"The user's existing box labels: {', '.join(known_labels)}" if known_labels \
            else "The user has no boxes yet"
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": _INTERPRET_SYSTEM.format(some=tr(lang, "qty_some"))},
                {"role": "user", "content": f"{hint}\n\nUser said: {text}"},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(self._url, headers=self._headers, json=payload)
            r.raise_for_status()
            data = r.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {}).get("total_tokens", 0)
        parsed = _parse_json(content)
        parsed.setdefault("intent", "query")
        parsed.setdefault("box_label", None)
        parsed.setdefault("items", [])
        parsed.setdefault("location_text", None)
        parsed.setdefault("language", lang or "en")
        parsed["_tokens"] = usage
        return parsed

    async def recognize_image(self, image_b64: str, mime: str = "image/jpeg", lang: str | None = None) -> dict:
        payload = {
            "model": settings.vision_model,
            "messages": [
                {"role": "system", "content": _VISION_SYSTEM.format(lang=lang_name(lang), some=tr(lang, "qty_some"))},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Identify the items and the handwritten label in this photo of a "
                                                 "storage box. Output JSON as instructed."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                    ],
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(self._url, headers=self._headers, json=payload)
            r.raise_for_status()
            data = r.json()
        parsed = _parse_json(data["choices"][0]["message"]["content"])
        parsed.setdefault("box_label", None)
        parsed.setdefault("items", [])
        return parsed

    async def chat_with_tools(self, messages: list[dict], tools: list[dict]) -> dict:
        """带工具的对话(function calling)。返回助手消息(含 tool_calls 或 content)。"""
        payload = {
            "model": settings.llm_model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0,
        }
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(self._url, headers=self._headers, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]

    async def answer_stream(
        self, question: str, context_json: str, relevant_hint: str
    ) -> AsyncIterator[str]:
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": _ANSWER_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Box data:\n{context_json}\n\n"
                        f"Relevance hints (top vector-search hits): {relevant_hint}\n\n"
                        f"Question: {question}"
                    ),
                },
            ],
            "temperature": 0.3,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", self._url, headers=self._headers, json=payload) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if chunk == "[DONE]":
                        break
                    try:
                        delta = json.loads(chunk)["choices"][0]["delta"].get("content")
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    if delta:
                        yield delta


def _parse_json(content: str) -> dict:
    content = content.strip()
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        content = m.group(0)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}


llm = LLM()
