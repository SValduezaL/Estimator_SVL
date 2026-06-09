from __future__ import annotations

from app.domain.schemas.estimation_common import DetailLevel, ProjectType, Tier
from app.generation.conversation.tier_resolver import resolve_tier


def test_tier_resolver_developer_for_high_complexity() -> None:
    decision = resolve_tier(
        detail_level=DetailLevel.DETAILED,
        project_type=ProjectType.WEB_SAAS,
        description="Proyecto complejo con integraciones",
    )
    assert decision.tier == Tier.DEVELOPER


def test_tier_resolver_executive_for_summary() -> None:
    decision = resolve_tier(
        detail_level=DetailLevel.SUMMARY,
        project_type=ProjectType.INTERNAL_TOOL,
        description="Resumen para comité",
    )
    assert decision.tier == Tier.EXECUTIVE


def test_tier_resolver_pm_for_product_signals() -> None:
    decision = resolve_tier(
        detail_level=DetailLevel.MEDIUM,
        project_type=ProjectType.WEB_SAAS,
        description="Necesito roadmap para stakeholders",
    )
    assert decision.tier == Tier.PM
