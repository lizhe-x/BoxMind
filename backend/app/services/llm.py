import json
import re
from collections.abc import AsyncIterator

import httpx

from ..config import settings
from ..i18n import lang_name, tr
from . import trace
from .prompts import ANSWER, INTERPRET, VISION


class LLM:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        self._url = f"{settings.llm_base_url}/chat/completions"

    @property
    def model_name(self) -> str:
        return settings.llm_model

    async def interpret(self, text: str, known_labels: list[str], lang: str | None = None) -> dict:
        """One sentence → intent + structure. Traced; providers implement `_interpret`."""
        t = trace.start("interpret", model=self.model_name, prompts={"interpret": INTERPRET.ref},
                        input=text, lang=lang or "")
        try:
            parsed = await self._interpret(text, known_labels, lang)
        except Exception as e:
            t.error = str(e)
            t.finish("error")
            raise
        parsed.setdefault("intent", "query")
        parsed.setdefault("box_label", None)
        parsed.setdefault("items", [])
        parsed.setdefault("location_text", None)
        parsed.setdefault("language", lang or "en")
        t.tokens = int(parsed.get("_tokens") or 0)
        t.finish("ok", parsed={k: v for k, v in parsed.items() if not k.startswith("_")})
        return parsed

    @staticmethod
    def _label_hint(known_labels: list[str]) -> str:
        return f"The user's existing box labels: {', '.join(known_labels)}" if known_labels \
            else "The user has no boxes yet"

    async def _interpret(self, text: str, known_labels: list[str], lang: str | None) -> dict:
        hint = self._label_hint(known_labels)
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": INTERPRET.format(some=tr(lang, "qty_some"))},
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
        parsed["_tokens"] = usage
        return parsed

    async def recognize_image(self, image_b64: str, mime: str = "image/jpeg", lang: str | None = None) -> dict:
        payload = {
            "model": settings.vision_model,
            "messages": [
                {"role": "system", "content": VISION.format(lang=lang_name(lang), some=tr(lang, "qty_some"))},
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
                {"role": "system", "content": ANSWER.text},
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


def _make() -> LLM:
    if settings.llm_provider == "claude_code":
        from .llm_claude import ClaudeCodeLLM  # imported late: it subclasses LLM and reuses the prompts above
        return ClaudeCodeLLM()
    return LLM()


llm = _make()
