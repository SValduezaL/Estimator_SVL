"""Pydantic models for budget ingest and embedding pipeline (S7)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ClientSector = Literal["finance", "ecommerce", "healthcare", "industrial"]

ComponentComplexity = Literal["low", "medium", "high"]

MainTechnology = Literal[
    "ruby_on_rails",
    "node_express",
    "java_spring_boot",
    "nextjs",
    "django",
    "laravel",
    "dotnet",
    "python_fastapi",
    "go",
    "azure_functions",
    "react_native",
    "elixir_phoenix",
]


class ClientMetadata(BaseModel):
    name: str = Field(min_length=1)
    sector: ClientSector
    country: str = Field(min_length=2, max_length=3)


class BudgetComponent(BaseModel):
    component_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    tech_stack: list[str] = Field(min_length=1)
    estimated_hours: int = Field(ge=1)
    complexity: ComponentComplexity
    dependencies: list[str] = Field(default_factory=list)

    @field_validator("tech_stack")
    @classmethod
    def validate_tech_stack_items(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if not cleaned:
            raise ValueError("tech_stack must contain at least one non-empty item")
        return cleaned


class Budget(BaseModel):
    budget_id: str = Field(min_length=1)
    client_metadata: ClientMetadata
    project_summary: str = Field(min_length=1)
    main_technology: MainTechnology
    year: int = Field(ge=2000, le=2100)
    total_estimated_hours: int = Field(ge=1)
    components: list[BudgetComponent] = Field(min_length=1)


class Chunk(BaseModel):
    chunk_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    metadata: dict[str, Any]
    token_count: int = Field(ge=0)


class EmbeddedChunk(Chunk):
    embedding: list[float] = Field(min_length=1)


class IngestRequest(BaseModel):
    budgets: list[Budget] = Field(min_length=1)


class IngestStats(BaseModel):
    total_budgets: int = Field(ge=0)
    total_chunks: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0.0)


class IngestResponse(BaseModel):
    chunks: list[EmbeddedChunk]
    stats: IngestStats
