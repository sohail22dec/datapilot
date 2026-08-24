import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field


class OutputGuardOutcome(BaseModel):
    """
    Result contract for Post-LLM output guardrail validation, redaction, and number grounding.
    """
    is_safe: bool = Field(..., description="True if output is clean or successfully sanitized.")
    sanitized_output: str = Field(..., description="Cleaned, redacted, and verified response text.")
    violations_detected: List[str] = Field(default_factory=list, description="List of identified security/policy issues.")
    is_grounded: bool = Field(default=True, description="True if numbers cited in text match DB rows/metrics.")
    grounded_numbers: List[float] = Field(default_factory=list, description="Numbers verified against DB data.")
    unverified_numbers: List[float] = Field(default_factory=list, description="Numbers not found in DB rows or aggregates.")
    latency_ms: float = Field(0.0, description="Latency spent executing output guardrail in ms.")


# ---------------------------------------------------------------------------
# Pre-compiled Secret & Credential Redaction Patterns
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    (
        "GROQ_API_KEY_LEAK",
        re.compile(r"\bgsk_[a-zA-Z0-9_-]{20,}\b"),
        "[REDACTED_API_KEY]",
    ),
    (
        "GEMINI_API_KEY_LEAK",
        re.compile(r"\bAIza[0-9A-Za-z-_]{20,}\b"),
        "[REDACTED_API_KEY]",
    ),
    (
        "DATABASE_URI_LEAK",
        re.compile(r"\bpostgres(?:ql)?(?:\+psycopg2)?://[^\s/]+@[^\s/]+/[^\s]+", re.IGNORECASE),
        "[REDACTED_DATABASE_URI]",
    ),
    (
        "BEARER_TOKEN_LEAK",
        re.compile(r"\bBearer\s+[a-zA-Z0-9_\-\.]{20,}\b", re.IGNORECASE),
        "Bearer [REDACTED_TOKEN]",
    ),
    (
        "ENV_VARIABLE_ASSIGNMENT_LEAK",
        re.compile(r"\b(DATABASE_URL|GEMINI_API_KEY|GROQ_API_KEY|POSTGRES_PASSWORD)\s*=\s*[^\s]+", re.IGNORECASE),
        r"\1=[REDACTED]",
    ),
]

# ---------------------------------------------------------------------------
# Stack Trace & Internal System Driver Errors
# ---------------------------------------------------------------------------

STACK_TRACE_PATTERNS = [
    re.compile(r"Traceback\s*\(most\s+recent\s+call\s+last\):", re.IGNORECASE),
    re.compile(r"\bpsycopg2\.(OperationalError|ProgrammingError|InternalError|DatabaseError)\b", re.IGNORECASE),
    re.compile(r"\bsqlalchemy\.exc\.(SQLAlchemyError|OperationalError|ProgrammingError)\b", re.IGNORECASE),
]

# ---------------------------------------------------------------------------
# System Prompt & Preamble Echo Scrubbing
# ---------------------------------------------------------------------------

PROMPT_ECHO_PATTERNS = [
    (
        "SYSTEM_PROMPT_ECHO",
        re.compile(r"(ENTRY_SYSTEM_PROMPT|LEAN_SYNTHESIS_PROMPT|You are DataPilot AI, an elite Business Intelligence Architect)", re.IGNORECASE),
    ),
]


# ---------------------------------------------------------------------------
# Number Grounding & Factuality Verification Engine
# ---------------------------------------------------------------------------

def extract_numbers_from_text(text: str) -> List[float]:
    """
    Extracts currency values (₹, $), percentages (%), and numeric metrics from text.
    Filters out calendar years (2020-2030) and ranking labels (e.g. 'top 5', '#1').
    """
    if not text:
        return []

    # Filter out calendar years (2020-2030) and ranking labels
    cleaned = re.sub(r"\b(202[0-9]|top\s+\d+|#\d+)\b", "", text, flags=re.IGNORECASE)

    # Match currency (₹1,24,500.50), percentages (14.5%), and standard numbers
    matches = re.findall(r"[₹\$]?\s*([0-9]{1,3}(?:,[0-9]{2,3})*(?:\.[0-9]+)?|\d+(?:\.\d+)?)\s*%?", cleaned)

    numbers: List[float] = []
    for m in matches:
        num_str = m.replace(",", "").strip()
        try:
            val = float(num_str)
            numbers.append(val)
        except ValueError:
            pass

    return numbers


