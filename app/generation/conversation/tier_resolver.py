"""Resolver determinista de tier en runtime."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.schemas.estimation_common import DetailLevel, ProjectType, Tier


@dataclass
class TierDecision:
    tier: Tier
    model_override: str | None
    max_tokens: int | None
    thinking_budget: int | None
    rule_id: str
    reason_codes: list[str]


def resolve_tier(
    *,
    detail_level: DetailLevel,
    project_type: ProjectType,
    description: str,
) -> TierDecision:
    reasons: list[str] = []
    if detail_level == DetailLevel.DETAILED or project_type == ProjectType.DATA_PIPELINE:
        reasons.append("high_complexity")
        return TierDecision(
            tier=Tier.DEVELOPER,
            model_override=None,
            max_tokens=3000,
            thinking_budget=1200,
            rule_id="rule_developer_high_complexity",
            reason_codes=reasons,
        )
    if detail_level == DetailLevel.SUMMARY:
        reasons.append("concise_output")
        return TierDecision(
            tier=Tier.EXECUTIVE,
            model_override=None,
            max_tokens=1200,
            thinking_budget=None,
            rule_id="rule_executive_summary",
            reason_codes=reasons,
        )
    if "roadmap" in description.lower() or "stakeholder" in description.lower():
        reasons.append("product_audience")
        return TierDecision(
            tier=Tier.PM,
            model_override=None,
            max_tokens=2200,
            thinking_budget=600,
            rule_id="rule_pm_product_signals",
            reason_codes=reasons,
        )
    return TierDecision(
        tier=Tier.DEFAULT,
        model_override=None,
        max_tokens=None,
        thinking_budget=None,
        rule_id="rule_default",
        reason_codes=["fallback"],
    )
