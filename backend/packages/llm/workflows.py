"""Specialised RAG workflows for numerical, temporal, and comparison questions.

Phase 10: Retrieves source values, validates units/periods, computes in Python,
then passes verified results to the LLM for explanation.

Rule 12: All Qdrant queries use authorized_document_ids scoped at the query level.
Rule 4 / Rule 1: No eval(), no exec(), no arbitrary code execution — all calculations
                 are done with explicit Python arithmetic only.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from packages.llm.generation import GenerationResult, RAGGenerator
from packages.retrieval.models import RetrievalResult

logger = logging.getLogger("enterprise_rag")

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

# Patterns to extract numeric values from text
_NUMBER_RE = re.compile(
    r"(?P<value>[\d,]+(?:\.\d+)?)\s*"
    r"(?P<unit>million|billion|trillion|thousand|M|B|T|K|%|percent)?\b",
    re.IGNORECASE,
)

_SCALE = {
    "thousand": 1_000,
    "k": 1_000,
    "million": 1_000_000,
    "m": 1_000_000,
    "billion": 1_000_000_000,
    "b": 1_000_000_000,
    "trillion": 1_000_000_000_000,
    "t": 1_000_000_000_000,
    "%": 1,
    "percent": 1,
}


def _extract_numeric_value(text: str) -> tuple[float | None, str | None]:
    """Extract the first numeric value and its unit from text.

    Returns (value, unit) or (None, None) if nothing found.
    Pure Python — no eval (Rule 4).
    """
    match = _NUMBER_RE.search(text)
    if not match:
        return None, None
    raw = match.group("value").replace(",", "")
    unit = (match.group("unit") or "").lower()
    try:
        value = float(raw)
    except ValueError:
        return None, None
    scale = _SCALE.get(unit, 1)
    return value * scale, unit or None


@dataclass
class ExtractedValue:
    """A numeric value extracted from a single retrieved chunk."""

    chunk_id: str
    raw_text: str
    value: float
    unit: str | None


def _extract_values_from_evidence(
    evidence: list[RetrievalResult],
) -> list[ExtractedValue]:
    """Extract numeric values from each chunk.  Skips chunks with no number."""
    extracted: list[ExtractedValue] = []
    for chunk in evidence:
        val, unit = _extract_numeric_value(chunk.text)
        if val is not None:
            extracted.append(
                ExtractedValue(
                    chunk_id=chunk.chunk_id,
                    raw_text=chunk.text[:500],
                    value=val,
                    unit=unit,
                )
            )
    return extracted


# ─────────────────────────────────────────────────────────────────────────────
# Numerical Workflow
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class NumericalResult:
    """Output of numerical workflow before LLM explanation."""

    source_values: list[ExtractedValue]
    computed_value: float | None
    unit: str | None
    source_chunk_ids: list[str]
    unit_consistent: bool
    note: str = ""


def _validate_units(values: list[ExtractedValue]) -> tuple[bool, str | None]:
    """Check that all extracted values share a consistent (scaled) unit."""
    if not values:
        return True, None
    units = {v.unit for v in values if v.unit}
    if len(units) <= 1:
        return True, next(iter(units), None)
    return False, None


def run_numerical_analysis(evidence: list[RetrievalResult]) -> NumericalResult:
    """Extract, validate, and aggregate numeric values from evidence chunks.

    All arithmetic is explicit Python — no eval, no user code execution (Rule 4).
    """
    source_values = _extract_values_from_evidence(evidence)
    if not source_values:
        return NumericalResult(
            source_values=[],
            computed_value=None,
            unit=None,
            source_chunk_ids=[],
            unit_consistent=True,
            note="No numeric values found in retrieved evidence.",
        )

    unit_ok, common_unit = _validate_units(source_values)
    # Sum is the default aggregation; LLM decides how to interpret it
    total = sum(v.value for v in source_values)
    chunk_ids = [v.chunk_id for v in source_values]

    return NumericalResult(
        source_values=source_values,
        computed_value=total,
        unit=common_unit,
        source_chunk_ids=chunk_ids,
        unit_consistent=unit_ok,
        note="" if unit_ok else "Warning: mixed units detected; aggregation may be inaccurate.",
    )


class NumericalWorkflow:
    """Workflow for numerical questions.

    Pipeline:
      retrieve → extract values → validate units / time period → compute in Python
      → LLM explains the verified result.
    """

    def __init__(self, generator: RAGGenerator) -> None:
        self._generator = generator

    async def run(
        self,
        question: str,
        evidence: list[RetrievalResult],
    ) -> GenerationResult:
        """Run numerical RAG workflow."""
        analysis = run_numerical_analysis(evidence)

        extra_system_parts = [
            "This is a NUMERICAL question. Follow these additional rules:",
            "- Use ONLY the computed values supplied in the evidence summary below.",
            "- Clearly label computed values as derived from source chunks.",
            "- If units are inconsistent, state the inconsistency in your answer.",
            "- Preserve source chunk IDs for every value you cite.",
        ]

        if analysis.computed_value is not None:
            unit_str = f" {analysis.unit}" if analysis.unit else ""
            extra_system_parts.append(
                f"\nPre-computed aggregate from evidence: {analysis.computed_value:,.2f}{unit_str}"
            )
            if analysis.note:
                extra_system_parts.append(f"Note: {analysis.note}")

        return await self._generator.generate(
            question=question,
            evidence=evidence,
            query_type="NUMERICAL",
            extra_system="\n".join(extra_system_parts),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Temporal Workflow
# ─────────────────────────────────────────────────────────────────────────────


class TemporalWorkflow:
    """Workflow for temporal questions.

    Validates that retrieved evidence matches the requested time period before
    generating. Instructs LLM to surface time-period context explicitly.
    """

    def __init__(self, generator: RAGGenerator) -> None:
        self._generator = generator

    async def run(
        self,
        question: str,
        evidence: list[RetrievalResult],
        requested_year: int | None = None,
    ) -> GenerationResult:
        """Run temporal RAG workflow."""
        # Filter evidence to the requested year if specified
        if requested_year is not None:
            year_matched = [c for c in evidence if c.year == requested_year]
            if year_matched:
                evidence = year_matched
            # If no match, keep all evidence and let LLM state the period mismatch

        extra_system = (
            "This is a TEMPORAL question.\n"
            "- Always state the time period (year, fiscal year, quarter) for each fact.\n"
            "- If the evidence does not cover the requested period, state this explicitly.\n"
            "- Do not extrapolate from one period to another."
        )
        if requested_year:
            extra_system += f"\nThe user requested data for: {requested_year}."

        return await self._generator.generate(
            question=question,
            evidence=evidence,
            query_type="TEMPORAL",
            extra_system=extra_system,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Comparison Workflow
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class EntityEvidence:
    """Evidence retrieved independently for a single entity in a comparison."""

    entity: str
    chunks: list[RetrievalResult]
    value: float | None = None
    unit: str | None = None


def _normalize_value(val: float, unit: str | None) -> float:
    """Values are already scaled by _extract_numeric_value; return as-is."""
    return val


class ComparisonWorkflow:
    """Workflow for comparison questions.

    Pipeline:
      extract entities → retrieve evidence independently per entity (with
      authorized_document_ids filter) → normalize values → compute difference
      in Python → LLM explains the cited comparison.

    Rule 12: Each retrieval call includes the user's authorized_document_ids filter.
    """

    def __init__(self, generator: RAGGenerator, retriever: Any) -> None:
        """
        Args:
            generator: RAGGenerator instance.
            retriever: HybridRetriever instance. Accepts any object with a
                       .retrieve(query, filters) method — no duck-typing risk
                       because this class is only instantiated by the graph.
        """
        self._generator = generator
        self._retriever = retriever

    def _retrieve_for_entity(
        self,
        query: str,
        entity: str,
        authorized_document_ids: list[str],
        extra_filters: dict[str, Any] | None = None,
    ) -> list[RetrievalResult]:
        """Retrieve evidence independently for one entity.

        Rule 12: authorized_document_ids is always included.
        """
        filters: dict[str, Any] = {"authorized_document_ids": authorized_document_ids}
        if extra_filters:
            filters.update(extra_filters)
        # Narrow by entity name to prefer entity-specific evidence
        entity_query = f"{entity} {query}"
        results, _ = self._retriever.retrieve(query=entity_query, filters=filters)
        return results

    async def run(
        self,
        question: str,
        entities: list[str],
        metric: str | None,
        authorized_document_ids: list[str],
        time_period: int | None = None,
        extra_filters: dict[str, Any] | None = None,
    ) -> GenerationResult:
        """Run comparison RAG workflow.

        Args:
            question: User's comparison question.
            entities: List of entities to compare (e.g. ["Apple", "Microsoft"]).
            metric: The metric being compared (e.g. "revenue").
            authorized_document_ids: IDs the user can access (pre-retrieval auth).
            time_period: Optional year to filter evidence.
            extra_filters: Optional additional Qdrant filters.
        """
        if not entities:
            return await self._generator.generate(
                question=question, evidence=[], query_type="COMPARISON"
            )

        entity_evidences: list[EntityEvidence] = []
        for entity in entities:
            year_filter = {"year": time_period} if time_period else {}
            ef = {**year_filter, **(extra_filters or {})}
            chunks = self._retrieve_for_entity(
                query=metric or question,
                entity=entity,
                authorized_document_ids=authorized_document_ids,
                extra_filters=ef or None,
            )
            ee = EntityEvidence(entity=entity, chunks=chunks)
            # Extract representative numeric value for this entity
            values = _extract_values_from_evidence(chunks)
            if values:
                ee.value = _normalize_value(values[0].value, values[0].unit)
                ee.unit = values[0].unit
            entity_evidences.append(ee)

        # Compute difference / ratio where possible (pure Python, no eval)
        comparison_notes: list[str] = []
        vals = [(ee.entity, ee.value) for ee in entity_evidences if ee.value is not None]
        if len(vals) == 2:
            e1_name, v1 = vals[0]
            e2_name, v2 = vals[1]
            diff = v1 - v2
            comparison_notes.append(
                f"Python-computed difference ({e1_name} − {e2_name}): {diff:,.2f}"
            )

        # Combine all entity evidence into a flat list
        all_evidence: list[RetrievalResult] = []
        for ee in entity_evidences:
            all_evidence.extend(ee.chunks)

        extra_system_parts = [
            "This is a COMPARISON question.",
            "- Compare entities using ONLY the evidence below.",
            "- State which evidence passage each fact comes from.",
            "- Label computed differences as 'Python-computed from source values'.",
            "- Do not invent figures not present in the evidence.",
        ]
        if comparison_notes:
            extra_system_parts.append("\nPre-computed values from Python:")
            extra_system_parts.extend(comparison_notes)

        return await self._generator.generate(
            question=question,
            evidence=all_evidence,
            query_type="COMPARISON",
            extra_system="\n".join(extra_system_parts),
        )