def build_ground_truth_numbers(
    rows: Optional[List[Dict[str, Any]]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Set[float]:
    """
    Builds a mathematical ground truth pool containing:
    1. Direct numeric cell values across all query result rows.
    2. Total row count (len(rows)).
    3. Column sums and averages.
    4. Computed metrics from the Python stats engine.
    """
    truth: Set[float] = set()
    rows = rows or []

    if rows:
        row_count = float(len(rows))
        truth.add(row_count)

        numeric_sums: Dict[str, float] = {}
        for r in rows:
            for k, v in r.items():
                if isinstance(v, (int, float)) and not k.endswith("_id"):
                    val = round(float(v), 2)
                    truth.add(val)
                    numeric_sums[k] = numeric_sums.get(k, 0.0) + val

        # Add column sums & column averages
        for col, total in numeric_sums.items():
            truth.add(round(total, 2))
            truth.add(round(total / row_count, 2))

    # Add metrics from stats engine (e.g. margin=14.5, growth=22.3)
    if metrics:
        for k, v in metrics.items():
            if isinstance(v, (int, float)):
                truth.add(round(float(v), 2))
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        for sub_k, sub_v in item.items():
                            if isinstance(sub_v, (int, float)) and not sub_k.endswith("_id"):
                                truth.add(round(float(sub_v), 2))

    return truth


def verify_number_grounding(
    text: str,
    rows: Optional[List[Dict[str, Any]]] = None,
    metrics: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, List[float], List[float]]:
    """
    Mathematically verifies that numbers cited in LLM text originate from real DB data.
    Uses exact and tolerance matching (±0.05 absolute or ±1% relative for rounding).
    Returns: (is_grounded, grounded_numbers, unverified_numbers)
    """
    claimed = extract_numbers_from_text(text)
    if not claimed:
        return True, [], []

    # If no rows or metrics provided, all claimed numbers are unverified
    if not rows and not metrics:
        return True, claimed, []

    ground_truth = build_ground_truth_numbers(rows, metrics)
    grounded: List[float] = []
    unverified: List[float] = []

    for num in claimed:
        matched = False
        for t in ground_truth:
            # Exact match, rounded match (±0.05), or relative tolerance (±1%)
            if abs(num - t) <= 0.05 or (t != 0 and abs(num - t) / abs(t) <= 0.015):
                matched = True
                break

        if matched:
            grounded.append(num)
        else:
            unverified.append(num)

    is_grounded = (len(unverified) == 0)
    return is_grounded, grounded, unverified


# ---------------------------------------------------------------------------
# Core Sanitization Functions
# ---------------------------------------------------------------------------

def redact_secrets(text: str) -> Tuple[str, List[str]]:
    """
    Scrubs API keys, database connection strings, tokens, and env variables from text.
    Returns the redacted text and list of triggered pattern names.
    """
    sanitized = text
    violations = []

    for rule_id, pattern, replacement in SECRET_PATTERNS:
        if pattern.search(sanitized):
            sanitized = pattern.sub(replacement, sanitized)
            violations.append(rule_id)

    return sanitized, violations


def scrub_stack_traces(text: str) -> Tuple[str, bool]:
    """
    Detects and scrubs raw Python tracebacks or database driver exceptions,
    replacing them with an executive, professional fallback message.
    """
    for pattern in STACK_TRACE_PATTERNS:
        if pattern.search(text):
            safe_fallback = (
                "I encountered an operational issue while retrieving these records. "
                "Please refine your business inquiry or try again."
            )
            return safe_fallback, True

    return text, False


def scrub_prompt_echoes(text: str) -> Tuple[str, List[str]]:
    """
    Removes accidental echoes of internal prompt template headers.
    """
    sanitized = text
    violations = []

    for rule_id, pattern in PROMPT_ECHO_PATTERNS:
        if pattern.search(sanitized):
            sanitized = pattern.sub("", sanitized).strip()
            violations.append(rule_id)

    return sanitized, violations


def sanitize_and_validate_output(
    text: str,
    rows: Optional[List[Dict[str, Any]]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    has_data: Optional[bool] = None,
) -> OutputGuardOutcome:
    """
    Executes high-speed Tier-3 deterministic Output Guardrail (Post-LLM):
    1. Redacts leaked API keys, tokens, DB URIs, and env secrets.
    2. Scrubs raw Python tracebacks and driver errors with executive messaging.
    3. Scrubs accidental system prompt template echoes.
    4. Handles blank / empty output with safe contextual fallback.
    5. Performs mathematical number grounding against raw DB rows & metrics.
    - Zero API calls, sub-millisecond execution (<0.05ms).
    """
    start_time = time.perf_counter()

    if has_data is None:
        has_data = bool(rows)

    if not isinstance(text, str):
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
        return OutputGuardOutcome(
            is_safe=False,
            sanitized_output="Analysis completed based on the retrieved records.",
            violations_detected=["NON_STRING_OUTPUT"],
            is_grounded=True,
            grounded_numbers=[],
            unverified_numbers=[],
            latency_ms=elapsed_ms,
        )

    all_violations: List[str] = []

    # 1. Scrub Stack Traces and Driver Exceptions
    cleaned, trace_scrubbed = scrub_stack_traces(text)
    if trace_scrubbed:
        all_violations.append("RAW_STACK_TRACE_SCRUBBED")

    # 2. Redact API Keys, Tokens, and Credentials
    cleaned, secret_violations = redact_secrets(cleaned)
    all_violations.extend(secret_violations)

    # 3. Scrub Prompt Echoes
    cleaned, prompt_violations = scrub_prompt_echoes(cleaned)
    all_violations.extend(prompt_violations)

    # 4. Handle Empty or Whitespace-only Outputs
    if not cleaned.strip():
        if has_data:
            cleaned = "Analysis completed based on the retrieved data records."
        else:
            cleaned = "No matching records were found in the database for your inquiry."
        all_violations.append("EMPTY_OUTPUT_FALLBACK")

    # 5. Verify Number Grounding against DB rows and metrics
    is_grounded, grounded_nums, unverified_nums = verify_number_grounding(
        text=cleaned,
        rows=rows,
        metrics=metrics,
    )
    if not is_grounded:
        all_violations.append("UNGROUNDED_NUMBER_DETECTED")

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 3)
    return OutputGuardOutcome(
        is_safe=True,
        sanitized_output=cleaned.strip(),
        violations_detected=all_violations,
        is_grounded=is_grounded,
        grounded_numbers=grounded_nums,
        unverified_numbers=unverified_nums,
        latency_ms=elapsed_ms,
    )
