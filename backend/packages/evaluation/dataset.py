"""Evaluation benchmark dataset format, schema, and loader."""
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

QueryType = Literal[
    "direct_lookup",
    "temporal",
    "comparison",
    "numerical",
    "legal",
    "cross_document",
    "unanswerable",
]

_DEFAULT_DATASET_FILE = Path(__file__).parent / "benchmark_dataset.json"


class EvaluationCase(BaseModel):
    """A single evaluation benchmark test case."""

    id: str
    question: str
    query_type: QueryType
    expected_chunk_ids: list[str] = Field(default_factory=list)
    relevance_grades: dict[str, int] = Field(default_factory=dict)
    expected_answer: str | None = None
    metadata_constraints: dict[str, Any] = Field(default_factory=dict)


def get_curated_benchmark_cases() -> list[EvaluationCase]:
    """Return the curated benchmark dataset of 110 cases across 7 categories."""
    if _DEFAULT_DATASET_FILE.exists():
        return load_benchmark_dataset(_DEFAULT_DATASET_FILE)

    # Minimal fallback in case JSON file is missing
    return [
        EvaluationCase(
            id="dl-01",
            question="What is the CIK number of Apple Inc.?",
            query_type="direct_lookup",
            expected_chunk_ids=["apple-2024-sec-cik"],
            relevance_grades={"apple-2024-sec-cik": 3},
            expected_answer="0000320193",
            metadata_constraints={"company": "Apple Inc.", "year": 2024},
        )
    ]


def load_benchmark_dataset(file_path: Path | None = None) -> list[EvaluationCase]:
    """Load benchmark dataset from JSON file or return built-in curated cases."""
    path = file_path or _DEFAULT_DATASET_FILE
    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return [EvaluationCase.model_validate(item) for item in data]
    return get_curated_benchmark_cases()


def save_benchmark_dataset(cases: list[EvaluationCase], file_path: Path) -> None:
    """Save benchmark cases to a JSON file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump([c.model_dump() for c in cases], f, indent=2)
