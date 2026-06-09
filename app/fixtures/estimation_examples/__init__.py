"""Ejemplos JSON canónicos de ``EstimationResult`` por project_type."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.domain.schemas.estimation_common import ProjectType
from app.domain.schemas.estimation_output import EstimationResult

_EXAMPLES_DIR = Path(__file__).resolve().parent


@lru_cache
def load_example_json(project_type: str, scenario: int) -> dict:
    path = _EXAMPLES_DIR / project_type / f"scenario_{scenario}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_validated_example(project_type: ProjectType, scenario: int) -> EstimationResult:
    data = load_example_json(project_type.value, scenario)
    return EstimationResult.model_validate(data)


def few_shot_json_block(project_type: ProjectType, scenario: int) -> str:
    """JSON compacto para inyectar en prompts."""
    data = load_example_json(project_type.value, scenario)
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
