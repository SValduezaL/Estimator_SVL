"""Detección heurística de PII (extensible por tipo)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from app.config import Settings
from app.foundation.guardrails.types import FailurePolicy
from app.foundation.guardrails.telemetry import guardrail_timer, log_guardrail_event
from app.foundation.guardrails.types import GuardrailCheckResult

REDACTION_TOKEN = "[REDACTED_PII]"


@dataclass(frozen=True)
class PiiRule:
    name: str
    pattern: re.Pattern[str]
    message: str


def _luhn_check(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    checksum = 0
    parity = len(digits) % 2
    for i, d in enumerate(digits):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _credit_card_rule() -> PiiRule:
    return PiiRule(
        name="credit_card",
        pattern=re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
        message="Payment card number detected — please remove personal data.",
    )


def default_pii_rules() -> list[PiiRule]:
    return [
        PiiRule(
            name="email",
            pattern=re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            message="Email address detected — please remove personal data.",
        ),
        PiiRule(
            name="iban",
            pattern=re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"),
            message="IBAN detected — please remove personal data.",
        ),
        PiiRule(
            name="phone",
            pattern=re.compile(r"(?:\+\d{1,3}[\s.-]?)?(?:\d[\s.-]?){9,12}\d"),
            message="Phone number detected — please remove personal data.",
        ),
        PiiRule(
            name="ssn",
            pattern=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            message="SSN-like number detected — please remove personal data.",
        ),
        PiiRule(
            name="openai_key",
            pattern=re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
            message="API key detected — please remove secrets.",
        ),
        PiiRule(
            name="aws_key",
            pattern=re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
            message="AWS access key detected — please remove secrets.",
        ),
        PiiRule(
            name="github_token",
            pattern=re.compile(r"\bghp_[A-Za-z0-9]{36,}\b"),
            message="GitHub token detected — please remove secrets.",
        ),
        _credit_card_rule(),
    ]


def _redact_with_rules(text: str, rules: list[PiiRule]) -> tuple[str, list[str]]:
    found: list[str] = []
    out = text
    for rule in rules:
        if rule.name == "credit_card":

            def repl(m: re.Match[str]) -> str:
                raw = re.sub(r"\D", "", m.group(0))
                if _luhn_check(raw):
                    found.append(rule.name)
                    return REDACTION_TOKEN
                return m.group(0)

            out = rule.pattern.sub(repl, out)
        else:
            if rule.pattern.search(out):
                found.append(rule.name)
                out = rule.pattern.sub(REDACTION_TOKEN, out)
    return out, found


def check_pii(
    text: str,
    *,
    settings: Settings,
    log_only: bool | None = None,
    input_mode: bool = True,
) -> GuardrailCheckResult:
    """Detecta PII; puede redactar (FILTER) o bloquear (EXCEPTION)."""
    enabled = (
        settings.guardrails_pii_input_enabled
        if input_mode
        else settings.guardrails_pii_output_enabled
    )
    name = "pii_input" if input_mode else "pii_output"
    if not enabled:
        return GuardrailCheckResult(name=name, passed=True, policy=FailurePolicy.LOG_ONLY)

    log_only_mode = (
        settings.guardrails_pii_input_log_only
        if log_only is None and input_mode
        else (log_only if log_only is not None else False)
    )
    policy = FailurePolicy.LOG_ONLY if log_only_mode else FailurePolicy.EXCEPTION

    with guardrail_timer(name):
        rules = default_pii_rules()
        redacted, found = _redact_with_rules(text, rules)
        if not found:
            return GuardrailCheckResult(name=name, passed=True, policy=policy)

        log_guardrail_event(
            "pii_detected",
            pii_types=found,
            input_mode=input_mode,
        )

        if log_only_mode:
            return GuardrailCheckResult(
                name=name,
                passed=True,
                policy=FailurePolicy.LOG_ONLY,
                metadata={"pii_types": found},
            )

        # FILTER policy for input: redact and continue
        if input_mode and not log_only_mode:
            # Default prod: EXCEPTION per baseline; FILTER if we add setting later
            pass

        first = found[0]
        msg = next((r.message for r in rules if r.name == first), "Personal data detected.")
        return GuardrailCheckResult(
            name=name,
            passed=False,
            policy=policy,
            message=msg,
            metadata={"pii_types": found},
            filtered_text=redacted if redacted != text else None,
        )


def redact_pii(text: str) -> str:
    """Redacta PII sin política (para output FILTER)."""
    redacted, _ = _redact_with_rules(text, default_pii_rules())
    return redacted
