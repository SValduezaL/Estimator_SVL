"""Tipos compartidos del sistema de caché de estimaciones."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

from app.prompts.registry import PromptBundle
from app.schemas.estimation_common import DetailLevel, ProjectType
from app.schemas.estimation_output import EstimationResult
from app.schemas.estimation_request import EstimationRequest


class CacheSource(str, Enum):
    NONE = "none"
    EXACT = "exact"
    SEMANTIC = "semantic"


@dataclass(frozen=True, slots=True)
class CacheBucket:
    """Identificador de aislamiento para búsqueda exacta y semántica."""

    prompt_version: str
    project_type: str
    detail_level: str
    output_format: str
    schema_version: str

    def as_tag(self) -> str:
        return (
            f"{self.prompt_version}"
            f":{self.project_type}"
            f":{self.detail_level}"
            f":{self.output_format}"
            f":{self.schema_version}"
        )


@dataclass(frozen=True, slots=True)
class CacheContext:
    """Contexto de una petición de estimación para lookup/store de caché."""

    request: EstimationRequest
    bundle: PromptBundle
    schema_version: str
    model: str
    max_tokens: int
    thinking_budget: int | None
    skip_cache: bool = False
    bucket: CacheBucket | None = None

    @property
    def description(self) -> str:
        return self.request.description.strip()


@dataclass(frozen=True, slots=True)
class CachedPayload:
    """Valor almacenado en Redis (exacta o semántica)."""

    result: EstimationResult
    model: str
    provider: str
    finish_reason: str
    usage: dict[str, int]
    cost_usd: float
    latency_ms: int = 0

    def to_redis_dict(self) -> dict[str, Any]:
        return {
            "result": self.result.model_dump(mode="json"),
            "model": self.model,
            "provider": self.provider,
            "finish_reason": self.finish_reason,
            "usage": dict(self.usage),
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
        }

    @classmethod
    def from_redis_dict(cls, data: dict[str, Any]) -> CachedPayload:
        raw_result = data.get("result")
        if not isinstance(raw_result, dict):
            raise ValueError("cached payload missing result dict")
        return cls(
            result=EstimationResult.model_validate(raw_result),
            model=str(data.get("model", "")),
            provider=str(data.get("provider", "")),
            finish_reason=str(data.get("finish_reason", "stop")),
            usage={
                "input_tokens": int(data.get("usage", {}).get("input_tokens", 0)),
                "output_tokens": int(data.get("usage", {}).get("output_tokens", 0)),
                "total_tokens": int(data.get("usage", {}).get("total_tokens", 0)),
            },
            cost_usd=float(data.get("cost_usd", 0.0)),
            latency_ms=int(data.get("latency_ms", 0)),
        )


@dataclass(frozen=True, slots=True)
class SemanticMatch:
    similarity: float
    result_json: str


@dataclass(frozen=True, slots=True)
class SemanticLookupResult:
    hit: bool
    payload: CachedPayload | None = None
    similarity: float | None = None
    top_matches: tuple[SemanticMatch, ...] = ()
    log_only_would_hit: bool = False


@dataclass(frozen=True, slots=True)
class CacheLookupResult:
    hit: bool
    source: CacheSource = CacheSource.NONE
    payload: CachedPayload | None = None
    similarity: float | None = None
    embedding: list[float] | None = None
    log_only_would_hit: bool = False

    def to_metrics(
        self,
        *,
        cache_key_model: str,
    ) -> dict[str, Any]:
        if not self.hit or self.payload is None:
            return {
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "finish_reason": "stop",
                "cache_hit": False,
                "cache_source": self.source.value,
                "provider": "",
                "model": cache_key_model,
                "cost_usd": 0.0,
            }
        p = self.payload
        return {
            "usage": dict(p.usage),
            "finish_reason": p.finish_reason,
            "cache_hit": True,
            "cache_source": self.source.value,
            "provider": p.provider,
            "model": p.model,
            "cost_usd": p.cost_usd,
            "semantic_similarity": self.similarity,
        }


CacheSourceLiteral = Literal["none", "exact", "semantic"]
