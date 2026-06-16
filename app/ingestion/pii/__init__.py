"""GDPR-compliant pseudonymization layer."""

__all__ = [
    "ConsistentPseudonymizer",
    "InMemoryMappingStore",
    "MappingStore",
    "PostgresMappingStore",
    "PseudonymizationResult",
    "build_analyzer",
    "BudgetIdRecognizer",
    "ClientCodeRecognizer",
]


def __getattr__(name: str):
    if name in {"InMemoryMappingStore", "MappingStore", "PostgresMappingStore"}:
        from app.ingestion.pii import mapping_store as mod

        return getattr(mod, name)
    if name in {"ConsistentPseudonymizer", "PseudonymizationResult"}:
        from app.ingestion.pii import pseudonymizer as mod

        return getattr(mod, name)
    if name == "build_analyzer":
        from app.ingestion.pii.analyzer import build_analyzer

        return build_analyzer
    if name == "BudgetIdRecognizer":
        from app.ingestion.pii.recognizers import BudgetIdRecognizer

        return BudgetIdRecognizer
    if name == "ClientCodeRecognizer":
        from app.ingestion.pii.recognizers import ClientCodeRecognizer

        return ClientCodeRecognizer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
