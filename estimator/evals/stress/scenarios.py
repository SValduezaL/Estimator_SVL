"""Synthetic multi-turn stress scenarios for CAG memory evaluation.

Each profile is a fixed script of 20 conversational turns (one POST
``/sessions/{id}/estimate`` per turn). Slice to ``N in TURN_LENGTHS`` for
shorter runs.

Fact-tracker contract (consumed by ``MemoryDriftMetric`` in Block 4)
--------------------------------------------------------------------
For turn ``k``, ``fact_to_remember`` is a short string introduced in that
turn. For any later snapshot at turn ``t > k``, downstream metrics expect
the fact to still be recoverable from session state (metadata, summary,
anchors, or model output). Use ``facts_introduced_up_to(profile, t)`` to
list ``(intro_turn, fact)`` pairs that should have been retained by turn
``t``.

Empty ``fact_to_remember`` values are skipped when building the tracker.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from evals.dataset import DetailLevelStr, OutputFormatStr, ProjectTypeStr


ProfileId = Literal["growing", "pivot", "contradicting"]

TURN_LENGTHS: tuple[int, ...] = (1, 3, 6, 10, 20)
PROFILE_IDS: tuple[ProfileId, ...] = ("growing", "pivot", "contradicting")


class StressTurn(BaseModel):
    """One business turn: transcript sent to the estimator + fact introduced."""

    turn_index: int = Field(ge=1, le=20)
    transcript: str = Field(min_length=20, max_length=80_000)
    fact_to_remember: str = Field(
        default="",
        description="Short fact introduced this turn; empty means no new tracked fact.",
    )


class StressProfile(BaseModel):
    """Full 20-turn script for one behavioural profile."""

    profile_id: ProfileId
    description: str
    project_type: ProjectTypeStr = "web_saas"
    detail_level: DetailLevelStr = "medium"
    output_format: OutputFormatStr = "phases_table"
    turns: list[StressTurn] = Field(min_length=20, max_length=20)

    @model_validator(mode="after")
    def _turn_indices_match_positions(self) -> StressProfile:
        for i, turn in enumerate(self.turns, start=1):
            if turn.turn_index != i:
                raise ValueError(
                    f"turn {i} has turn_index={turn.turn_index}, expected {i}"
                )
        return self


def _t(turn_index: int, transcript: str, fact_to_remember: str = "") -> StressTurn:
    return StressTurn(
        turn_index=turn_index,
        transcript=transcript,
        fact_to_remember=fact_to_remember,
    )


def _build_growing_turns() -> list[StressTurn]:
    """Nimbus CRM — requirements accumulate; project name must survive to turn 20."""
    return [
        _t(
            1,
            "Kickoff for Nimbus CRM: a B2B sales pipeline product for the commercial "
            "team. Stack is React on the frontend and Postgres on the backend. Team "
            "of four engineers plus one product owner.",
            "project name: Nimbus",
        ),
        _t(
            2,
            "Add enterprise authentication: OAuth2 with Google Workspace and "
            "role-based access control for sales managers vs reps.",
            "requirement: OAuth2 and RBAC",
        ),
        _t(
            3,
            "We need strict multi-tenant isolation so each customer organisation "
            "only sees its own deals, contacts, and audit data.",
            "requirement: multi-tenant isolation",
        ),
        _t(
            4,
            "Compliance requires an immutable audit log of every create, update, "
            "and delete on opportunities and accounts.",
            "requirement: immutable audit log",
        ),
        _t(
            5,
            "Sales ops asked for CSV export of pipelines and activities with "
            "scheduled nightly dumps to S3.",
            "feature: CSV export",
        ),
        _t(
            6,
            "Integrate outbound webhooks so customer systems get notified when "
            "deal stages change.",
            "feature: outbound webhooks",
        ),
        _t(
            7,
            "Contractual SLA is 99.9% uptime for the SaaS API and dashboard.",
            "SLA: 99.9 percent uptime",
        ),
        _t(
            8,
            "GDPR applies: configurable data retention policies and right-to-erasure "
            "workflows for contact records.",
            "compliance: GDPR data retention",
        ),
        _t(
            9,
            "Delivery expects GitHub Actions CI/CD with automated tests on every PR.",
            "DevOps: GitHub Actions CI/CD",
        ),
        _t(
            10,
            "Separate staging and production environments with promotion gates.",
            "environments: staging and production",
        ),
        _t(
            11,
            "Public API needs per-tenant rate limiting and abuse protection.",
            "API: rate limiting",
        ),
        _t(
            12,
            "Users want email notifications for assignments, mentions, and stage changes.",
            "feature: email notifications",
        ),
        _t(
            13,
            "Leadership wants an analytics dashboard with funnel conversion and "
            "forecast charts.",
            "feature: analytics dashboard",
        ),
        _t(
            14,
            "Admin console must be mobile-responsive for field sales on tablets.",
            "UI: mobile-responsive admin",
        ),
        _t(
            15,
            "Operations require nightly encrypted backups with 30-day retention.",
            "ops: nightly backups",
        ),
        _t(
            16,
            "Security gate: external penetration test before production launch.",
            "security: penetration test before launch",
        ),
        _t(
            17,
            "Include end-user training documentation and short video walkthroughs.",
            "deliverable: training documentation",
        ),
        _t(
            18,
            "Four weeks of hypercare support after go-live are in scope.",
            "support: 4 weeks hypercare",
        ),
        _t(
            19,
            "Roadmap note: phase 2 will add Stripe billing but is out of scope for "
            "this estimate.",
            "roadmap: phase 2 Stripe billing",
        ),
        _t(
            20,
            "Final pass for Nimbus CRM: please produce a consolidated estimate that "
            "integrates every requirement we discussed across all prior turns, "
            "keeping the original Nimbus product identity.",
            "project name: Nimbus",
        ),
    ]


def _build_pivot_turns() -> list[StressTurn]:
    """Atlas — stack pivots from React web to Flutter mobile at turn 5."""
    return [
        _t(
            1,
            "We are scoping Atlas, an operations dashboard for warehouse managers. "
            "Initial plan is a React SPA with a Node.js API and Postgres database.",
            "project name: Atlas",
        ),
        _t(
            2,
            "Confirm the web client stays on React with TypeScript and component "
            "library Chakra for the first milestone.",
            "stack includes React",
        ),
        _t(
            3,
            "Backend remains Node.js with Express; expose REST endpoints for inventory "
            "and shipment status.",
            "stack includes Node",
        ),
        _t(
            4,
            "Postgres is the system of record; we need migration tooling and seed data.",
            "stack includes Postgres",
        ),
        _t(
            5,
            "Strategic pivot: cancel the React web front end. Re-scope Atlas as a "
            "Flutter mobile app for iOS and Android; warehouse staff will use phones "
            "on the floor instead of desktops.",
            "stack includes Flutter",
        ),
        _t(
            6,
            "Flutter app must support offline-first sync when connectivity drops in "
            "the warehouse.",
            "mobile: offline-first Flutter",
        ),
        _t(
            7,
            "Add push notifications for urgent pick exceptions and delayed shipments.",
            "mobile: push notifications",
        ),
        _t(
            8,
            "Release through Apple App Store and Google Play with enterprise MDM option.",
            "mobile: store deployment",
        ),
        _t(
            9,
            "Product wants Firebase analytics for screen flows and crash-free sessions.",
            "mobile: Firebase analytics",
        ),
        _t(
            10,
            "Operators authenticate with biometric login on shared devices.",
            "mobile: biometric login",
        ),
        _t(
            11,
            "Marketing links should open specific screens via deep linking.",
            "mobile: deep linking",
        ),
        _t(
            12,
            "Legacy React prototype stays read-only for demos only; production is "
            "Flutter-only going forward.",
            "stack includes React",
        ),
        _t(
            13,
            "Use Flutter Bloc for state management and predictable UI tests.",
            "mobile: Flutter Bloc pattern",
        ),
        _t(
            14,
            "QA needs automated integration tests on simulators and two physical devices.",
            "QA: mobile integration tests",
        ),
        _t(
            15,
            "Wire Sentry for crash reporting and release health in production.",
            "ops: Sentry crash reporting",
        ),
        _t(
            16,
            "Feature flags to roll out scanning workflow gradually per warehouse.",
            "ops: feature flags",
        ),
        _t(
            17,
            "Localise the app in English and Spanish for LATAM sites.",
            "i18n: English and Spanish",
        ),
        _t(
            18,
            "Accessibility target is WCAG 2.1 AA for all operator flows.",
            "a11y: WCAG 2.1 AA",
        ),
        _t(
            19,
            "Beta distribution via TestFlight and Play internal track before GA.",
            "release: TestFlight beta",
        ),
        _t(
            20,
            "Final Atlas estimate on the Flutter mobile scope; ignore the retired "
            "React web delivery except the read-only demo noted earlier.",
            "stack includes Flutter",
        ),
    ]


def _build_contradicting_turns() -> list[StressTurn]:
    """Helix — conflicting budget figures at turns 3 and 8."""
    return [
        _t(
            1,
            "Helix is an internal tooling programme for finance analysts. We need a "
            "first estimate for phase one delivery this fiscal year.",
            "project name: Helix",
        ),
        _t(
            2,
            "Core scope is five engineers for six months building workflow automation "
            "and approval chains.",
            "scope: five engineer team",
        ),
        _t(
            3,
            "Executive steering committee locked the budget at 30,000 EUR total for "
            "phase one — non-negotiable, signed off in yesterday's board note.",
            "budget locked: 30000 EUR",
        ),
        _t(
            4,
            "Integrate LDAP single sign-on with our corporate directory.",
            "feature: LDAP SSO",
        ),
        _t(
            5,
            "Fine-grained role-based permissions for analysts, reviewers, and admins.",
            "feature: RBAC permissions",
        ),
        _t(
            6,
            "Reporting module with scheduled PDF exports to shared drives.",
            "feature: reporting module",
        ),
        _t(
            7,
            "Migrate historical spreadsheets from the legacy Helix macros tool.",
            "feature: legacy data migration",
        ),
        _t(
            8,
            "Budget revision after vendor quotes: steering agreed to raise phase one "
            "funding to 80,000 EUR. Please replan phases against the new ceiling.",
            "budget revised: 80000 EUR",
        ),
        _t(
            9,
            "Extend QA with dedicated regression suite and two UAT cycles.",
            "scope: extended QA phase",
        ),
        _t(
            10,
            "Deploy on Kubernetes in our existing platform cluster.",
            "infra: Kubernetes deployment",
        ),
        _t(
            11,
            "Observability with Prometheus metrics and Grafana dashboards.",
            "ops: Prometheus observability",
        ),
        _t(
            12,
            "Disaster recovery with RPO under four hours for critical workflows.",
            "ops: disaster recovery",
        ),
        _t(
            13,
            "Connect to three external vendor APIs for market data feeds.",
            "feature: vendor APIs",
        ),
        _t(
            14,
            "Admin console for operations to replay failed jobs.",
            "feature: admin console",
        ),
        _t(
            15,
            "Reconfirm the approved phase one budget remains 80,000 EUR after scope "
            "additions — this supersedes the earlier 30k figure.",
            "budget revised: 80000 EUR",
        ),
        _t(
            16,
            "External security review required before production cutover.",
            "security: security review",
        ),
        _t(
            17,
            "UAT sessions with business users in Madrid and London offices.",
            "UAT: business user testing",
        ),
        _t(
            18,
            "Handover pack: runbooks, architecture diagrams, and admin guides.",
            "deliverable: documentation handover",
        ),
        _t(
            19,
            "Include a three-month warranty period for defect fixes post go-live.",
            "support: 3 month warranty",
        ),
        _t(
            20,
            "Final Helix estimate consolidating all functional scope and the latest "
            "budget guidance from steering.",
            "project name: Helix",
        ),
    ]


_PROFILES: dict[ProfileId, StressProfile] = {
    "growing": StressProfile(
        profile_id="growing",
        description=(
            "Requirements accumulate turn by turn on Nimbus CRM; measures cost curve "
            "and whether the original project name survives turn 20."
        ),
        turns=_build_growing_turns(),
    ),
    "pivot": StressProfile(
        profile_id="pivot",
        description=(
            "Atlas pivots from React web to Flutter mobile at turn 5; measures "
            "whether mentioned_technologies updates cleanly or accumulates both stacks."
        ),
        project_type="mobile_app",
        turns=_build_pivot_turns(),
    ),
    "contradicting": StressProfile(
        profile_id="contradicting",
        description=(
            "Helix states a locked 30k EUR budget then revises to 80k EUR; measures "
            "which figure persists in metadata, anchors, or summary."
        ),
        project_type="internal_tool",
        turns=_build_contradicting_turns(),
    ),
}


def get_profile(profile_id: ProfileId) -> StressProfile:
    """Return the full 20-turn script for ``profile_id``."""
    return _PROFILES[profile_id].model_copy(deep=True)


def slice_profile(profile: StressProfile, n: int) -> StressProfile:
    """Return a copy with only the first ``n`` turns (``n`` must be in ``TURN_LENGTHS``)."""
    if n not in TURN_LENGTHS:
        raise ValueError(f"n must be one of {TURN_LENGTHS}, got {n}")
    if n > len(profile.turns):
        raise ValueError(f"profile has {len(profile.turns)} turns, cannot slice to {n}")
    return profile.model_copy(update={"turns": profile.turns[:n]}, deep=True)


def iter_scenario_slices() -> Iterator[tuple[ProfileId, int, StressProfile]]:
    """Yield all (profile_id, n, sliced_profile) combinations — 15 total."""
    for profile_id in PROFILE_IDS:
        full = get_profile(profile_id)
        for n in TURN_LENGTHS:
            yield profile_id, n, slice_profile(full, n)


def facts_introduced_up_to(
    profile: StressProfile, turn_index: int
) -> list[tuple[int, str]]:
    """Facts introduced on turns ``1..turn_index`` (for MemoryDriftMetric).

    Returns ``(intro_turn, fact)`` pairs in turn order. Skips empty facts.
    """
    if turn_index < 1 or turn_index > len(profile.turns):
        raise ValueError(f"turn_index must be 1..{len(profile.turns)}, got {turn_index}")
    out: list[tuple[int, str]] = []
    for turn in profile.turns:
        if turn.turn_index > turn_index:
            break
        if turn.fact_to_remember.strip():
            out.append((turn.turn_index, turn.fact_to_remember.strip()))
    return out


def expected_facts_after_turn(profile: StressProfile, n: int) -> list[tuple[int, str]]:
    """Alias: all facts that should be retained after completing turn ``n``."""
    return facts_introduced_up_to(profile, n)
