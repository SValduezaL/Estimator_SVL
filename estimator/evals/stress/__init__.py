"""Synthetic multi-turn stress scenarios for CAG evaluation."""

from evals.stress.attachment_sizes import (
    ATTACHMENT_SIZE_KB,
    BASELINE_TRANSCRIPT,
    FIXTURES_DIR,
    PDF_FILENAMES,
    RECALL_MARKERS,
)
from evals.stress.metrics import (
    CostBudgetMetric,
    LatencyBudgetMetric,
    MemoryDriftMetric,
)
from evals.stress.observation import SessionSnapshot, TurnObservation
from evals.stress.scenarios import (
    PROFILE_IDS,
    TURN_LENGTHS,
    ProfileId,
    StressProfile,
    StressTurn,
    expected_facts_after_turn,
    facts_introduced_up_to,
    get_profile,
    iter_scenario_slices,
    slice_profile,
)

__all__ = [
    "ATTACHMENT_SIZE_KB",
    "BASELINE_TRANSCRIPT",
    "FIXTURES_DIR",
    "PDF_FILENAMES",
    "RECALL_MARKERS",
    "CostBudgetMetric",
    "LatencyBudgetMetric",
    "MemoryDriftMetric",
    "SessionSnapshot",
    "TurnObservation",
    "PROFILE_IDS",
    "TURN_LENGTHS",
    "ProfileId",
    "StressProfile",
    "StressTurn",
    "expected_facts_after_turn",
    "facts_introduced_up_to",
    "get_profile",
    "iter_scenario_slices",
    "slice_profile",
]
