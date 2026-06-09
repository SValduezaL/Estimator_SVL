"""Hooks LLM-as-judge (arquitectura preparada, sin judge real por defecto)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.domain.schemas.estimation_output import EstimationResult


@dataclass
class JudgeContext:
    description_hash: str
    project_type: str
    detail_level: str
    result: EstimationResult
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class JudgeVerdict:
    passed: bool
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class OutputJudge(Protocol):
    def evaluate(self, ctx: JudgeContext) -> JudgeVerdict: ...


class NoOpOutputJudge:
    """Judge por defecto: no bloquea ni reintenta."""

    def evaluate(self, ctx: JudgeContext) -> JudgeVerdict:
        _ = ctx
        return JudgeVerdict(passed=True)


_judges: list[OutputJudge] = [NoOpOutputJudge()]


def register_output_judge(judge: OutputJudge) -> None:
    _judges.append(judge)


def reset_output_judges() -> None:
    global _judges
    _judges = [NoOpOutputJudge()]


def run_output_judges(ctx: JudgeContext, *, enabled: bool) -> JudgeVerdict:
    if not enabled:
        return JudgeVerdict(passed=True)
    for judge in _judges:
        verdict = judge.evaluate(ctx)
        if not verdict.passed:
            return verdict
    return JudgeVerdict(passed=True)
