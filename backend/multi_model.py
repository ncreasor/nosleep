import asyncio
import logging
from typing import Optional
from dataclasses import dataclass
from anthropic import Anthropic
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    """Response from a single model."""
    model: str
    content: str
    confidence: float = 1.0
    error: Optional[str] = None


@dataclass
class EnsembleResult:
    """Result from ensemble of models."""
    answer: str
    model_responses: list[ModelResponse]
    consensus_score: float  # 0-1, how much models agree
    recommended_model: str
    confidence: float


class MultiModelEnsemble:
    """Use multiple LLMs for consensus-based answers."""

    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key)
        # Note: Anthropic API key should be in env
        self.anthropic_client = None
        try:
            import os
            if os.getenv("ANTHROPIC_API_KEY"):
                self.anthropic_client = Anthropic()
        except Exception as e:
            logger.warning(f"Anthropic client not available: {e}")

    async def query_gpt(
        self, system: str, messages: list[dict]
    ) -> ModelResponse:
        """Query OpenAI GPT model."""
        try:
            response = self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[{"role": "system", "content": system}] + messages,
                temperature=0.7,
                max_tokens=1000,
            )
            content = response.choices[0].message.content
            return ModelResponse(
                model="gpt-4o-mini",
                content=content,
                confidence=0.9,
            )
        except Exception as e:
            logger.error(f"GPT query error: {e}")
            return ModelResponse(
                model="gpt-4o-mini",
                content="",
                error=str(e),
                confidence=0,
            )

    async def query_claude(
        self, system: str, messages: list[dict]
    ) -> ModelResponse:
        """Query Claude model."""
        if not self.anthropic_client:
            return ModelResponse(
                model="claude-3-haiku",
                content="",
                error="Anthropic client not configured",
                confidence=0,
            )

        try:
            response = self.anthropic_client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=1000,
                system=system,
                messages=messages,
            )
            content = response.content[0].text
            return ModelResponse(
                model="claude-3-haiku",
                content=content,
                confidence=0.85,
            )
        except Exception as e:
            logger.error(f"Claude query error: {e}")
            return ModelResponse(
                model="claude-3-haiku",
                content="",
                error=str(e),
                confidence=0,
            )

    def _calculate_consensus(self, responses: list[ModelResponse]) -> float:
        """Calculate how much responses agree (0-1)."""
        if len(responses) < 2:
            return 1.0

        successful = [r for r in responses if r.content and not r.error]
        if len(successful) < 2:
            return 0.0

        # Simple similarity metric: check if responses have similar length and keywords
        # In production, would use semantic similarity (embedding distance)
        contents = [r.content.lower() for r in successful]

        # Extract key words from first response
        words_1 = set(contents[0].split()[:20])

        overlaps = []
        for content in contents[1:]:
            words_n = set(content.split()[:20])
            overlap = len(words_1 & words_n) / max(len(words_1), len(words_n), 1)
            overlaps.append(overlap)

        if overlaps:
            return sum(overlaps) / len(overlaps)
        return 0.5

    def _select_best_response(
        self, responses: list[ModelResponse]
    ) -> ModelResponse:
        """Select best response based on confidence and error rates."""
        successful = [r for r in responses if r.content and not r.error]

        if not successful:
            return ModelResponse(
                model="ensemble",
                content="All models failed to generate response",
                error="All models failed",
                confidence=0,
            )

        # Sort by confidence and select highest
        return max(successful, key=lambda r: r.confidence)

    async def query_ensemble(
        self, system: str, messages: list[dict]
    ) -> EnsembleResult:
        """Query multiple models and combine results."""

        # Run all models in parallel
        responses = await asyncio.gather(
            self.query_gpt(system, messages),
            self.query_claude(system, messages),
        )

        # Calculate consensus
        consensus = self._calculate_consensus(responses)

        # Select best response
        best = self._select_best_response(responses)

        # Determine confidence based on consensus and model confidence
        confidence = min(1.0, consensus * 0.5 + best.confidence * 0.5)

        return EnsembleResult(
            answer=best.content,
            model_responses=responses,
            consensus_score=consensus,
            recommended_model=best.model,
            confidence=confidence,
        )

    @staticmethod
    def format_ensemble_response(result: EnsembleResult) -> dict:
        """Format ensemble result for API response."""
        return {
            "content": result.answer,
            "model": result.recommended_model,
            "ensemble": {
                "consensus_score": result.consensus_score,
                "confidence": result.confidence,
                "models_used": [r.model for r in result.model_responses if r.content],
                "agreement": "high" if result.consensus_score > 0.7 else "medium" if result.consensus_score > 0.4 else "low",
            },
            "model_details": [
                {
                    "model": r.model,
                    "confidence": r.confidence,
                    "error": r.error,
                }
                for r in result.model_responses
            ],
        }
