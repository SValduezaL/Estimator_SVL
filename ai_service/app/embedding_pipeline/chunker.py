"""Structural chunking for normalized budget JSON documents."""

from __future__ import annotations

from typing import Any

import tiktoken

from ai_service.app.embedding_pipeline.schemas import Budget, BudgetComponent, Chunk

EMBEDDING_MODEL_FOR_TOKEN_COUNT = "text-embedding-3-small"


class JSONStructuralChunker:
    """Chunks budget documents at the component level (one component = one chunk)."""

    def __init__(self, model_for_token_count: str = EMBEDDING_MODEL_FOR_TOKEN_COUNT) -> None:
        self._tokenizer = tiktoken.encoding_for_model(model_for_token_count)

    def chunk(self, budgets: list[Budget]) -> list[Chunk]:
        chunks: list[Chunk] = []
        for budget in budgets:
            chunks.extend(self._chunk_one_budget(budget))
        return chunks

    def _chunk_one_budget(self, budget: Budget) -> list[Chunk]:
        parent_context = self._build_parent_context(budget)
        return [
            self._build_chunk(component, budget, parent_context)
            for component in budget.components
        ]

    def _build_parent_context(self, budget: Budget) -> str:
        sector = budget.client_metadata.sector
        return (
            f"[Project: {budget.project_summary}]\n"
            f"[Client sector: {sector} | Year: {budget.year} | "
            f"Main tech: {budget.main_technology}]"
        )

    def _build_chunk(
        self,
        component: BudgetComponent,
        budget: Budget,
        parent_context: str,
    ) -> Chunk:
        text = self._build_chunk_text(component, parent_context)
        return Chunk(
            chunk_id=f"{budget.budget_id}::{component.component_id}",
            text=text,
            metadata=self._build_metadata(component, budget),
            token_count=len(self._tokenizer.encode(text)),
        )

    def _build_chunk_text(self, component: BudgetComponent, parent_context: str) -> str:
        tech_stack = ", ".join(component.tech_stack)
        return (
            f"{parent_context}\n\n"
            f"Component: {component.name}\n"
            f"Description: {component.description}\n"
            f"Tech stack: {tech_stack}\n"
            f"Complexity: {component.complexity}\n"
            f"Estimated hours: {component.estimated_hours}"
        )

    def _build_metadata(self, component: BudgetComponent, budget: Budget) -> dict[str, Any]:
        return {
            "budget_id": budget.budget_id,
            "component_id": component.component_id,
            "component_name": component.name,
            "client_name": budget.client_metadata.name,
            "client_sector": budget.client_metadata.sector,
            "client_country": budget.client_metadata.country,
            "main_technology": budget.main_technology,
            "year": budget.year,
            "complexity": component.complexity,
            "estimated_hours": component.estimated_hours,
        }
