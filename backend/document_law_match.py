import asyncio
import logging
import re
import time
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from zeroentropy import ZeroEntropy

from config import settings

logger = logging.getLogger(__name__)

CHUNK_WORDS = 350
CHUNK_OVERLAP = 50
MIN_CHUNK_WORDS = 40
EMBED_BATCH = 16
VECTOR_DIM = 1280
ZEMBED_MODEL = "zembed-1"
MAX_DOC_CHUNKS = 48
RETRY_ATTEMPTS = 5
RETRY_BASE_DELAY = 1.0


def _chunk_document_words(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []
    step = max(1, CHUNK_WORDS - CHUNK_OVERLAP)
    chunks: list[str] = []
    for i in range(0, len(words), step):
        part = words[i : i + CHUNK_WORDS]
        if len(part) < MIN_CHUNK_WORDS and i + CHUNK_WORDS < len(words):
            continue
        joined = " ".join(part).strip()
        if joined:
            chunks.append(joined)
    if not chunks:
        chunks.append(" ".join(words).strip())
    return chunks


def _embed_batch(ze: ZeroEntropy, texts: list[str]) -> list[list[float]]:
    delay = RETRY_BASE_DELAY
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        try:
            resp = ze.models.embed(
                model=ZEMBED_MODEL,
                input=texts,
                input_type="document",
                dimensions=VECTOR_DIM,
                encoding_format="float",
            )
            return [item.embedding[:VECTOR_DIM] for item in resp.results]
        except Exception as exc:
            if attempt == RETRY_ATTEMPTS:
                raise
            logger.warning(
                "ZeroEntropy embed batch attempt %s/%s failed: %s — retry in %ss",
                attempt,
                RETRY_ATTEMPTS,
                exc,
                delay,
            )
            time.sleep(delay)
            delay *= 2
    raise RuntimeError("embed_batch: exhausted retries")


def _embed_all(ze: ZeroEntropy, texts: list[str]) -> list[list[float]]:
    out: list[list[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        out.extend(_embed_batch(ze, batch))
    return out


def _language_filter(language: Optional[str]) -> Optional[Filter]:
    if not language:
        return None
    return Filter(must=[FieldCondition(key="language", match=MatchValue(value=language))])


_DOC_ARTICLE_RE = re.compile(
    r"(?:^|[\s,.;:(]|№\s*)(?:статья|ст\.?)\s*(\d+)",
    re.IGNORECASE | re.MULTILINE,
)
_CHUNK_FIRST_ARTICLE_RE = re.compile(
    r"(?:^|\n)\s*(?:Статья|СТАТЬЯ|статья)\s+(\d+)",
    re.MULTILINE,
)
_KAZ_BAP_RE = re.compile(r"(?:^|\n)\s*(\d+)\s*[-–]\s*(?:бап|бабы)\b", re.MULTILINE)


def _extract_article_numbers_from_text(text: str) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _DOC_ARTICLE_RE.finditer(text):
        n = m.group(1)
        if n not in seen:
            seen.add(n)
            out.append(n)
    for m in _KAZ_BAP_RE.finditer(text):
        n = m.group(1)
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _extract_primary_article_from_law_chunk(law_text: str) -> Optional[str]:
    if not law_text:
        return None
    m = _CHUNK_FIRST_ARTICLE_RE.search(law_text.strip())
    if m:
        return m.group(1)
    m2 = re.search(r"(?:ст\.|статья)\s+(\d+)", law_text[:800], re.IGNORECASE)
    return m2.group(1) if m2 else None


def _guess_law_code(title: str, sphere: str) -> Optional[str]:
    t = f"{title or ''} {sphere or ''}".lower()
    pairs = [
        ("трудовой", "ТК РК"),
        ("тк рк", "ТК РК"),
        ("гражданский процессуальный", "ГПК РК"),
        ("гпк рк", "ГПК РК"),
        ("уголовно-процессуальный", "УПК РК"),
        ("упк рк", "УПК РК"),
        ("гражданск", "ГК РК"),
        ("гк рк", "ГК РК"),
        ("налогов", "НК РК"),
        ("нк рк", "НК РК"),
        ("уголовн", "УК РК"),
        ("ук рк", "УК РК"),
        ("административн", "КоАП РК"),
        ("коап", "КоАП РК"),
        ("земельн", "ЗК РК"),
        ("зк рк", "ЗК РК"),
        ("жилищн", "ЖК РК"),
        ("жк рк", "ЖК РК"),
        ("семейн", "СК РК"),
        ("ск рк", "СК РК"),
    ]
    for needle, code in pairs:
        if needle in t:
            return code
    if sphere == "labor":
        return "ТК РК"
    if sphere == "finance":
        return "НК РК"
    if sphere == "civilian_rights":
        return "ГК РК"
    return None


def _score_to_confidence(score: float) -> tuple[int, str]:
    s = max(0.0, min(1.0, float(score)))
    pct = int(round(s * 100))
    if pct >= 72:
        level = "high"
    elif pct >= 48:
        level = "medium"
    else:
        level = "low"
    return pct, level


def _law_point_to_article(
    *,
    score: float,
    payload: dict[str, Any],
    doc_chunk: str,
    point_id: Any,
) -> dict[str, Any]:
    from laws_validator import validate_norm

    title = (payload.get("title") or "").strip() or "Норма законодательства РК"
    num = (payload.get("number") or "").strip()
    norm_text = f"{title}" + (f" ({num})" if num else "")
    if len(norm_text) > 220:
        norm_text = norm_text[:217] + "…"
    is_active = payload.get("is_active", True)
    law_full = (payload.get("text") or "").strip()
    law_snip = law_full[:420].strip()

    cited_in_doc = _extract_article_numbers_from_text(doc_chunk)
    chunk_article = _extract_primary_article_from_law_chunk(law_full)
    law_code = _guess_law_code(title, str(payload.get("sphere") or ""))

    registry: Optional[dict[str, Any]] = None
    if chunk_article and law_code:
        synthetic = f"ст. {chunk_article} {law_code}"
        registry = validate_norm(synthetic)

    if chunk_article is None:
        alignment = "unknown"
    elif not cited_in_doc:
        alignment = "unknown"
    elif chunk_article in cited_in_doc:
        alignment = "match"
    else:
        alignment = "mismatch"

    if alignment == "match":
        av_label = "Номера статей в фрагменте документа и в найденной норме согласованы"
    elif alignment == "mismatch":
        av_label = "Номера статей в тексте документа и в фрагменте нормы различаются — перепроверьте ссылку"
    else:
        av_label = "Нет явных ссылок на статьи в фрагменте документа или не удалось извлечь номер статьи из нормы"

    reg_note = ""
    if registry and registry.get("valid"):
        reg_note = f"Проверка номера: ст. {chunk_article} {law_code} есть в справочнике."
    elif registry and not registry.get("valid"):
        reg_note = f"Проверка номера: {registry.get('reason') or 'нет в локальной базе'}"

    confidence_pct, confidence_level = _score_to_confidence(score)

    applicability_parts = []
    if reg_note:
        applicability_parts.append(reg_note)
    if law_snip:
        applicability_parts.append(law_snip)
    applicability = " ".join(applicability_parts)[:1100]

    return {
        "norm_text": norm_text,
        "title": title,
        "status": "valid" if is_active else "outdated",
        "applicability": applicability,
        "usage_context": (
            f"Фрагмент вашего документа, по которому найдено соответствие:\n{doc_chunk[:900]}"
        ),
        "introduced": payload.get("date") or None,
        "amendments": [],
        "replaced_by": None,
        "deleted_at": None,
        "current_status_explanation": (payload.get("status") or "").strip()
        or ("Норма действует" if is_active else "Норма не действует / утратила силу"),
        "law_url": payload.get("url"),
        "law_chunk_preview": law_snip,
        "confidence": confidence_pct,
        "confidence_level": confidence_level,
        "relevance_score": round(float(score), 6),
        "article_verification": {
            "cited_article_numbers": cited_in_doc,
            "norm_article_number": chunk_article,
            "inferred_law_code": law_code,
            "alignment": alignment,
            "label": av_label,
            "registry": {
                "checked": bool(registry),
                "valid": registry.get("valid") if registry else None,
                "synthetic_reference": f"ст. {chunk_article} {law_code}" if chunk_article and law_code else None,
                "reason": registry.get("reason") if registry else None,
            },
        },
        "qdrant_point_id": str(point_id),
        "match_method": "qdrant_semantic_zembed",
    }


async def match_document_to_laws(
    document_text: str,
    *,
    language: str = "rus",
    top_k_per_chunk: int = 5,
    max_results: int = 28,
) -> dict[str, Any]:
    text = (document_text or "").strip()
    if not text:
        return {
            "articles": [],
            "meta": {
                "document_chunks": 0,
                "collection": settings.qdrant_laws_collection,
                "truncated": False,
            },
        }

    chunks = _chunk_document_words(text)
    truncated = False
    if len(chunks) > MAX_DOC_CHUNKS:
        chunks = chunks[:MAX_DOC_CHUNKS]
        truncated = True
        logger.info("Document capped at %s chunks; rest skipped", MAX_DOC_CHUNKS)

    if not chunks:
        return {
            "articles": [],
            "meta": {
                "document_chunks": 0,
                "collection": settings.qdrant_laws_collection,
                "truncated": False,
            },
        }

    ze = ZeroEntropy(api_key=settings.zeroentropy_api_key)
    vectors = await asyncio.to_thread(_embed_all, ze, chunks)

    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_service_api_key or None,
        timeout=60.0,
    )
    collection = settings.qdrant_laws_collection

    def search_one(args: tuple[int, list[float], str]) -> list[tuple[Any, float, dict[str, Any], str]]:
        idx, vector, chunk_text = args
        flt = _language_filter(language)
        attempts: list[Optional[Filter]] = [flt, None] if flt else [None]
        for f in attempts:
            try:
                res = client.search(
                    collection_name=collection,
                    query_vector=vector,
                    query_filter=f,
                    limit=top_k_per_chunk,
                    with_payload=True,
                    with_vectors=False,
                )
                hits = [
                    (r.id, float(r.score), r.payload or {}, chunk_text)
                    for r in res
                ]
                if hits:
                    return hits
            except Exception as e:
                logger.warning("Qdrant search failed (chunk %s, filter=%s): %s", idx, f, e)
        return []

    tasks = [
        asyncio.to_thread(search_one, (i, vectors[i], chunks[i]))
        for i in range(len(chunks))
    ]
    nested = await asyncio.gather(*tasks)

    best: dict[Any, dict[str, Any]] = {}
    for group in nested:
        for point_id, score, payload, doc_chunk in group:
            prev = best.get(point_id)
            if prev is None or score > prev["score"]:
                best[point_id] = {
                    "score": score,
                    "payload": payload,
                    "doc_chunk": doc_chunk,
                }

    ordered = sorted(
        best.items(),
        key=lambda kv: kv[1]["score"],
        reverse=True,
    )[:max_results]

    articles = [
        _law_point_to_article(
            score=item["score"],
            payload=item["payload"],
            doc_chunk=item["doc_chunk"],
            point_id=pid,
        )
        for pid, item in ordered
    ]

    return {
        "articles": articles,
        "meta": {
            "document_chunks": len(chunks),
            "collection": collection,
            "truncated": truncated,
        },
    }
