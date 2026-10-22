"""RAG generation service: retrieves evidence, calls LLM, validates citations.

Rule 12: LLM never receives documents the user cannot access.
Rule 12: Citation validation strips any chunk_id the LLM fabricated.
Rule 14: Provider errors are caught and re-raised as safe AppException-compatible errors.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from packages.llm.prompt import build_rag_messages
from packages.llm.providers import ProviderError, parse_json_content
from packages.retrieval.injection_filter import PromptInjectionFilter
from packages.retrieval.models import RetrievalResult

logger = logging.getLogger("enterprise_rag")


@dataclass
class GenerationResult:
    """Structured output from the RAG generation pipeline.

    Fields exposed to the API (Rule 6: minimum necessary data).
    CoT / internal state is never stored here.
    """

    answer: str
    citation_ids: list[str]
    grounded: bool
    abstained: bool
    query_type: str = "DIRECT"
    # token_usage kept server-side only; not returned in API response
    token_usage: dict = field(default_factory=dict)
    evidence: list[RetrievalResult] = field(default_factory=list)


class CitationValidationError(Exception):
    """Raised when citation validation produces a completely empty result that is unrecoverable."""


def validate_citations(
    claimed_ids: list[str],
    evidence: list[RetrievalResult],
) -> list[str]:
    """Strip any citation IDs the LLM fabricated.

    Returns only IDs that appear in the retrieved evidence set.
    Fabricated IDs are logged server-side (Rule 12).
    """
    valid_ids = {chunk.chunk_id for chunk in evidence}
    verified: list[str] = []
    fabricated: list[str] = []

    for cid in claimed_ids:
        if cid in valid_ids:
            verified.append(cid)
        else:
            fabricated.append(cid)

    if fabricated:
        logger.warning(
            "LLM fabricated citation IDs — stripped from response",
            extra={"extra": {"fabricated_count": len(fabricated)}},
        )

    return verified


class RAGGenerator:
    """Orchestrates: evidence → prompt → LLM → citation validation → GenerationResult.

    The provider is injected at construction time (not user-controlled).
    """

    def __init__(self, provider: object) -> None:
        self._provider = provider

    async def generate(
        self,
        question: str,
        evidence: list[RetrievalResult],
        query_type: str = "DIRECT",
        extra_system: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> GenerationResult:
        """Run grounded generation against validated evidence.

        Args:
            question: Sanitised user question.
            evidence: Access-controlled retrieved chunks.
            query_type: Classified query type for logging / response.
            extra_system: Optional extra system-prompt text for specialised workflows.
            conversation_history: Optional recent conversation turns.

        Returns:
            GenerationResult with validated citations only.
        """
        if not evidence:
            return GenerationResult(
                answer=(
                    "I was unable to find sufficient evidence in the available documents "
                    "to answer this question."
                ),
                citation_ids=[],
                grounded=False,
                abstained=True,
                query_type=query_type,
            )

        # Risk 1 mitigation: drop adversarial chunks before prompt assembly.
        injection_filter = PromptInjectionFilter()
        filter_result = injection_filter.filter(evidence)
        safe_evidence = filter_result.kept

        # If all chunks were dropped, abstain rather than expose adversarial content.
        if not safe_evidence:
            logger.warning(
                "All retrieved chunks were flagged for prompt injection — abstaining",
                extra={"extra": {"dropped_count": filter_result.dropped_count}},
            )
            return GenerationResult(
                answer=(
                    "I was unable to find sufficient trustworthy evidence in the available "
                    "documents to answer this question."
                ),
                citation_ids=[],
                grounded=False,
                abstained=True,
                query_type=query_type,
            )

        messages = build_rag_messages(
            question=question,
            evidence=safe_evidence,
            extra_system=extra_system,
            conversation_history=conversation_history,
        )

        try:
            raw = await self._provider.generate(messages=messages, response_schema={})
        except ProviderError as exc:
            logger.error(
                "LLM provider error during generation",
                extra={"extra": {"provider": exc.provider}},
            )
            # Re-raise as a typed error; the route handler converts to safe HTTP response
            raise

        content = raw.get("content", "")
        token_usage = raw.get("usage", {})

        parsed = parse_json_content(content)

        answer = str(parsed.get("answer", "")).strip()
        raw_citation_ids = parsed.get("citation_ids", [])
        grounded = bool(parsed.get("grounded", False))
        abstained = bool(parsed.get("abstained", False))

        if not answer:
            # This can happen when the LLM provider's content filter blocked the output
            # (e.g. finish_reason=content_filter) or when the model returned empty JSON
            answer = (
                "I'm sorry, but I was unable to generate a response for this question. "
                "This may be due to content filtering or insufficient evidence in the documents. "
                "Please try rephrasing your question."
            )
            abstained = True
            grounded = False

        # Validate citations — strip any IDs the LLM fabricated (Rule 12)
        if isinstance(raw_citation_ids, list):
            citation_ids = validate_citations(raw_citation_ids, evidence)
        else:
            citation_ids = []
            logger.warning("LLM returned non-list citation_ids; treating as empty")

        # If LLM claims grounded but all citations were fabricated, correct it
        if grounded and not citation_ids and not abstained:
            grounded = False
            logger.warning("LLM claimed grounded=true but all citation IDs were invalid")

        return GenerationResult(
            answer=answer,
            citation_ids=citation_ids,
            grounded=grounded,
            abstained=abstained,
            query_type=query_type,
            token_usage=token_usage,
        )
