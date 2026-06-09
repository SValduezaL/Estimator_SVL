"""Interfaz común para estrategias de chunking."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import structlog
import tiktoken
from tiktoken import Encoding
from tiktoken.load import load_tiktoken_bpe

from app.foundation.ssl_utils import configure_ssl_certificates
from app.generation.rag.schemas import Budget, Chunk

log = structlog.get_logger()

_LOCAL_CL100K_BPE = (
    Path(__file__).resolve().parents[4] / "data" / "encodings" / "cl100k_base.tiktoken"
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

_ENCODING: Encoding | None = None


def _get_encoding() -> Encoding:
    global _ENCODING
    if _ENCODING is not None:
        return _ENCODING
    if _LOCAL_CL100K_BPE.is_file():
        mergeable_ranks = load_tiktoken_bpe(
            str(_LOCAL_CL100K_BPE),
            expected_hash=_CL100K_BPE_HASH,
        )
        _ENCODING = Encoding(
            name="cl100k_base",
            pat_str=_CL100K_PAT_STR,
            mergeable_ranks=mergeable_ranks,
            special_tokens=_CL100K_SPECIAL_TOKENS,
        )
        return _ENCODING
    configure_ssl_certificates()
    _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def count_tokens(text: str) -> int:
    return len(_get_encoding().encode(text))


def emit_chunking_done(
    *,
    strategy: str,
    chunks: list[Chunk],
    n_input_documents: int,
    extra_api_calls: int = 0,
    extra_cost_usd: float = 0.0,
    latency_ms: float = 0.0,
) -> None:
    log.info(
        "chunking_done",
        strategy=strategy,
        n_chunks=len(chunks),
        n_input_documents=n_input_documents,
        extra_api_calls=extra_api_calls,
        extra_cost_usd=round(extra_cost_usd, 6),
        latency_ms=round(latency_ms, 1),
    )


class Chunker(ABC):
    last_extra_api_calls: int = 0
    last_extra_cost_usd: float = 0.0

    @abstractmethod
    def chunk(self, budgets: list[Budget]) -> list[Chunk]:
        ...

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        ...
