"""Evaluation package: Benchmark dataset, IR metrics, comparative runner, and CLI."""

from packages.evaluation.dataset import (
    EvaluationCase,
    QueryType,
    get_curated_benchmark_cases,
    load_benchmark_dataset,
    save_benchmark_dataset,
)
from packages.evaluation.generation_eval import (
    CaseEvaluationResult,
    GenerationEvaluationRunner,
    PipelineEvaluationSummary,
)
from packages.evaluation.metrics import (
    abstention_correctness,
    answer_relevance,
    citation_accuracy,
    citation_completeness,
    dcg_at_k,
    groundedness,
    mrr,
    ndcg_at_k,
    recall_at_k,
)
from packages.evaluation.runner import BenchmarkRunner

__all__ = [
    "BenchmarkRunner",
    "CaseEvaluationResult",
    "EvaluationCase",
    "GenerationEvaluationRunner",
    "PipelineEvaluationSummary",
    "QueryType",
    "abstention_correctness",
    "answer_relevance",
    "citation_accuracy",
    "citation_completeness",
    "dcg_at_k",
    "get_curated_benchmark_cases",
    "groundedness",
    "load_benchmark_dataset",
    "mrr",
    "ndcg_at_k",
    "recall_at_k",
    "save_benchmark_dataset",
]
