"""Synthetic multi-turn stress scenarios for CAG evaluation."""

from evals.stress.attachment_sizes import (
    ATTACHMENT_SIZE_KB,
    BASELINE_TRANSCRIPT,
    FIXTURES_DIR,
    PDF_FILENAMES,
    RECALL_MARKERS,
)
from evals.stress.metrics import (
    AttachmentRecallMetric,
    CostBudgetMetric,
    LatencyBudgetMetric,
    MemoryDriftMetric,
    evaluate_memory_drift,
    recall_marker_token,
)
from evals.stress.observation import (
    SessionSnapshot,
    TurnObservation,
    snapshot_from_session_info,
)
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
    "AttachmentRecallMetric",
    "CostBudgetMetric",
    "LatencyBudgetMetric",
    "MemoryDriftMetric",
    "SessionSnapshot",
    "TurnObservation",
    "evaluate_memory_drift",
    "recall_marker_token",
    "snapshot_from_session_info",
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
