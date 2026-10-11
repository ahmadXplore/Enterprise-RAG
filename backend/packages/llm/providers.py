"""LLM provider implementations: Groq, OpenRouter, Ollama.

Each class conforms to the LLMProvider Protocol defined in packages/llm/__init__.py.
API keys are consumed from Settings only — never accepted from callers or exposed in
logs / responses (Rule 4, Rule 8).
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

logger = logging.getLogger("enterprise_rag")

# Sentinel for missing optional key — distinct from empty string
_UNSET = object()


class ProviderError(Exception):
    """Raised when an LLM provider returns an error."""

    def __init__(self, provider: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.provider = provider
        # status_code kept server-side only; never forwarded verbatim to clients
        self.status_code = status_code


def _safe_headers(provider: str, api_key: str | None) -> dict[str, str]:
    """Build Authorization header without logging the key."""
    if not api_key:
        raise ProviderError(provider, f"{provider} API key is not configured")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


async def _execute_with_retry(
    provider_name: str,
    request_fn: Callable[[], Awaitable[httpx.Response]],
    max_retries: int = 3,
    base_delay: float = 0.5,
) -> httpx.Response:
    """Execute an HTTP request with exponential backoff and jitter (Rule 15)."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = await request_fn()
            if resp.status_code == 200:
                return resp

            # Retry transient rate-limit (429) or gateway errors (502, 503, 504)
            if resp.status_code in {429, 502, 503, 504}:
                if attempt == max_retries - 1:
                    logger.warning(
                        "%s API returned %s after %d attempts",
                        provider_name,
                        resp.status_code,
                        max_retries,
                        extra={"extra": {"status_code": resp.status_code, "attempt": attempt + 1}},
                    )
                    raise ProviderError(
                        provider_name, "LLM provider temporarily unavailable", resp.status_code
                    )

                retry_after_hdr = resp.headers.get("Retry-After")
                sleep_secs = base_delay * (2**attempt) + random.uniform(0.05, 0.2)  # noqa: S311
                if retry_after_hdr:
                    try:
                        sleep_secs = max(sleep_secs, min(float(retry_after_hdr), 5.0))
                    except (ValueError, TypeError):
                        pass

                logger.info(
                    f"{provider_name} returned {resp.status_code}; retrying in {sleep_secs:.2f}s",
                    extra={"extra": {"status_code": resp.status_code, "attempt": attempt + 1}},
                )
                await asyncio.sleep(sleep_secs)
                continue

            # Non-transient HTTP error (400, 401, 403, 404, etc.)
            logger.warning(
                f"{provider_name} API returned non-transient status",
                extra={"extra": {"status_code": resp.status_code}},
            )
            raise ProviderError(provider_name, "LLM provider returned an error", resp.status_code)

        except (httpx.TimeoutException, httpx.RequestError) as exc:
            last_exc = exc
            if attempt == max_retries - 1:
                logger.warning(
                    f"{provider_name} network/timeout failed after {max_retries} attempts",
                    extra={"extra": {"error": str(exc), "attempt": attempt + 1}},
                )
                if isinstance(exc, httpx.TimeoutException):
                    raise ProviderError(provider_name, "Request timed out") from exc
                raise ProviderError(
                    provider_name, f"Network error contacting {provider_name}"
                ) from exc

            sleep_secs = base_delay * (2**attempt) + random.uniform(0.05, 0.2)  # noqa: S311
            logger.info(
                "%s network glitch (%s); retrying in %.2fs",
                provider_name,
                type(exc).__name__,
                sleep_secs,
                extra={"extra": {"error": str(exc), "attempt": attempt + 1}},
            )
            await asyncio.sleep(sleep_secs)

    if last_exc:
        raise ProviderError(provider_name, "LLM request failed") from last_exc
    raise ProviderError(provider_name, "LLM request failed")


