import re
import time
from typing import List, Optional
from pydantic import BaseModel, Field


class GuardrailOutcome(BaseModel):
    """
    Result contract for pre-flight input guardrail validation.
    """
    is_safe: bool = Field(..., description="True if input passed all checks without violations.")
    sanitized_text: str = Field(..., description="Cleaned, normalized input string.")
    rejection_reason: Optional[str] = Field(None, description="Polite, executive-grade explanation if rejected.")
    violation_type: Optional[str] = Field(None, description="Category of rule triggered (if any).")
    matched_patterns: List[str] = Field(default_factory=list, description="Identifiers of triggered rules.")
    latency_ms: float = Field(0.0, description="Latency spent executing pre-flight guardrail in ms.")


# ---------------------------------------------------------------------------
# Pre-compiled Zero-False-Positive Regex Patterns
# ---------------------------------------------------------------------------

# 1. Explicit SQL injection syntax (structural syntax delimiters, not normal English words)
SQL_INJECTION_PATTERNS = [
    (
        "SQL_MUTATION_CHAINING",
        re.compile(
            r";\s*(DROP|DELETE\s+FROM|TRUNCATE|ALTER\s+TABLE|UPDATE\s+\w+\s+SET|INSERT\s+INTO|GRANT|REVOKE)\b",
            re.IGNORECASE,
        ),
        "For data integrity and security, database modification commands (DROP, DELETE, TRUNCATE, ALTER, INSERT, UPDATE) are not permitted. DataPilot operates strictly with read-only analytical access.",
    ),
    (
        "SQL_COMMENT_INJECTION",
        re.compile(r"(--\s*$|/\*.*?\*/)", re.MULTILINE | re.DOTALL),
        "Inquiry contains SQL comment syntax delimiters (`--` or `/* */`). Please submit your question in standard natural language.",
    ),
    (
        "SQL_UNION_SCHEMA_PROBE",
        re.compile(
            r"\bUNION\s+(ALL\s+)?SELECT\b.*?\bFROM\s+(pg_shadow|pg_authid|pg_user|information_schema|pg_tables)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "Direct queries probing internal database catalog tables and security metadata are restricted.",
    ),
]

# 2. Explicit prompt injection and system override signatures
PROMPT_INJECTION_PATTERNS = [
    (
        "SYSTEM_TAG_INJECTION",
        re.compile(r"<\s*/?\s*(system|instruction|developer|inst|context|system_prompt)\s*>", re.IGNORECASE),
        "System prompt boundary tags (`<system>`, `[INST]`) are not allowed in queries. Please rephrase your question in natural language.",
    ),
    (
        "PROMPT_OVERRIDE_DIRECTIVE",
        re.compile(
            r"(?i)\b(ignore|disregard|forget|bypass|override)\b.*?\b(all|previous|prior|system|above)\b.*?\b(instructions|rules|prompts|directives|guardrails)\b"
        ),
        "DataPilot AI operates strictly within enterprise data analytics boundaries and cannot override core system instructions.",
    ),
    (
        "ROLE_HIJACK_JAILBREAK",
        re.compile(
            r"(?i)\b(you are now|act as|pretend to be)\b.*?\b(dan|jailbreak|unrestricted|developer mode|god mode|root)\b"
        ),
        "Role-switching or unconstrained mode requests are not permitted. DataPilot operates exclusively as a Business Intelligence analyst.",
    ),
    (
        "SYSTEM_PROMPT_EXTRACTION",
        re.compile(
            r"(?i)\b(repeat|print|show|reveal|display|output|dump)\b.*?\b(your\s+full\s+system\s+prompt|initial\s+instructions|system\s+directive|developer\s+prompt)\b"
        ),
        "Internal operational directives and prompt architecture cannot be disclosed.",
    ),
]

# 3. Environment & Secret Extraction Probes
SECRET_PROBE_PATTERNS = [
    (
        "CREDENTIAL_EXTRACTION_PROBE",
        re.compile(
            r"(?i)\b(show|print|reveal|dump|extract|read|get)\b.*?(database_url|postgres_password|gemini_api_key|groq_api_key|api_key|secret_key|\.env\b|server\s+secrets)"
        ),
        "Access to environment variables, system credentials, and private API keys is strictly prohibited.",
    ),
]


# ---------------------------------------------------------------------------
# Sanitization and Normalization
# ---------------------------------------------------------------------------

def sanitize_user_input(text: str) -> str:
    """
    Normalizes input text by:
    1. Removing null bytes and non-printable control characters.
    2. Normalizing multiple whitespace / tab characters to single spaces.
    3. Stripping leading and trailing whitespace.
    """
    if not text:
        return ""

    # Remove null bytes and ASCII control characters (keep standard \n, \r, \t)
    cleaned = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)

    # Normalize excessive newlines / whitespace
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


