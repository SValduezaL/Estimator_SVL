"""Domain-specific Presidio recognizers."""

from __future__ import annotations

from presidio_analyzer import Pattern, PatternRecognizer


class BudgetIdRecognizer(PatternRecognizer):
    """Detects ``BUD-YYYY-NNN`` budget identifiers (S7 schema)."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="BUDGET_ID",
            name="BudgetIdRecognizer",
            patterns=[
                Pattern(
                    name="budget_id_pattern",
                    regex=r"\bBUD-\d{4}-\d{3,4}\b",
                    score=0.95,
                )
            ],
            supported_language="es",
        )


class ClientCodeRecognizer(PatternRecognizer):
    """Detects ``CLI-NNNN`` client codes."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="CLIENT_CODE",
            name="ClientCodeRecognizer",
            patterns=[
                Pattern(
                    name="client_code_pattern",
                    regex=r"\bCLI-\d{4}\b",
                    score=0.95,
                )
            ],
            supported_language="es",
        )
