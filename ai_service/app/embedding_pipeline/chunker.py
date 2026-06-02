"""Structural chunking for normalized budget JSON documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tiktoken
from tiktoken import Encoding
from tiktoken.load import load_tiktoken_bpe
from tiktoken.model import encoding_name_for_model

from ai_service.app.embedding_pipeline.schemas import Budget, BudgetComponent, Chunk
from ai_service.app.ssl_utils import configure_ssl_certificates

EMBEDDING_MODEL_FOR_TOKEN_COUNT = "text-embedding-3-small"

_LOCAL_CL100K_BPE = (
    Path(__file__).resolve().parents[2] / "data" / "encodings" / "cl100k_base.tiktoken"
)
_CL100K_BPE_HASH = "223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7"
_CL100K_PAT_STR = (
    r"""'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| """
    r"""?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s"""
)
_CL100K_SPECIAL_TOKENS = {
    "<|endoftext|>": 100257,
    "<|fim_prefix|>": 100258,
    "<|fim_middle|>": 100259,
    "<|fim_suffix|>": 100260,
    "<|endofprompt|>": 100276,
}


def _tokenizer_for_model(model_for_token_count: str) -> Encoding:
    """Load cl100k_base from bundled file when available (avoids SSL download on Windows)."""
    encoding_name = encoding_name_for_model(model_for_token_count)
    if encoding_name == "cl100k_base" and _LOCAL_CL100K_BPE.is_file():
        mergeable_ranks = load_tiktoken_bpe(
            str(_LOCAL_CL100K_BPE),
            expected_hash=_CL100K_BPE_HASH,
        )
        return Encoding(
            name="cl100k_base",
            pat_str=_CL100K_PAT_STR,
            mergeable_ranks=mergeable_ranks,
            special_tokens=_CL100K_SPECIAL_TOKENS,
        )

    configure_ssl_certificates()
    return tiktoken.encoding_for_model(model_for_token_count)


class JSONStructuralChunker:
    """Chunks budget documents at the component level (one component = one chunk)."""

    def __init__(self, model_for_token_count: str = EMBEDDING_MODEL_FOR_TOKEN_COUNT) -> None:
        self._model_for_token_count = model_for_token_count
        self._tokenizer: Encoding | None = None

    @property
    def _encoding(self) -> Encoding:
        if self._tokenizer is None:
            self._tokenizer = _tokenizer_for_model(self._model_for_token_count)
        return self._tokenizer

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
            token_count=len(self._encoding.encode(text)),
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
