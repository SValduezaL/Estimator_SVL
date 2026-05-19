"""Tests de filtros y fallback."""

import json
from pathlib import Path

from app.guardrails.filters import build_safe_fallback, enforce_scope_response
from app.schemas.estimation_common import OUT_OF_SCOPE_PREFIX, DetailLevel, ProjectType
from tests.conftest import _STUB_RESULT

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


def test_enforce_scope_low_confidence() -> None:
    low = _STUB_RESULT.model_copy(
        update={"confidence_pct": 25, "summary": "Alcance muy vago sin prefijo " + "x" * 5}
    )
    out = enforce_scope_response(low)
    assert out.summary.startswith(OUT_OF_SCOPE_PREFIX)
    assert out.total_cost_eur == 0
    assert len(out.phases) == 1


def test_safe_fallback_snapshot() -> None:
    fb = build_safe_fallback(
        project_type=ProjectType.WEB_SAAS,
        detail_level=DetailLevel.MEDIUM,
    )
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    path = SNAPSHOT_DIR / "safe_fallback_medium.json"
    if path.exists():
        expected = json.loads(path.read_text(encoding="utf-8"))
        assert fb.model_dump(mode="json") == expected
    else:
        path.write_text(
            json.dumps(fb.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
