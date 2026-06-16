"""Presidio AnalyzerEngine factory configured for Spanish text."""

from __future__ import annotations

from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.config import get_settings
from app.ingestion.pii.recognizers import BudgetIdRecognizer, ClientCodeRecognizer


@lru_cache
def build_analyzer() -> AnalyzerEngine:
    settings = get_settings()
    provider = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "es", "model_name": settings.presidio_spacy_model}],
        }
    )
    engine = AnalyzerEngine(
        nlp_engine=provider.create_engine(),
        supported_languages=["es"],
    )
    engine.registry.add_recognizer(BudgetIdRecognizer())
    engine.registry.add_recognizer(ClientCodeRecognizer())
    return engine