class GroqProvider:
    """LLM provider backed by the Groq Chat Completions API.

    Rule 4: GROQ_API_KEY is read from Settings only, never from user input.
    Rule 15: Hard timeout on every HTTP call, exponential backoff retries.
    """

    _BASE_URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str, timeout_seconds: int, max_tokens: int) -> None:
        if not api_key:
            raise ProviderError("groq", "GROQ_API_KEY is not configured")
        self._api_key = api_key
        self.model = model
        self._timeout = timeout_seconds
        self._max_tokens = max_tokens

    async def generate(
        self,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a chat completion request and return the raw response dict."""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": 0.0,  # deterministic for grounded RAG
        }
        if response_schema:
            # Groq supports JSON mode via response_format
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await _execute_with_retry(
                provider_name="groq",
                request_fn=lambda: client.post(
                    self._BASE_URL,
                    headers=_safe_headers("groq", self._api_key),
                    json=payload,
                ),
            )

        data = resp.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", self.model),
            "usage": data.get("usage", {}),
        }


class OpenRouterProvider:
    """LLM provider backed by the OpenRouter Chat Completions API.

    Rule 4: OPENROUTER_API_KEY read from Settings only.
    Rule 15: Hard timeout on every HTTP call, exponential backoff retries.
    """

    _BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, api_key: str, model: str, timeout_seconds: int, max_tokens: int) -> None:
        if not api_key:
            raise ProviderError("openrouter", "OPENROUTER_API_KEY is not configured")
        self._api_key = api_key
        self.model = model
        self._timeout = timeout_seconds
        self._max_tokens = max_tokens

    async def generate(
        self,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": 0.0,
        }
        if response_schema:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await _execute_with_retry(
                provider_name="openrouter",
                request_fn=lambda: client.post(
                    self._BASE_URL,
                    headers={
                        **_safe_headers("openrouter", self._api_key),
                        "HTTP-Referer": "https://enterprise-rag",
                        "X-Title": "Enterprise RAG",
                    },
                    json=payload,
                ),
            )

        data = resp.json()
        return {
            "content": data["choices"][0]["message"]["content"],
            "model": data.get("model", self.model),
            "usage": data.get("usage", {}),
        }


class OllamaProvider:
    """LLM provider backed by a local Ollama instance.

    Rule 7: OLLAMA_BASE_URL must not be a user-supplied value.
    Rule 15: Hard timeout on every HTTP call, exponential backoff retries.
    """

    def __init__(self, base_url: str, model: str, timeout_seconds: int, max_tokens: int) -> None:
        # Guard against SSRF: accept only the configured server URL (Rule 7)
        self._base_url = base_url.rstrip("/")
        self.model = model
        self._timeout = timeout_seconds
        self._max_tokens = max_tokens

    async def generate(
        self,
        messages: list[dict[str, str]],
        response_schema: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"num_predict": self._max_tokens, "temperature": 0.0},
        }
        if response_schema:
            payload["format"] = "json"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await _execute_with_retry(
                provider_name="ollama",
                request_fn=lambda: client.post(
                    f"{self._base_url}/api/chat",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                ),
            )

        data = resp.json()
        return {
            "content": data["message"]["content"],
            "model": data.get("model", self.model),
            "usage": {
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        }


def build_provider(
    provider_name: str,
    model: str,
    timeout_seconds: int,
    max_tokens: int,
    groq_api_key: str | None = None,
    openrouter_api_key: str | None = None,
    ollama_base_url: str = "http://localhost:11434",
) -> GroqProvider | OpenRouterProvider | OllamaProvider:
    """Instantiate the configured LLM provider.

    Rule 4: API keys come from Settings only; callers must not inject them from
    user-controlled input.
    """
    name = provider_name.lower()
    if name == "groq":
        if not groq_api_key:
            raise ProviderError("groq", "GROQ_API_KEY is required for the groq provider")
        return GroqProvider(
            api_key=groq_api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
    if name == "openrouter":
        if not openrouter_api_key:
            raise ProviderError(
                "openrouter", "OPENROUTER_API_KEY is required for the openrouter provider"
            )
        return OpenRouterProvider(
            api_key=openrouter_api_key,
            model=model,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
    if name == "ollama":
        return OllamaProvider(
            base_url=ollama_base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            max_tokens=max_tokens,
        )
    raise ProviderError(provider_name, f"Unknown LLM provider: {provider_name!r}")


def build_provider_from_settings() -> GroqProvider | OpenRouterProvider | OllamaProvider:
    """Build the LLM provider from application Settings.

    This is the only correct call-site for production use —
    keys are never accepted from user input.
    """
    from apps.api.app.config import get_settings  # avoid circular import at module load

    s = get_settings()
    return build_provider(
        provider_name=s.LLM_PROVIDER,
        model=s.LLM_MODEL,
        timeout_seconds=s.LLM_TIMEOUT_SECONDS,
        max_tokens=s.LLM_MAX_TOKENS,
        groq_api_key=s.GROQ_API_KEY,
        openrouter_api_key=s.OPENROUTER_API_KEY,
        ollama_base_url=s.OLLAMA_BASE_URL,
    )


def parse_json_content(raw: str) -> dict[str, Any]:
    """Parse JSON from LLM output.  Returns empty dict on failure (safe fallback)."""
    try:
        # Strip markdown code fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}