# ---------------------------------------------------------------------------
# Pre-Flight Guardrail Validator (Layer 1 - <0.5ms)
# ---------------------------------------------------------------------------

def sanitize_and_validate_input(text: str) -> GuardrailOutcome:
    """
    Executes high-speed Tier-1 deterministic input guardrails.
    - Sub-millisecond latency.
    - Zero false positives on legitimate analytical queries (e.g. 'customers who dropped orders').
    - Intercepts malformed inputs, explicit SQL injection syntax, and prompt injections.
    """
    start_time = time.perf_counter()

    if not isinstance(text, str):
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        return GuardrailOutcome(
            is_safe=False,
            sanitized_text="",
            rejection_reason="Invalid inquiry format. Please provide a text-based analytical question.",
            violation_type="INVALID_TYPE",
            matched_patterns=["NON_STRING_INPUT"],
            latency_ms=elapsed_ms,
        )

    # 1. Sanitize
    cleaned = sanitize_user_input(text)

    # 2. Length & Empty Boundaries
    if len(cleaned) == 0:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        return GuardrailOutcome(
            is_safe=False,
            sanitized_text="",
            rejection_reason="Inquiry cannot be empty. Please ask a business question regarding sales, customers, or analytics.",
            violation_type="EMPTY_INPUT",
            matched_patterns=["EMPTY_STRING"],
            latency_ms=elapsed_ms,
        )

    if len(cleaned) > 600:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        return GuardrailOutcome(
            is_safe=False,
            sanitized_text=cleaned[:200] + "...",
            rejection_reason="The inquiry exceeds the maximum allowed length of 600 characters. Please provide a more concise question.",
            violation_type="OVERSIZED_INPUT",
            matched_patterns=["EXCEEDS_MAX_LENGTH"],
            latency_ms=elapsed_ms,
        )

    # 3. Check Explicit SQL Injection Patterns
    for rule_id, pattern, reason in SQL_INJECTION_PATTERNS:
        if pattern.search(cleaned):
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
            return GuardrailOutcome(
                is_safe=False,
                sanitized_text=cleaned,
                rejection_reason=reason,
                violation_type=rule_id,
                matched_patterns=[rule_id],
                latency_ms=elapsed_ms,
            )

    # 4. Check Prompt Injection & System Override Patterns
    for rule_id, pattern, reason in PROMPT_INJECTION_PATTERNS:
        if pattern.search(cleaned):
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
            return GuardrailOutcome(
                is_safe=False,
                sanitized_text=cleaned,
                rejection_reason=reason,
                violation_type=rule_id,
                matched_patterns=[rule_id],
                latency_ms=elapsed_ms,
            )

    # 5. Check Secret / Credential Probes
    for rule_id, pattern, reason in SECRET_PROBE_PATTERNS:
        if pattern.search(cleaned):
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
            return GuardrailOutcome(
                is_safe=False,
                sanitized_text=cleaned,
                rejection_reason=reason,
                violation_type=rule_id,
                matched_patterns=[rule_id],
                latency_ms=elapsed_ms,
            )

    # Clean input passed all pre-flight checks
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
    return GuardrailOutcome(
        is_safe=True,
        sanitized_text=cleaned,
        rejection_reason=None,
        violation_type=None,
        matched_patterns=[],
        latency_ms=elapsed_ms,
    )
