"""Unit tests for synthetic stress scenarios (Block 2 — data only)."""

from __future__ import annotations

import pytest

from evals.stress import (
    PROFILE_IDS,
    TURN_LENGTHS,
    expected_facts_after_turn,
    facts_introduced_up_to,
    get_profile,
    iter_scenario_slices,
    slice_profile,
)


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_profile_has_twenty_turns_with_contiguous_indices(profile_id: str) -> None:
    profile = get_profile(profile_id)  # type: ignore[arg-type]
    assert len(profile.turns) == 20
    assert [t.turn_index for t in profile.turns] == list(range(1, 21))


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_all_transcripts_meet_min_length(profile_id: str) -> None:
    profile = get_profile(profile_id)  # type: ignore[arg-type]
    for turn in profile.turns:
        assert len(turn.transcript) >= 20, f"turn {turn.turn_index} too short"


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
@pytest.mark.parametrize("n", TURN_LENGTHS)
def test_slice_profile_returns_first_n_turns(profile_id: str, n: int) -> None:
    full = get_profile(profile_id)  # type: ignore[arg-type]
    sliced = slice_profile(full, n)
    assert len(sliced.turns) == n
    assert [t.turn_index for t in sliced.turns] == list(range(1, n + 1))


def test_slice_profile_rejects_invalid_n() -> None:
    profile = get_profile("growing")
    with pytest.raises(ValueError, match="n must be one of"):
        slice_profile(profile, 7)


def test_iter_scenario_slices_yields_fifteen_combinations() -> None:
    combos = list(iter_scenario_slices())
    assert len(combos) == len(PROFILE_IDS) * len(TURN_LENGTHS) == 15
    ids = {(pid, n) for pid, n, _ in combos}
    assert len(ids) == 15


def test_growing_facts_include_nimbus_at_turn_20() -> None:
    profile = get_profile("growing")
    facts = facts_introduced_up_to(profile, 20)
    nimbus_facts = [(i, f) for i, f in facts if "Nimbus" in f]
    assert any(i == 1 for i, _ in nimbus_facts)
    assert any(i == 20 for i, _ in nimbus_facts)


def test_pivot_flutter_introduced_at_turn_5_and_persists_to_10() -> None:
    profile = get_profile("pivot")
    facts_at_10 = facts_introduced_up_to(profile, 10)
    intro_turns = {i for i, f in facts_at_10 if "Flutter" in f}
    assert 5 in intro_turns
    assert any(i == 1 and "Atlas" in f for i, f in facts_at_10)
    assert any(i <= 5 and "React" in f for i, f in facts_at_10)


def test_contradicting_exposes_both_budget_facts_at_turn_20() -> None:
    profile = get_profile("contradicting")
    facts = facts_introduced_up_to(profile, 20)
    budget_facts = [(i, f) for i, f in facts if "budget" in f.lower()]
    assert any(i == 3 and "30000" in f for i, f in budget_facts)
    assert any(i == 8 and "80000" in f for i, f in budget_facts)
    assert expected_facts_after_turn(profile, 20) == facts


def test_pivot_uses_mobile_app_project_type() -> None:
    assert get_profile("pivot").project_type == "mobile_app"


def test_contradicting_uses_internal_tool_project_type() -> None:
    assert get_profile("contradicting").project_type == "internal_tool"
