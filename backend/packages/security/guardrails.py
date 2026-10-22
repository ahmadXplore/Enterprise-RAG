"""AI Input and Output Security Guardrails.

Enforces Rule 12 — AI/RAG Security:
1. Input Guard: Lightweight regex & pattern classifier blocking users from typing
   known jailbreaks, prompt injection attempts, or sensitive keywords.
2. Output Guard: Deep inspection of LLM generated text before presentation to user.
   If restricted data (SSNs, API keys, private keys, credit cards, or banned keywords)
   is detected, blocks the response and replaces it with a generic security message.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import ClassVar

logger = logging.getLogger("enterprise_rag")


class SecurityGuardrailError(Exception):
    """Raised when an input prompt or output response violates security policies."""

    def __init__(self, message: str, guard_type: str, violation_category: str) -> None:
        super().__init__(message)
        self.guard_type = guard_type
        self.violation_category = violation_category


# ─────────────────────────────────────────────────────────────────────────────
# 1. INPUT GUARDRAIL
# ─────────────────────────────────────────────────────────────────────────────


class InputGuard:
    """Lightweight classifier blocking jailbreaks and sensitive injection keywords."""

    GENERIC_BLOCKED_MESSAGE: ClassVar[str] = (
        "Input blocked by security guardrails: your message contains prohibited "
        "keywords or prompt manipulation attempts."
    )

    # Known jailbreaks and instruction override patterns (compiled case-insensitively)
    JAILBREAK_PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        (
            re.compile(
                r"ignore\s+(all\s+)?(previous|prior|above|earlier|system)\s+(instructions?|rules?|prompts?|context)",
                re.IGNORECASE,
            ),
            "instruction_override_ignore",
        ),
        (
            re.compile(
                r"disregard\s+(all\s+)?(previous|prior|above|earlier|system)\s+(instructions?|rules?|prompts?|context)",
                re.IGNORECASE,
            ),
            "instruction_override_disregard",
        ),
        (
            re.compile(
                r"forget\s+(all\s+)?(previous|prior|above|earlier|system)\s+(instructions?|rules?|prompts?|context)",
                re.IGNORECASE,
            ),
            "instruction_override_forget",
        ),
        (
            re.compile(
                r"override\s+(the\s+)?(system\s+)?(prompt|rules?|instructions?|guidelines?)",
                re.IGNORECASE,
            ),
            "system_prompt_override",
        ),
        (
            re.compile(
                r"\b(DAN\s+mode|do\s+anything\s+now|developer\s+mode\s+enabled|enable\s+developer\s+mode)\b",
                re.IGNORECASE,
            ),
            "dan_jailbreak_mode",
        ),
        (
            re.compile(
                r"\b(jailbreak|jailbroken|unrestricted\s+mode|no\s+restrictions?\s+mode)\b",
                re.IGNORECASE,
            ),
            "explicit_jailbreak_token",
        ),
        (
            re.compile(
                r"bypass\s+(all\s+)?(safety|restrictions?|filters?|guidelines?|policies?)",
                re.IGNORECASE,
            ),
            "safety_bypass_attempt",
        ),
        (
            re.compile(
                r"you\s+are\s+now\s+(an?\s+)?(unrestricted|unfiltered|rogue|evil|uncensored)\s+(ai|assistant|model|bot)",
                re.IGNORECASE,
            ),
            "persona_hijack",
        ),
        (
            re.compile(
                r"act\s+as\s+(an?\s+)?(unrestricted|unfiltered|evil|malicious|lawless)\s+(ai|assistant|model|bot)",
                re.IGNORECASE,
            ),
            "persona_hijack_act_as",
        ),
        (
            re.compile(
                r"pretend\s+(you\s+have\s+no\s+(rules|restrictions|limits|ethics)|you\s+are\s+unrestricted)",
                re.IGNORECASE,
            ),
            "pretend_no_rules",
        ),
        (
            re.compile(
                r"(reveal|print|output|show|repeat)\s+(your\s+)?(exact\s+)?(system\s+prompt|hidden\s+instructions?|internal\s+instructions?|system\s+instructions?)",
                re.IGNORECASE,
            ),
            "system_prompt_leak_attempt",
        ),
        (
            re.compile(
                r"what\s+(is|are)\s+your\s+(exact\s+)?(system\s+prompt|internal\s+instructions?|system\s+instructions?)",
                re.IGNORECASE,
            ),
            "system_prompt_probe",
        ),
        (
            re.compile(
                r"(?:\b|^)(format\s+c:|rm\s+-rf(\s+[\/~]|\s*$)|drop\s+table\s+users|union\s+select\s+.*\s+from)",
                re.IGNORECASE,
            ),
            "destructive_command_payload",
        ),
    ]

    @classmethod
    def check(cls, text: str) -> tuple[bool, str | None, str | None]:
        """Check if an input message violates security guardrails.

        Returns:
            Tuple of (is_safe, violation_category, error_message).
            If safe: (True, None, None).
            If violation detected: (False, violation_category, GENERIC_BLOCKED_MESSAGE).
        """
        if not text or not isinstance(text, str):
            return True, None, None

        cleaned = text.strip()
        for pattern, category in cls.JAILBREAK_PATTERNS:
            if pattern.search(cleaned):
                logger.warning(
                    "InputGuard blocked message",
                    extra={
                        "event": "security_input_blocked",
                        "category": category,
                        "text_prefix": cleaned[:80],
                    },
                )
                return False, category, cls.GENERIC_BLOCKED_MESSAGE

        return True, None, None


# ─────────────────────────────────────────────────────────────────────────────
# 2. OUTPUT GUARDRAIL
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class OutputGuardResult:
    is_safe: bool
    safe_text: str
    violations: list[str]
    blocked: bool


class OutputGuard:
    """Inspects LLM output before presentation to user.

    If restricted data (SSNs, API keys, private keys, passwords, banned words)
    is found, blocks the response and returns a standard enterprise error.
    """

    GENERIC_BLOCKED_MESSAGE: ClassVar[str] = (
        "This response was blocked by enterprise security guardrails because "
        "it was detected to contain restricted or sensitive information."
    )

    # Patterns for restricted sensitive data
    RESTRICTED_PATTERNS: ClassVar[list[tuple[re.Pattern[str], str]]] = [
        # 1. Social Security Numbers (US SSN: XXX-XX-XXXX with valid area code checks)
        (
            re.compile(
                r"\b(?!000|666|9\d{2})\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b"
            ),
            "social_security_number",
        ),
        # 2. OpenAI API Keys (legacy sk-... and project sk-proj-...)
        (
            re.compile(r"\bsk-(?:proj-)?[a-zA-Z0-9_-]{20,}\b"),
            "openai_api_key",
        ),
        # 3. Anthropic API Keys (sk-ant-...)
        (
            re.compile(r"\bsk-ant-[a-zA-Z0-9_-]{20,}\b"),
            "anthropic_api_key",
        ),
        # 4. AWS Access Key IDs
        (
            re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            "aws_access_key",
        ),
        # 5. GitHub Personal Access Tokens (ghp, gho, ghu, ghs, ghr)
        (
            re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"),
            "github_token",
        ),
        # 6. Slack API Tokens (xoxb, xoxp, xoxa, xoxr, xoxs)
        (
            re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,}\b"),
            "slack_token",
        ),
        # 7. Hugging Face Tokens (hf_...)
        (
            re.compile(r"\bhf_[A-Za-z0-9]{30,}\b"),
            "huggingface_token",
        ),
        # 8. JWT / Bearer tokens (standard 3-segment base64 token)
        (
            re.compile(
                r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
            ),
            "jwt_bearer_token",
        ),
        # 9. RSA / EC / OpenSSH Private Keys
        (
            re.compile(r"-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----"),
            "private_cryptographic_key",
        ),
        # 10. Database URI Connection strings containing credentials
        (
            re.compile(
                r"(?:postgres|postgresql|mysql|mongodb|redis):\/\/[^:\s\n]+:[^@\s\n]+@[^\s\n]+"
            ),
            "database_credentials_uri",
        ),
        # 11. Credit Card Numbers (Major formats: 13-16 digits with hyphen/space)
        (
            re.compile(
                r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
            ),
            "payment_card_number",
        ),
        # 12. Banned raw credentials / password assignments
        (
            re.compile(
                r"\b(?:password|passwd|secret_key|api_secret)\s*[:=]\s*['\"][^'\"]{6,}['\"]",
                re.IGNORECASE,
            ),
            "raw_password_assignment",
        ),
    ]

    @classmethod
    def check(cls, text: str) -> tuple[bool, list[str]]:
        """Check if output contains any restricted sensitive data.

        Returns:
            Tuple of (is_safe, detected_violation_categories).
        """
        if not text or not isinstance(text, str):
            return True, []

        violations: list[str] = []
        for pattern, category in cls.RESTRICTED_PATTERNS:
            if pattern.search(text):
                violations.append(category)

        return len(violations) == 0, violations

    @classmethod
    def sanitize_or_block(cls, text: str) -> OutputGuardResult:
        """Inspect and return safe text, blocking if restricted data is present."""
        is_safe, violations = cls.check(text)
        if not is_safe:
            logger.warning(
                "OutputGuard blocked response due to restricted data leak",
                extra={
                    "event": "security_output_blocked",
                    "violations": violations,
                },
            )
            return OutputGuardResult(
                is_safe=False,
                safe_text=cls.GENERIC_BLOCKED_MESSAGE,
                violations=violations,
                blocked=True,
            )

        return OutputGuardResult(
            is_safe=True,
            safe_text=text,
            violations=[],
            blocked=False,
        )


def validate_input(text: str) -> str:
    """Validate user prompt through InputGuard. Raises SecurityGuardrailError if blocked."""
    is_safe, category, msg = InputGuard.check(text)
    if not is_safe:
        raise SecurityGuardrailError(
            message=msg or InputGuard.GENERIC_BLOCKED_MESSAGE,
            guard_type="input_guard",
            violation_category=category or "unknown",
        )
    return text


def validate_output(text: str) -> str:
    """Validate LLM answer through OutputGuard. Raises SecurityGuardrailError if blocked."""
    result = OutputGuard.sanitize_or_block(text)
    if result.blocked:
        raise SecurityGuardrailError(
            message=result.safe_text,
            guard_type="output_guard",
            violation_category=", ".join(result.violations),
        )
    return text
