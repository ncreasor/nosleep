"""Hybrid RAG system for Kazakhstan legal documents using Qdrant and ZeroEntropy."""

import asyncio
import logging
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, HasIdCondition, MatchValue
from rank_bm25 import BM25Okapi
import anthropic
from config import settings
from zeroentropy import ZeroEntropy

logger = logging.getLogger(__name__)


class LawsRAG:
    """Hybrid RAG using dense vectors (ZeroEntropy zembed-1), BM25 keyword search, and ZeRank reranking."""

    def __init__(self):
        self.qdrant = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_service_api_key or None)
        self.ze = ZeroEntropy(api_key=settings.zeroentropy_api_key)
        self.claude = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.collection_name = settings.qdrant_laws_collection
        self.bm25 = None
        self._corpus = None

    async def _build_bm25_index(self):
        """Build BM25 index from all documents in Qdrant."""
        if self.bm25 is not None:
            return

        try:
            # Scroll all points from Qdrant
            points, _ = self.qdrant.scroll(
                collection_name=self.collection_name,
                limit=10000,
                with_payload=True,
            )

            texts = [point.payload.get("text", "") for point in points]
            # Tokenize (simple whitespace + lowercase)
            tokenized = [text.lower().split() for text in texts]

            self.bm25 = BM25Okapi(tokenized)
            self._corpus = texts
            logger.info(f"BM25 index built with {len(texts)} documents")
        except Exception as e:
            logger.error(f"Failed to build BM25 index: {e}")
            raise

    async def search(
        self,
        query: str,
        is_active: Optional[bool] = None,
        sphere: Optional[str] = None,
        language: str = "rus",
        doc_kind: Optional[str] = None,
        top_k: int = 10,
        use_reranking: bool = True,
    ) -> list[dict]:
        """
        Hybrid search: dense (zembed-1) + sparse (BM25) + reranking (ZeRank).

        Args:
            query: User search query
            is_active: Filter by active/repealed status (True=active, False=repealed)
            sphere: Filter by sphere (labor, finance, civilian_rights)
            language: Language (rus, kaz)
            doc_kind: Document kind filter
            top_k: Number of results to return
            use_reranking: Whether to use ZeRank reranking

        Returns:
            List of search results with metadata
        """
        # Build BM25 index if needed
        if self.bm25 is None:
            await self._build_bm25_index()

        # Build Qdrant filter
        filter_conditions = [
            FieldCondition(key="language", match=MatchValue(value=language))
        ]
        if is_active is not None:
            filter_conditions.append(
                FieldCondition(key="is_active", match=MatchValue(value=is_active))
            )
        if sphere:
            filter_conditions.append(
                FieldCondition(key="sphere", match=MatchValue(value=sphere))
            )
        if doc_kind:
            filter_conditions.append(
                FieldCondition(key="doc_kind", match=MatchValue(value=doc_kind))
            )

        qdrant_filter = Filter(must=filter_conditions) if filter_conditions else None

        # 1. Dense search via zembed-1
        try:
            # Get embedding from ZeroEntropy
            embed_response = self.ze.embeddings.create(
                model="zembed-1",
                input=[query]
            )
            query_embedding = embed_response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to embed query: {e}")
            raise

        # Dense search in Qdrant
        dense_results = self.qdrant.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=qdrant_filter,
            limit=top_k * 3,  # Get more candidates for fusion
            with_payload=True,
            with_vectors=False,
        )

        # 2. BM25 keyword search on corpus
        bm25_scores = self.bm25.get_scores(query.lower().split())

        # Combine results: create a map of text -> combined score
        combined_scores = {}

        # Add dense search scores (normalized)
        for i, result in enumerate(dense_results):
            text = result.payload.get("text", "")
            score = 1.0 / (i + 1)  # Reciprocal rank fusion component
            combined_scores[result.id] = {
                "score": score,
                "result": result,
                "bm25_score": 0,
            }

        # Add BM25 scores (normalized)
        if self._corpus:
            for doc_id, bm25_score in enumerate(bm25_scores):
                if bm25_score > 0:
                    # Try to find matching point
                    for result in dense_results:
                        if result.payload.get("text", "") == self._corpus[doc_id]:
                            normalized_bm25 = bm25_score / (max(bm25_scores) + 1e-6)
                            if result.id not in combined_scores:
                                combined_scores[result.id] = {
                                    "score": 0,
                                    "result": result,
                                    "bm25_score": normalized_bm25,
                                }
                            else:
                                combined_scores[result.id]["bm25_score"] = normalized_bm25

        # Fuse scores (50% dense + 50% BM25)
        for point_id in combined_scores:
            score = combined_scores[point_id]["score"]
            bm25 = combined_scores[point_id]["bm25_score"]
            combined_scores[point_id]["fused_score"] = 0.5 * score + 0.5 * bm25

        # Sort by fused score
        sorted_results = sorted(
            combined_scores.values(),
            key=lambda x: x["fused_score"],
            reverse=True
        )

        # 3. Rerank with ZeRank if enabled
        if use_reranking and len(sorted_results) > 0:
            try:
                documents = [
                    r["result"].payload.get("text", "")[:512]
                    for r in sorted_results[:top_k * 2]
                ]

                if documents:
                    rerank_response = self.ze.reranking.create(
                        model="zerank-1",
                        query=query,
                        documents=documents
                    )

                    # Reorder by ZeRank scores
                    rerank_map = {i: r.relevance_score for i, r in enumerate(rerank_response.results)}
                    for i, result in enumerate(sorted_results[:top_k * 2]):
                        result["rerank_score"] = rerank_map.get(i, 0)

                    sorted_results = sorted(
                        sorted_results,
                        key=lambda x: x.get("rerank_score", 0),
                        reverse=True
                    )
            except Exception as e:
                logger.warning(f"ZeRank reranking failed, using fusion scores: {e}")

        # 4. Format results
        formatted_results = []
        for result in sorted_results[:top_k]:
            payload = result["result"].payload
            formatted_results.append({
                "id": result["result"].id,
                "title": payload.get("title", ""),
                "text": payload.get("text", "")[:500],  # Preview
                "url": payload.get("url", ""),
                "doc_type": payload.get("doc_type", ""),
                "date": payload.get("date", ""),
                "number": payload.get("number", ""),
                "authority": payload.get("authority", ""),
                "status": payload.get("status", ""),
                "is_active": payload.get("is_active", False),
                "sphere": payload.get("sphere", ""),
                "language": payload.get("language", ""),
                "doc_kind": payload.get("doc_kind", ""),
                "relevance_score": result.get("rerank_score", result.get("fused_score", 0)),
            })

        return formatted_results

    async def generate_answer(
        self,
        query: str,
        context: list[dict],
        language: str = "rus",
    ) -> str:
        """Generate an answer using Claude Haiku based on retrieved context."""

        # Format context for Claude
        context_text = "\n\n---\n\n".join([
            f"**{c['title']}** ({c['status']})\n"
            f"Date: {c['date']}\n"
            f"Authority: {c['authority']}\n"
            f"Active: {c['is_active']}\n\n"
            f"{c['text']}"
            for c in context
        ])

        system_prompt = """You are a legal assistant specialized in Kazakhstan law.
You provide accurate, helpful answers based on the legal documents provided.
When referencing laws, always mention if they are currently active or repealed.
Respond in Russian (if asked in Russian) or English (if asked in English)."""

        user_prompt = f"""Based on the following Kazakhstan legal documents, answer the question:

Question: {query}

Context from legal database:
{context_text}

Please provide a clear, accurate answer referencing the relevant laws.
Always note which laws are active (active: true) vs. repealed (active: false)."""

        try:
            response = self.claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                system=system_prompt,
            )

            return response.content[0].text
        except Exception as e:
            logger.error(f"Failed to generate answer with Claude: {e}")
            raise

    async def chat(
        self,
        query: str,
        is_active: Optional[bool] = None,
        sphere: Optional[str] = None,
        language: str = "rus",
        top_k: int = 5,
    ) -> dict:
        """End-to-end RAG: search + generate answer."""

        # Search
        results = await self.search(
            query=query,
            is_active=is_active,
            sphere=sphere,
            language=language,
            top_k=top_k,
            use_reranking=True,
        )

        if not results:
            return {
                "answer": "No relevant laws found in the database.",
                "results": [],
                "sources_count": 0,
            }

        # Generate answer
        answer = await self.generate_answer(query, results, language)

        return {
            "answer": answer,
            "results": results,
            "sources_count": len(results),
        }
