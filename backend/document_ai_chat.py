import json
import uuid
import anthropic

from config import settings
from llm_json import parse_llm_json, strip_llm_json_fence

AI_CHAT_MODEL = "claude-haiku-4-5-20251001"
AI_CHAT_SCHEMA = "ai_chat_v1"


def _build_messages_for_api(history: list[tuple[str, str]], user_message: str, document_text: str) -> list[dict]:
    blocks = []
    for role, content in history[-20:]:
        if role == "user":
            blocks.append({"role": "user", "content": content})
        elif role == "assistant":
            blocks.append({"role": "assistant", "content": content})
    blocks.append(
        {
            "role": "user",
            "content": (
                f"[ТЕКУЩИЙ_ТЕКСТ_ДОКУМЕНТА]\n{document_text}\n\n"
                f"[ЗАПРОС_ПОЛЬЗОВАТЕЛЯ]\n{user_message}"
            ),
        }
    )
    return blocks


def run_document_ai_chat_turn(
    *,
    document_text: str,
    history: list[tuple[str, str]],
    user_message: str,
) -> dict:
    doc = (document_text or "")[:14000]
    system = f"""Ты юридический ассистент по документам (Казахстан). Пользователь просит изменить или прокомментировать текст договора/документа.

Правила:
- Отвечай ТОЛЬКО валидным JSON без markdown-обёртки, формат:
{{"schema":"{AI_CHAT_SCHEMA}","reply":"текст ответа пользователю на русском","proposed_edits":[{{"find":"точная подстрока из документа","replace":"новый текст","reason":"кратко"}}],"status":"pending"}}
- Если правки не нужны (только вопрос/объяснение), proposed_edits = [] и status = "none".
- Каждый "find" ДОЛЖЕН дословно встречаться в [ТЕКУЩИЙ_ТЕКСТ_ДОКУМЕНТА] ровно один раз; если не уверен — не предлагай правку, объясни в reply.
- Не выдумывай цитаты: только фрагменты из переданного текста.
- Замены — минимально необходимые для запроса пользователя."""

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    messages = _build_messages_for_api(history, user_message.strip(), doc)

    response = client.messages.create(
        model=AI_CHAT_MODEL,
        max_tokens=4096,
        system=system,
        messages=messages,
    )

    raw = ""
    for block in response.content:
        if block.type == "text":
            raw += block.text

    try:
        data = parse_llm_json(strip_llm_json_fence(raw))
    except json.JSONDecodeError:
        data = {
            "schema": AI_CHAT_SCHEMA,
            "reply": raw[:4000] or "Не удалось разобрать ответ модели.",
            "proposed_edits": [],
            "status": "none",
        }

    if not isinstance(data, dict):
        data = {
            "schema": AI_CHAT_SCHEMA,
            "reply": str(data),
            "proposed_edits": [],
            "status": "none",
        }

    data.setdefault("schema", AI_CHAT_SCHEMA)
    data.setdefault("reply", "")
    data.setdefault("proposed_edits", [])
    data.setdefault("status", "pending" if data.get("proposed_edits") else "none")
    data["proposal_id"] = str(uuid.uuid4())

    edits = []
    for e in data.get("proposed_edits") or []:
        if not isinstance(e, dict):
            continue
        find = (e.get("find") or "").strip()
        replace = e.get("replace")
        if replace is None:
            replace = ""
        if not find or find not in doc:
            continue
        if doc.count(find) != 1:
            continue
        edits.append(
            {
                "find": find,
                "replace": str(replace),
                "reason": (e.get("reason") or "").strip() or None,
            }
        )

    data["proposed_edits"] = edits
    if not edits:
        data["status"] = "none"
    else:
        data["status"] = "pending"

    return data


def assistant_message_to_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


def parse_stored_assistant_message(content: str | None) -> dict | None:
    if not content or not content.strip().startswith("{"):
        return None
    try:
        d = parse_llm_json(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict) or d.get("schema") != AI_CHAT_SCHEMA:
        return None
    return d


def merge_message_status(content: str | None, status: str) -> str | None:
    d = parse_stored_assistant_message(content)
    if not d:
        return content
    d["status"] = status
    return assistant_message_to_json(d)
