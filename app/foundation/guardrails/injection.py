"""Detección heurística de prompt injection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.config import Settings
from app.foundation.guardrails.types import FailurePolicy
from app.foundation.guardrails.telemetry import guardrail_timer, log_guardrail_event
from app.foundation.guardrails.types import GuardrailCheckResult

_PATTERNS_DIR = Path(__file__).resolve().parent / "patterns"
_FLAG_MAP = {"IGNORECASE": re.IGNORECASE, "DOTALL": re.DOTALL, "MULTILINE": re.MULTILINE}


@dataclass(frozen=True)
class InjectionPattern:
    id: str
    category: str
    compiled: re.Pattern[str]


def _parse_flags(flag_str: str) -> int:
    flags = 0
    for part in flag_str.split("|"):
        part = part.strip()
        if part in _FLAG_MAP:
            flags |= _FLAG_MAP[part]
    return flags


def load_injection_patterns(version: str = "v1") -> list[InjectionPattern]:
    path = _PATTERNS_DIR / f"injection_{version}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"Injection patterns file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    out: list[InjectionPattern] = []
    for entry in data.get("patterns", []):
        flags = _parse_flags(entry.get("flags", ""))
        out.append(
            InjectionPattern(
                id=entry["id"],
                category=entry.get("category", "unknown"),
                compiled=re.compile(entry["pattern"], flags),
            )
        )
    return out


_REGISTRY_CACHE: dict[str, list[InjectionPattern]] = {}


def get_pattern_registry(version: str, *, reload: bool = False) -> list[InjectionPattern]:
    if reload or version not in _REGISTRY_CACHE:
        _REGISTRY_CACHE[version] = load_injection_patterns(version)
    return _REGISTRY_CACHE[version]


def clear_pattern_registry_cache() -> None:
    _REGISTRY_CACHE.clear()


def check_prompt_injection(
    text: str,
    *,
    settings: Settings,
) -> GuardrailCheckResult:
    """Detecta patrones de inyección de instrucciones."""
    name = "prompt_injection"
    if not settings.guardrails_injection_enabled:
        return GuardrailCheckResult(name=name, passed=True, policy=FailurePolicy.LOG_ONLY)

    policy = (
        FailurePolicy.LOG_ONLY
        if settings.guardrails_injection_log_only
        else FailurePolicy.EXCEPTION
    )

    with guardrail_timer(name):
        patterns = get_pattern_registry(settings.guardrails_injection_pattern_version)
        for pat in patterns:
            match = pat.compiled.search(text)
            if match:
                snippet = match.group(0)[:80]
                log_guardrail_event(
                    "prompt_injection_detected",
                    pattern_id=pat.id,
                    category=pat.category,
                    pattern_version=settings.guardrails_injection_pattern_version,
                    match_preview=snippet,
                )
                return GuardrailCheckResult(
                    name=name,
                    passed=False,
                    policy=policy,
                    message=f"Suspicious instruction-like text detected: {snippet!r}",
                    metadata={
                        "pattern_id": pat.id,
                        "category": pat.category,
                        "match": snippet,
                    },
                )

    return GuardrailCheckResult(name=name, passed=True, policy=policy)
