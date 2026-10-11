"""LLM package: providers, prompt builder, grounded generation, workflows, and agentic graph."""

from collections.abc import AsyncIterator
from typing import Any, Protocol

from packages.llm.generation import GenerationResult, RAGGenerator, validate_citations
from packages.llm.graph import RAGGraph
from packages.llm.graph_state import GraphState
from packages.llm.prompt import build_rag_messages
from packages.llm.providers import (
    GroqProvider,
    OllamaProvider,
    OpenRouterProvider,
    ProviderError,
    build_provider,
    build_provider_from_settings,
)
from packages.llm.workflows import ComparisonWorkflow, NumericalWorkflow, TemporalWorkflow


class LLMProvider(Protocol):
    """Protocol for LLM providers (Groq, OpenRouter, Ollama)."""

    async def generate(
        self, messages: list[dict[str, str]], response_schema: dict[str, Any] | None = None
    ) -> dict[str, Any]: ...

    async def stream(self, messages: list[dict[str, str]]) -> AsyncIterator[str]: ...


__all__ = [
    "LLMProvider",
    "GenerationResult",
    "GraphState",
    "GroqProvider",
    "NumericalWorkflow",
    "OllamaProvider",
    "OpenRouterProvider",
    "ProviderError",
    "RAGGenerator",
    "RAGGraph",
    "ComparisonWorkflow",
    "TemporalWorkflow",
    "build_provider",
    "build_provider_from_settings",
    "build_rag_messages",
    "validate_citations",
]
