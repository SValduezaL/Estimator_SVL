"""Consistent pseudonymizer — same input → same pseudonym, every time."""

from __future__ import annotations

import hashlib
import hmac
import random
from collections.abc import Callable
from dataclasses import dataclass

from faker import Faker
from presidio_analyzer import AnalyzerEngine

from app.ingestion.pii.mapping_store import MappingStore


@dataclass(frozen=True)
class AppliedMapping:
    entity_type: str
    original_hash: str
    pseudonym: str
    start: int
    end: int


@dataclass(frozen=True)
class PseudonymizationResult:
    pseudonymized_text: str
    applied: list[AppliedMapping]


class ConsistentPseudonymizer:
    def __init__(
        self,
        *,
        analyzer: AnalyzerEngine,
        mapping_store: MappingStore,
        salt: str,
        faker_locale: str = "es_ES",
        language: str = "es",
    ) -> None:
        self._analyzer = analyzer
        self._store = mapping_store
        self._salt = salt.encode("utf-8")
        self._language = language
        self._faker = Faker(faker_locale)
        self._faker.seed_instance(0)
        self._generators: dict[str, Callable[[], str]] = {
            "PERSON": self._faker.name,
            "EMAIL_ADDRESS": self._faker.ascii_company_email,
            "LOCATION": self._faker.city,
            "BUDGET_ID": lambda: f"BUD-{random.randint(2020, 2029)}-{random.randint(0, 9999):04d}",
            "CLIENT_CODE": lambda: f"CLI-{random.randint(0, 9999):04d}",
        }

    def pseudonymize(
        self,
        text: str,
        *,
        entities: list[str] | None = None,
    ) -> PseudonymizationResult:
        results = self._analyzer.analyze(
            text=text,
            language=self._language,
            entities=entities,
        )
        if not results:
            return PseudonymizationResult(pseudonymized_text=text, applied=[])

        results.sort(key=lambda r: r.end, reverse=True)

        out = text
        applied: list[AppliedMapping] = []
        for result in results:
            original_value = text[result.start : result.end]
            entity_type = result.entity_type
            original_hash = self._hash(original_value)
            factory = self._generators.get(entity_type, self._fallback_pseudonym)
            pseudonym = self._store.lookup_or_create(
                entity_type=entity_type,
                original_hash=original_hash,
                new_pseudonym_factory=factory,
            )
            out = out[: result.start] + pseudonym + out[result.end :]
            applied.append(
                AppliedMapping(
                    entity_type=entity_type,
                    original_hash=original_hash,
                    pseudonym=pseudonym,
                    start=result.start,
                    end=result.end,
                )
            )

        return PseudonymizationResult(pseudonymized_text=out, applied=applied)

    def _hash(self, value: str) -> str:
        return hmac.new(self._salt, value.encode("utf-8"), hashlib.sha256).hexdigest()

    def _fallback_pseudonym(self) -> str:
        return f"REDACTED-{self._faker.uuid4()[:8]}"
