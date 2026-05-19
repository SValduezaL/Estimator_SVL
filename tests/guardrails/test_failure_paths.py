"""Rutas de fallo: moderación caída, reintentos agotados."""

from unittest.mock import MagicMock

import pytest

from app.guardrails.exceptions import ModerationUnavailable
from app.guardrails.moderation import check_moderation
from app.guardrails.types import FailurePolicy
from app.guardrails.types import GuardrailCheckResult
from app.guardrails.validators import validate_cost_coherence
from app.schemas.estimation_output import Phase
from tests.conftest import _STUB_RESULT
from tests.guardrails.conftest import guardrails_strict_settings


def test_moderation_unavailable_fail_closed(guardrails_strict_settings) -> None:
    guardrails_strict_settings.guardrails_fail_open_on_moderation_error = False
    client = MagicMock()
    client.moderations.create.side_effect = OSError("down")
    with pytest.raises(ModerationUnavailable):
        check_moderation("text", settings=guardrails_strict_settings, openai_client=client)


def test_extreme_cost_rate_triggers_retry(guardrails_strict_settings) -> None:
    bad_phase = Phase(
        name="Overpriced",
        deliverable="Entrega con tarifa irreal aquí",
        stack=["COBOL"],
        hours=1,
        cost_eur=100_000,
    )
    bad = _STUB_RESULT.model_copy(
        update={
            "phases": [bad_phase],
            "total_cost_eur": 100_000,
        }
    )
    check = validate_cost_coherence(bad, settings=guardrails_strict_settings)
    assert check.policy == FailurePolicy.RETRY
    assert not check.passed
