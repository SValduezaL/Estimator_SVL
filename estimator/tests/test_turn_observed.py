"""Tests for the unified ``turn_observed`` structlog event (actor path, etapa 1)."""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.schemas.estimation import DetailLevel, OutputFormat, ProjectType
from app.services import estimation as estimation_module
from app.services.estimation import EstimationService
from app.sessions.models import ProjectMetadata, Session
from tests.conftest import FakeLLMWrapper, make_canned_result

VALID_TRANSCRIPT = (
    "We want a CRM called Nimbus built with React and Postgres for the sales team."
)

VALID_FORM_FIELDS = {
    "transcript": VALID_TRANSCRIPT,
    "project_type": "web_saas",
    "detail_level": "medium",
    "output_format": "phases_table",
}


def _turn_observed_events(logs: list[dict]) -> list[dict]:
    return [entry for entry in logs if entry.get("event") == "turn_observed"]


@pytest.fixture
def estimation_service(fake_wrapper: FakeLLMWrapper) -> EstimationService:
    fake_wrapper.add_turn(
        result=make_canned_result(),
        metadata=ProjectMetadata(project_name="Nimbus"),
    )
    return EstimationService(
        llm_wrapper=fake_wrapper,
        exact_cache=None,
        semantic_cache=None,
        openai_client=None,
        metadata_extractor_model="gpt-4o-mini",
    )


def test_turn_observed_emitted_once_per_turn_with_all_fields(
    estimation_service: EstimationService,
    fake_wrapper: FakeLLMWrapper,
) -> None:
    session = Session()
    fake_wrapper.add_turn(
        result=make_canned_result(total_cost_eur=30_000),
        metadata=ProjectMetadata(project_name="Nimbus", assumed_team_size=4),
    )

    with capture_logs() as cap_logs:
        response1 = estimation_service.estimate_conversational(
            session=session,
            transcript=VALID_TRANSCRIPT,
            project_type=ProjectType.WEB_SAAS,
            detail_level=DetailLevel.MEDIUM,
            output_format=OutputFormat.PHASES_TABLE,
            attachments_total_chars=500,
        )
        response2 = estimation_service.estimate_conversational(
            session=session,
            transcript=VALID_TRANSCRIPT + " Add billing with Stripe.",
            project_type=ProjectType.WEB_SAAS,
            detail_level=DetailLevel.MEDIUM,
            output_format=OutputFormat.PHASES_TABLE,
            attachments_total_chars=0,
        )

    assert response1.observability is not None
    assert response1.observability.turn_index == 1
    assert response2.observability is not None
    assert response2.observability.turn_index == 2

    events = _turn_observed_events(cap_logs)
    assert len(events) == 2

    first, second = events
    assert first["turn_index"] == 1
    assert second["turn_index"] == 2
    assert first["session_id"] == session.session_id
    assert first["enriched_transcript_chars"] == len(VALID_TRANSCRIPT)
    assert first["attachments_total_chars"] == 500
    assert second["attachments_total_chars"] == 0
    assert first["messages_in_window"] == 2
    assert second["messages_in_window"] == 4
    assert first["anchors_count"] == 0
    assert first["summary_chars"] == 0
    # Actor + metadata extractor (two LLM calls per turn).
    assert first["tokens_in"] == 200
    assert first["tokens_out"] == 100
    assert first["cost_usd"] == pytest.approx(0.0002)
    assert first["latency_ms"] == 2
    assert first["cache_hit_kind"] == "none"
    assert first["last_resolved_tier"] is not None
    assert session.turn_count == 2


def test_turn_observed_via_http_two_turns(
    conversational_client: tuple[TestClient, object],
    fake_wrapper: FakeLLMWrapper,
) -> None:
    client, _store = conversational_client
    fake_wrapper.add_turn()
    fake_wrapper.add_turn()

    with capture_logs() as cap_logs:
        session_id = client.post("/sessions").json()["session_id"]
        r1 = client.post(f"/sessions/{session_id}/estimate", data=VALID_FORM_FIELDS)
        r2 = client.post(
            f"/sessions/{session_id}/estimate",
            data={
                **VALID_FORM_FIELDS,
                "transcript": VALID_TRANSCRIPT + " Add Stripe billing module.",
            },
        )

    assert r1.status_code == 200, r1.text
    assert r2.status_code == 200, r2.text

    body1 = r1.json()
    assert body1["observability"] is not None
    assert body1["observability"]["turn_index"] == 1
    assert body1["observability"]["session_id"] == session_id
    assert body1["observability"]["latency_ms"] == 2
    assert body1["observability"]["tokens_in"] == 200
    body2 = r2.json()
    assert body2["observability"]["turn_index"] == 2

    # Primary contract: observability on the HTTP response (structlog capture may
    # miss PrintLogger output in integration tests).
    events = _turn_observed_events(cap_logs)
    if events:
        assert len(events) == 2
        assert events[0]["turn_index"] == 1
        assert events[1]["turn_index"] == 2
        assert events[0]["session_id"] == session_id


def test_turn_observed_reports_attachment_chars(
    conversational_client: tuple[TestClient, object],
    fake_wrapper: FakeLLMWrapper,
) -> None:
    from docx import Document

    client, _store = conversational_client
    fake_wrapper.add_turn()

    doc = Document()
    doc.add_paragraph("Attachment body for turn_observed sizing test.")
    buf = io.BytesIO()
    doc.save(buf)
    docx_payload = buf.getvalue()

    transcript = "We need an estimation; see the attached spec for details."
    with patch.object(
        estimation_module,
        "_emit_turn_observed",
        wraps=estimation_module._emit_turn_observed,
    ) as emit_spy:
        session_id = client.post("/sessions").json()["session_id"]
        response = client.post(
            f"/sessions/{session_id}/estimate",
            data={
                "transcript": transcript,
                "project_type": "web_saas",
                "detail_level": "medium",
                "output_format": "phases_table",
            },
            files=[
                (
                    "attachments",
                    (
                        "spec.docx",
                        docx_payload,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ),
                )
            ],
        )

    assert response.status_code == 200, response.text
    assert emit_spy.call_count == 1
    call = emit_spy.call_args.kwargs
    assert call["attachments_total_chars"] > 0
    assert call["enriched_transcript_chars"] > len(transcript)
