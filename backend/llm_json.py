import json
from typing import Any


def strip_llm_json_fence(text: str) -> str:
    t = (text or "").strip()
    if not t.startswith("```"):
        return t
    first_nl = t.find("\n")
    if first_nl == -1:
        inner = t.removeprefix("```")
        if inner.startswith("json"):
            inner = inner[4:].lstrip()
        if inner.endswith("```"):
            inner = inner[:-3]
        return inner.strip()
    body = t[first_nl + 1 :].rstrip()
    if body.endswith("```"):
        body = body[:-3].rstrip()
    return body


def parse_llm_json(text: str) -> Any:
    return json.loads(strip_llm_json_fence(text))
