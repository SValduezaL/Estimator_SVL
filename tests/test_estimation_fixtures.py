"""Los fixtures JSON deben validar como ``EstimationResult`` y cumplir reasoning medium."""

import pytest

from app.fixtures.estimation_examples import load_validated_example
from app.schemas.estimation_common import DetailLevel, ProjectType
from app.services.structured_llm import assert_reasoning_length


@pytest.mark.parametrize("project_type", list(ProjectType))
@pytest.mark.parametrize("scenario", [1, 2, 3])
def test_fixture_validates(project_type: ProjectType, scenario: int) -> None:
    result = load_validated_example(project_type, scenario)
    assert len(result.phases) >= 1
    assert all(len(p.stack) >= 1 for p in result.phases)
    assert_reasoning_length(result, DetailLevel.MEDIUM)
