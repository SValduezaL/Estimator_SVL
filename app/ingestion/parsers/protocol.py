"""The Parser protocol and ParseContext."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Protocol, runtime_checkable

from app.ingestion.catalog.models import CatalogSource
from app.ingestion.documents.models import Document
from app.ingestion.loaders.filesystem import LoadedBlob


@dataclass(frozen=True)
class ParseContext:
    source: CatalogSource
    source_version: str
    ingested_at: datetime


@runtime_checkable
class Parser(Protocol):
    supported_formats: ClassVar[set[str]]

    def parse(
        self, blob: LoadedBlob, context: ParseContext
    ) -> Iterable[Document]:  # pragma: no cover
        ...
