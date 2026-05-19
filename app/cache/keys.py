"""Claves compuestas y buckets de caché."""

from __future__ import annotations

import hashlib
import json

from app.cache.types import CacheBucket, CacheContext
from app.prompts.registry import PromptBundle


def output_format_for_bundle(bundle: PromptBundle) -> str:
    """Formato de salida derivado del bundle (aislamiento entre plantillas)."""
    if bundle.template_subdir in ("v1", "v2"):
        return "line_items"
    return "structured"


def bucket_for_context(ctx: CacheContext) -> CacheBucket:
    if ctx.bucket is not None:
        return ctx.bucket
    return CacheBucket(
        prompt_version=ctx.bundle.public_id,
        project_type=ctx.request.project_type.value,
        detail_level=ctx.request.detail_level.value,
        output_format=output_format_for_bundle(ctx.bundle),
        schema_version=ctx.schema_version,
    )


def normalize_description(description: str) -> str:
    return " ".join(description.strip().split())


def make_exact_key(ctx: CacheContext) -> str:
    """Clave exacta v2 pre-render: bucket + descripción normalizada + parámetros de generación."""
    bucket = bucket_for_context(ctx)
    payload = json.dumps(
        {
            "bucket": bucket.as_tag(),
            "description": normalize_description(ctx.description),
            "model": ctx.model,
            "max_tokens": ctx.max_tokens,
            "thinking_budget": ctx.thinking_budget,
        },
        sort_keys=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"estimation:exact:v2:{ctx.schema_version}:{digest}"
