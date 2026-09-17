import json
import re
from typing import AsyncIterator

import httpx

from ..config import settings

_INTERPRET_SYSTEM = """你是 BoxMind(箱子物品管理应用)的解析引擎。用户会说一句话,可能是「录入物品」或「查询/提问」。
你必须只输出一个 JSON 对象,不要输出任何其他文字。结构:

{
  "intent": "ingest" | "query" | "operation",
  "box_label": string | null,      // 用户提到的箱子编号/名字,原样保留,如 "1号"、"A2"、"红色大箱";没提到则 null
  "items": [{"name": string, "qty_text": string}],   // intent=ingest 时的物品列表,否则 []
  "location_text": string | null,  // 用户描述的存放位置,如 "车库左侧第二层货架";没说则 null
  "language": "zh" | "en" | "es"   // 用户这句话的语言
}

规则:
- 只有"把东西放进箱子" 才是 ingest: "1号箱我放了羽绒服三件" → intent=ingest, box_label="1号"
- 提问/找东西/统计 → query: "我的雪地靴在哪" / "3号箱里有什么" / "我有几个箱子"
- 其它对箱子/物品的"操作"一律 → operation(这类只需返回 intent=operation,其它字段可空):
  改位置("7号箱在厨房水槽下面")、改名("3号箱改名叫工具箱")、合并("把6号并到7号")、
  删箱/删物品("删掉钳子")、移动("把电钻移到5号")、清空、绑码、记录当前GPS位置、
  撤销/还原/撤回("撤销""撤销上一步""还原")
- qty_text 格式: "×3"、"×2 双"、"×1 袋";数量不明确用 "若干"
- box_label 归一化: "1号箱"/"Box 1"/"一号" 都写成 "1号";字母/中文编号原样保留(去掉末尾的"箱"字,如"红色大箱"→"红色大箱"保留原样)
- 物品名称保持用户用语,不要翻译
- 录入语句里的位置描述放 location_text,不要混进 items"""

_VISION_SYSTEM = """你是 BoxMind 的拍照识别引擎。用户拍了一张「打开的收纳箱」照片,你要识别箱内物品,并尽量读出箱子上的手写编号。
只输出一个 JSON 对象,不要任何其他文字。结构:

{
  "box_label": string | null,   // 照片里箱子上的手写编号(如 "2号"、"A2");看不到则 null
  "items": [
    {"name": string, "qty_text": string, "confidence": "high" | "medium" | "low"}
  ]
}

规则:
- 只识别能看清的实物;每类物品一行,name 用中文常见叫法
- qty_text 格式 "×3"、"×2 双";数量不确定用 "若干"
- confidence: 清楚可辨 high,较模糊 medium,猜测 low
- 看不出任何物品时 items 为空数组"""

_ANSWER_SYSTEM = """你是 BoxMind 的 AI 助手,帮用户找到存放在箱子里的物品。下面提供了该用户的全部箱子数据(JSON)。

回答规则:
- 用用户提问的语言回答(中文问答中文,英文问答英文,西语问答西语);物品名保留录入时的原文
- 跨语言语义匹配: 比如用户问 "snow boots"、数据里是 "雪地靴",要能对上;"保暖的衣服" 能匹配 "羽绒服"
- 回答要具体: 在哪个箱子、数量、位置描述、最后更新时间;聚合问题(几个箱子、哪些没记位置)直接基于数据统计
- 找不到就如实说没有记录,并提示用户可能没录入过
- 口语化、简洁,2~3 句话以内,不用列表不用 markdown
- 「相关度参考」是向量检索的提示,仅供参考,以完整数据为准"""


class LLM:
    def __init__(self) -> None:
        self._headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        self._url = f"{settings.llm_base_url}/chat/completions"

    async def interpret(self, text: str, known_labels: list[str]) -> dict:
        hint = f"该用户已有的箱子编号: {', '.join(known_labels)}" if known_labels else "该用户还没有任何箱子"
        payload = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": _INTERPRET_SYSTEM},
                {"role": "user", "content": f"{hint}\n\n用户的话: {text}"},
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
        parsed.setdefault("language", "zh")
        parsed["_tokens"] = usage
        return parsed

    async def recognize_image(self, image_b64: str, mime: str = "image/jpeg") -> dict:
        payload = {
            "model": settings.vision_model,
            "messages": [
                {"role": "system", "content": _VISION_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "识别这张收纳箱照片里的物品和手写编号,按要求输出 JSON。"},
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
                    "content": f"箱子数据:\n{context_json}\n\n相关度参考(向量检索 top 命中): {relevant_hint}\n\n用户提问: {question}",
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
