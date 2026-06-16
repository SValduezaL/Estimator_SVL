"""Parser protocol and registry."""

from app.ingestion.parsers.budget_json import BudgetJsonParser
from app.ingestion.parsers.protocol import ParseContext, Parser
from app.ingestion.parsers.registry import ParserRegistry, default_registry
from app.ingestion.parsers.transcript_txt import TranscriptTxtParser

__all__ = [
    "BudgetJsonParser",
    "ParseContext",
    "Parser",
    "ParserRegistry",
    "TranscriptTxtParser",
    "default_registry",
]
