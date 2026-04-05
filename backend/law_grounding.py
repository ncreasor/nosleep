from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import anthropic

from config import settings
from llm_json import parse_llm_json

logger = logging.getLogger(__name__)

GROUNDING_MODEL = "claude-haiku-4-5-20251001"
DOC_CHUNK_MAX = 1200
LAW_EXCERPT_MAX = 1000


def _clip(s: str, n: int) -> str:
    t = (s or "").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _default_grounding() -> dict[str, Any]:
    return {
        "selected_index": None,
        "verdict": "unclear",
        "grounding_confidence": 0,
        "rationale": "Не удалось выполнить проверку соответствия.",
    }


def verify_chunk_candidates_sync(
    client: anthropic.Anthropic,
    doc_chunk: str,
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Given a document fragment and up to 5 retrieved law chunks, ask the model
    which candidate (if any) substantively applies and return a structured verdict.
    """
    if not candidates:
        return _default_grounding()

    dc = _clip(doc_chunk, DOC_CHUNK_MAX)
    lines: list[str] = []
    for i, c in enumerate(candidates):
        payload = c.get("payload") or {}
        title = (payload.get("title") or "").strip() or "Норма РК"
        num = (payload.get("number") or "").strip()
        head = f"{title}" + (f" ({num})" if num else "")
        body = _clip((payload.get("text") or "").strip(), LAW_EXCERPT_MAX)
        lines.append(f"--- Кандидат {i} ---\nНазвание: {head}\nТекст нормы (фрагмент):\n{body}")

    blocks = "\n\n".join(lines)

    prompt = f"""Ты помощник по праву РК. Даны фрагмент пользовательского документа и до 5 фрагментов норм из базы (кандидаты семантического поиска — могут быть ложными попаданиями).

КРИТИЧЕСКИ: «applicable» (подтверждено) ставь ТОЛЬКО если одновременно выполняется:
1) Текст выбранного кандидата по смыслу действительно регулирует или подтверждает описанную ситуацию.
2) Если во фрагменте документа указаны конкретные статьи/формулировки норм — они не противоречат содержанию кандидата (номер статьи в базе и ссылки в тексте должны быть согласованы; нельзя подтверждать, если в договоре сослались на выдуманную или явно ошибочную статью при другом содержании нормы).
3) Нет признаков выдуманных «юридических» новелл: криптовалютная зарплата по умолчанию, обязательная блокчейн-выплата, статьи с абсурдными названиями под видом ТК/ГК РК, запрет пенсии, тотальный контроль геолокации, «неограниченные выходные» как норма и т.п. Если в документе есть такие нереалистичные ссылки, а в тексте кандидата этого нет — это НЕ applicable.

Семантическая близость темы НЕ достаточна, если ссылки в документе фиктивны или не подтверждаются переданным фрагментом нормы.

Фрагмент документа:
\"\"\"
{dc}
\"\"\"

Кандидаты из базы норм:
{blocks}

Верни ТОЛЬКО JSON без markdown:
{{
  "selected_index": <целое 0..{len(candidates) - 1} или null если ни один не подходит>,
  "verdict": "applicable" | "partially_applicable" | "not_applicable" | "unclear",
  "grounding_confidence": <целое 0-100>,
  "rationale": "<1-3 предложения по-русски>"
}}

Правила: при сомнении и при выдуманных/несостыковывающихся ссылках — "not_applicable" или "unclear", selected_index: null. Не выдумывай нормы вне переданных фрагментов."""

    try:
        response = client.messages.create(
            model=GROUNDING_MODEL,
            max_tokens=600,
            temperature=0,
            system="Отвечай только валидным JSON. Эксперт по законодательству РК. Не подтверждай явно ошибочные или фантазийные ссылки на статьи в пользовательских договорах.",
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        data = parse_llm_json(text)
        if not isinstance(data, dict):
            return _default_grounding()

        raw_idx = data.get("selected_index")
        idx: Optional[int] = None
        if raw_idx is not None:
            try:
                ii = int(raw_idx)
                if 0 <= ii < len(candidates):
                    idx = ii
            except (TypeError, ValueError):
                idx = None

        verdict = str(data.get("verdict") or "unclear").lower()
        if verdict not in (
            "applicable",
            "partially_applicable",
            "not_applicable",
            "unclear",
        ):
            verdict = "unclear"

        try:
            gconf = int(data.get("grounding_confidence", 0))
        except (TypeError, ValueError):
            gconf = 0
        gconf = max(0, min(100, gconf))

        rationale = str(data.get("rationale") or "").strip()
        if not rationale:
            rationale = "Оценка без пояснения."

        if verdict == "not_applicable":
            idx = None

        return {
            "selected_index": idx,
            "verdict": verdict,
            "grounding_confidence": gconf,
            "rationale": rationale[:1200],
        }
    except Exception as exc:
        logger.warning("law grounding LLM failed: %s", exc)
        return _default_grounding()


async def verify_chunks_batched(
    doc_chunks: list[str],
    nested_hits: list[list[tuple[Any, float, dict[str, Any], str]]],
    max_concurrency: int,
) -> list[dict[str, Any]]:
    """
    For each chunk index, run grounding on that chunk's Qdrant hit list.
    Returns list aligned with doc_chunks (same length).
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    sem = asyncio.Semaphore(max(1, max_concurrency))

    async def one(
        chunk_text: str,
        group: list[tuple[Any, float, dict[str, Any], str]],
    ) -> dict[str, Any]:
        if not group:
            return _default_grounding()
        candidates: list[dict[str, Any]] = []
        for point_id, score, payload, _dc in group:
            candidates.append(
                {
                    "point_id": point_id,
                    "score": score,
                    "payload": payload,
                }
            )
        async with sem:
            return await asyncio.to_thread(
                verify_chunk_candidates_sync,
                client,
                chunk_text,
                candidates,
            )

    tasks = [
        one(doc_chunks[i], nested_hits[i])
        for i in range(len(doc_chunks))
    ]
    return await asyncio.gather(*tasks)
