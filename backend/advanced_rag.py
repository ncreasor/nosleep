import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from sentence_transformers import CrossEncoder
from rank_bm25 import BM25Okapi
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import numpy as np

from config import settings
from llm_json import parse_llm_json

logger = logging.getLogger(__name__)
openai_client = OpenAI(api_key=settings.openai_api_key)


@dataclass
class RAGResult:
    """Result from RAG pipeline with all metadata."""
    answer: str
    sources: list[dict]
    confidence: float
    query_variants: list[str]


class QueryExpansion:
    """Expand user query into multiple semantic variants."""

    def __init__(self):
        self.client = openai_client

    def expand_query(self, query: str, num_variants: int = 4) -> list[str]:
        """Generate query variants using LLM."""
        prompt = f"""Generate {num_variants} semantic variations of this legal/regulatory query.
        Return ONLY the variations as a JSON array of strings, no other text.

        Original query: "{query}"

        Variations should:
        - Use synonyms (e.g., "налоги" -> "налогообложение", "сбор")
        - Expand abbreviations
        - Use both formal and colloquial terms
        - Include related concepts

        Return format: ["variant1", "variant2", "variant3", "variant4"]
        """

        try:
            response = self.client.messages.create(
                model=settings.openai_model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text
            variants = parse_llm_json(content)
            return [query] + variants[:num_variants]
        except Exception as e:
            logger.error(f"Query expansion failed: {e}")
            return [query]


class HyDE:
    """Hypothetical Document Embeddings - generate hypothetical docs matching query."""

    def __init__(self):
        self.client = openai_client

    def generate_hypothetical_doc(self, query: str) -> str:
        """Generate a hypothetical legal document that would answer the query."""
        prompt = f"""You are a legal document expert. Based on this query, write a brief hypothetical legal document snippet (2-3 sentences) that would answer it. Write in Kazakh or Russian as appropriate.

        Query: "{query}"

        Write a realistic legal document excerpt that would contain the answer. Be concise."""

        try:
            response = self.client.messages.create(
                model=settings.openai_model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"HyDE generation failed: {e}")
            return query


class HybridSearch:
    """Combine BM25 (lexical) and semantic search."""

    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant = qdrant_client
        self.bm25 = None
        self.documents = []  # Store for BM25
        self.doc_id_map = {}

    def index_documents(self, documents: list[dict]):
        """Index documents for BM25 (called after fetching from DB)."""
        self.documents = documents
        tokenized_docs = [
            doc["content"].lower().split() for doc in documents
        ]
        self.bm25 = BM25Okapi(tokenized_docs)
        self.doc_id_map = {i: doc["id"] for i, doc in enumerate(documents)}

    def bm25_search(self, query: str, top_k: int = 10) -> list[dict]:
        """Full-text search using BM25."""
        if not self.bm25:
            return []

        query_tokens = query.lower().split()
        scores = self.bm25.get_scores(query_tokens)
        top_indices = np.argsort(scores)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append(
                    {
                        "id": self.doc_id_map[idx],
                        "content": self.documents[idx]["content"],
                        "score": float(scores[idx]),
                        "source": "bm25",
                    }
                )
        return results

    def semantic_search(
        self, embedding: list[float], top_k: int = 10, collection: str = None
    ) -> list[dict]:
        """Vector similarity search."""
        if collection is None:
            collection = settings.qdrant_collection

        try:
            results = self.qdrant.search(
                collection_name=collection,
                query_vector=embedding,
                limit=top_k,
                with_payload=True,
            )
            return [
                {
                    "id": hit.id,
                    "content": hit.payload.get("content", ""),
                    "score": hit.score,
                    "source": "semantic",
                }
                for hit in results
            ]
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def hybrid_search(
        self,
        query: str,
        embedding: list[float],
        documents: list[dict],
        top_k: int = 10,
    ) -> list[dict]:
        """Combine BM25 and semantic results."""
        # Index documents for BM25
        self.index_documents(documents)

        # Run both searches in parallel
        bm25_results = self.bm25_search(query, top_k)
        semantic_results = self.semantic_search(embedding, top_k)

        # Merge and deduplicate
        merged = {}
        for result in bm25_results:
            doc_id = result["id"]
            merged[doc_id] = {
                "id": doc_id,
                "content": result["content"],
                "bm25_score": result["score"],
                "semantic_score": 0,
                "source": "bm25",
            }

        for result in semantic_results:
            doc_id = result["id"]
            if doc_id in merged:
                merged[doc_id]["semantic_score"] = result["score"]
                merged[doc_id]["source"] = "hybrid"
            else:
                merged[doc_id] = {
                    "id": doc_id,
                    "content": result["content"],
                    "bm25_score": 0,
                    "semantic_score": result["score"],
                    "source": "semantic",
                }

        # Normalize and combine scores
        for doc_id in merged:
            bm25 = merged[doc_id]["bm25_score"]
            semantic = merged[doc_id]["semantic_score"]
            # Weighted average: 40% BM25, 60% semantic
            merged[doc_id]["combined_score"] = 0.4 * (
                bm25 / max(10, max([r["bm25_score"] for r in bm25_results] or [1]))
            ) + 0.6 * semantic

        # Sort by combined score
        sorted_results = sorted(
            merged.values(), key=lambda x: x["combined_score"], reverse=True
        )
        return sorted_results[:top_k]


class CrossEncoderReranker:
    """Use cross-encoder to rerank results by relevance."""

    def __init__(self, model_name: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384"):
        try:
            self.model = CrossEncoder(model_name)
        except Exception as e:
            logger.warning(f"Failed to load cross-encoder: {e}. Using fallback.")
            self.model = None

    def rerank(
        self, query: str, documents: list[dict], top_k: int = 5
    ) -> list[dict]:
        """Rerank documents by relevance to query."""
        if not documents or not self.model:
            return documents[:top_k]

        try:
            # Prepare pairs for cross-encoder
            pairs = [
                [query, doc.get("content", "")[:512]] for doc in documents
            ]

            # Score all pairs
            scores = self.model.predict(pairs)

            # Add scores and sort
            for doc, score in zip(documents, scores):
                doc["rerank_score"] = float(score)

            sorted_docs = sorted(
                documents, key=lambda x: x.get("rerank_score", 0), reverse=True
            )
            return sorted_docs[:top_k]
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return documents[:top_k]


class ContextCompression:
    """Extract only relevant passages from documents."""

    @staticmethod
    def compress_context(documents: list[dict], query: str, max_chars: int = 3000) -> str:
        """Extract relevant passages and compress into concise context."""
        context_parts = []
        total_chars = 0

        for doc in documents:
            content = doc.get("content", "")
            if not content:
                continue

            # Split into sentences
            sentences = content.split(". ")
            relevant_sentences = []

            # Simple relevance: include sentences with query keywords
            query_terms = set(query.lower().split())
            for sentence in sentences:
                sentence_terms = set(sentence.lower().split())
                if sentence_terms & query_terms:  # Has common terms
                    relevant_sentences.append(sentence)

            passage = ". ".join(relevant_sentences[:3])  # Take top 3 relevant sentences
            if passage and total_chars < max_chars:
                context_parts.append(
                    f"[{doc.get('title', 'Document')}]\n{passage}"
                )
                total_chars += len(passage)

        return "\n\n".join(context_parts)


class AdvancedRAG:
    """Complete RAG pipeline with expansion, HyDE, hybrid search, and reranking."""

    def __init__(self, qdrant_client: QdrantClient):
        self.qdrant = qdrant_client
        self.query_expansion = QueryExpansion()
        self.hyde = HyDE()
        self.hybrid = HybridSearch(qdrant_client)
        self.reranker = CrossEncoderReranker()
        self.compressor = ContextCompression()
        self.client = openai_client

    def process_query(
        self, query: str, embedding: list[float], documents: list[dict]
    ) -> RAGResult:
        """Run complete RAG pipeline."""

        # Step 1: Expand query
        query_variants = self.query_expansion.expand_query(query, num_variants=3)
        logger.info(f"Query variants: {query_variants}")

        # Step 2: HyDE - generate hypothetical document
        hypothetical = self.hyde.generate_hypothetical_doc(query)
        logger.info(f"Hypothetical doc: {hypothetical}")

        # Step 3: Hybrid search with original query and variants
        all_results = {}
        for variant in query_variants:
            # Get embedding for variant (reuse for original, generate for others)
            if variant == query:
                variant_embedding = embedding
            else:
                variant_embedding = self._get_embedding(variant)

            results = self.hybrid.hybrid_search(
                variant, variant_embedding, documents, top_k=15
            )
            for result in results:
                doc_id = result["id"]
                if doc_id not in all_results:
                    all_results[doc_id] = result
                else:
                    # Average scores from multiple query variants
                    all_results[doc_id]["combined_score"] = (
                        all_results[doc_id]["combined_score"]
                        + result["combined_score"]
                    ) / 2

        # Step 4: Rerank top results
        top_results = sorted(
            all_results.values(),
            key=lambda x: x["combined_score"],
            reverse=True,
        )[:20]
        reranked = self.reranker.rerank(query, top_results, top_k=10)

        # Step 5: Compress context
        context = self.compressor.compress_context(reranked, query)

        # Step 6: Calculate confidence
        confidence = (
            reranked[0].get("rerank_score", 0)
            if reranked
            else 0
        )

        return RAGResult(
            answer=context,
            sources=[
                {"title": doc.get("title", f"Doc {i}"), "score": doc.get("rerank_score", 0)}
                for i, doc in enumerate(reranked[:5])
            ],
            confidence=min(1.0, float(confidence)),
            query_variants=query_variants,
        )

    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding for text."""
        try:
            response = self.client.embeddings.create(
                model=settings.openai_embed_model,
                input=text[:8191],
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return [0] * 1536
