"""Tests de moderación OpenAI."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.foundation.guardrails.exceptions import InputGuardrailViolation, ModerationUnavailable
from app.foundation.guardrails.input import run_input_guardrails
from app.foundation.guardrails.moderation import check_moderation
from tests.foundation.guardrails.conftest import guardrails_strict_settings


def _mock_client(*, flagged: bool = False, categories: dict | None = None) -> MagicMock:
    cats = categories or {"hate": flagged, "violence": False}
    client = MagicMock()
    result = SimpleNamespace(
        flagged=flagged,
        categories=SimpleNamespace(**cats),
        category_scores=SimpleNamespace(**{k: 0.9 if v else 0.01 for k, v in cats.items()}),
    )
    client.moderations.create.return_value = SimpleNamespace(results=[result])
    return client


def test_moderation_flagged_raises(guardrails_strict_settings) -> None:
    client = _mock_client(flagged=True, categories={"hate": True})
    check = check_moderation("bad text", settings=guardrails_strict_settings, openai_client=client)
    assert not check.passed


def test_moderation_passes(guardrails_strict_settings) -> None:
    client = _mock_client(flagged=False)
    check = check_moderation("ok text", settings=guardrails_strict_settings, openai_client=client)
    assert check.passed


def test_moderation_fail_open(guardrails_strict_settings) -> None:
    guardrails_strict_settings.guardrails_fail_open_on_moderation_error = True
    client = MagicMock()
    client.moderations.create.side_effect = RuntimeError("network")
    check = check_moderation("text", settings=guardrails_strict_settings, openai_client=client)
    assert check.passed


def test_moderation_fail_closed(guardrails_strict_settings) -> None:
    guardrails_strict_settings.guardrails_fail_open_on_moderation_error = False
    client = MagicMock()
    client.moderations.create.side_effect = RuntimeError("network")
    with pytest.raises(ModerationUnavailable):
        check_moderation("text", settings=guardrails_strict_settings, openai_client=client)


def test_run_input_moderation_violation(guardrails_strict_settings) -> None:
    client = _mock_client(flagged=True, categories={"violence": True})
    with pytest.raises(InputGuardrailViolation) as exc:
        run_input_guardrails(
            "Some normal project description here enough length",
            settings=guardrails_strict_settings,
            openai_client=client,
        )
    assert exc.value.reason == "moderation"
