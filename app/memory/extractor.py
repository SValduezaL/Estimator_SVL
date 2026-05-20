"""Actualización de ProjectMetadata mediante extractor LLM (OpenAI Responses API)."""

from __future__ import annotations

import json
from typing import Any

import structlog
from pydantic import ValidationError

from app.memory.exceptions import MetadataExtractionError
from app.memory.models import ProjectMetadata

log = structlog.get_logger(__name__)

EXTRACTION_PROMPT = """
You receive the current ProjectMetadata of a software estimation session
and the latest conversation turn.

Your task:
produce an updated ProjectMetadata that incorporates
any new facts revealed in the turn.

Rules:
- Only update fields when the turn provides clear evidence.
- Preserve existing values unless explicitly revised.
- If the user retracts a previous fact, remove it.
- For lists, append new items without duplicates.
- Never invent information.
- Never infer technologies that were not explicitly mentioned.
- Never overwrite valid data with weaker assumptions.

Current metadata:
{current_metadata_json}

Latest turn:

USER:
{user_turn}

ASSISTANT:
{assistant_turn}

Return ONLY valid JSON matching the ProjectMetadata schema.
"""


def _metadata_json_schema() -> dict[str, Any]:
    """Schema compatible con OpenAI Responses ``json_schema`` + ``strict: true``."""
    return {
        "type": "object",
        "properties": {
            "project_name": {"type": ["string", "null"]},
            "assumed_team_size": {"type": ["integer", "null"]},
            "mentioned_technologies": {
                "type": "array",
                "items": {"type": "string"},
            },
            "agreed_scope": {"type": ["string", "null"]},
            "explicit_constraints": {
                "type": "array",
                "items": {"type": "string"},
            },
            "rejected_options": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": [
            "project_name",
            "assumed_team_size",
            "mentioned_technologies",
            "agreed_scope",
            "explicit_constraints",
            "rejected_options",
        ],
        "additionalProperties": False,
    }


def _parse_response_output(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text).strip()

    output = getattr(response, "output", None) or []
    chunks: list[str] = []
    for item in output:
        content = getattr(item, "content", None) or []
        for block in content:
            text = getattr(block, "text", None)
            if text:
                chunks.append(str(text))
    if not chunks:
        raise MetadataExtractionError("Extractor response contained no text output")
    return "\n".join(chunks).strip()


async def update_metadata_llm(
    metadata: ProjectMetadata,
    user_turn: str,
    assistant_turn: str,
    client: Any,
) -> ProjectMetadata:
    """Actualiza metadata con OpenAI Responses API y salida JSON estructurada."""
    if client is None:
        raise MetadataExtractionError("OpenAI client is not configured")

    prompt = EXTRACTION_PROMPT.format(
        current_metadata_json=metadata.model_dump_json(),
        user_turn=user_turn,
        assistant_turn=assistant_turn,
    )

    log.info(
        "metadata_extraction_started",
        log_category="technical",
        user_turn_chars=len(user_turn),
        assistant_turn_chars=len(assistant_turn),
        metadata_empty=metadata.is_empty(),
    )

    try:
        response = await client.responses.create(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": prompt}],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "project_metadata",
                    "schema": _metadata_json_schema(),
                    "strict": True,
                }
            },
        )
        raw_json = _parse_response_output(response)
        parsed = json.loads(raw_json)
        updated = ProjectMetadata.model_validate(parsed)
    except MetadataExtractionError:
        raise
    except (json.JSONDecodeError, ValidationError) as exc:
        log.error(
            "metadata_extraction_validation_failed",
            log_category="technical",
            error_recoverable=False,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )
        raise MetadataExtractionError("Invalid metadata JSON from extractor") from exc
    except Exception as exc:
        log.error(
            "metadata_extraction_failed",
            log_category="technical",
            error_recoverable=False,
            error_type=type(exc).__name__,
            error_message=str(exc),
            exc_info=True,
        )
        detail = str(exc) or type(exc).__name__
        raise MetadataExtractionError(
            f"Metadata extraction LLM call failed: {detail}"
        ) from exc

    log.info(
        "metadata_extraction_completed",
        log_category="technical",
        metadata_empty=updated.is_empty(),
        technologies_count=len(updated.mentioned_technologies),
        constraints_count=len(updated.explicit_constraints),
        rejected_count=len(updated.rejected_options),
    )
    return updated
