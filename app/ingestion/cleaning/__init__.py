"""Tabular validation and cleaning for budget records."""

from app.ingestion.cleaning.budget_records import clean_budget_records

__all__ = [
    "BudgetRecord",
    "ValidationResult",
    "clean_budget_records",
    "validate_with_policy",
]


def __getattr__(name: str):
    if name == "BudgetRecord":
        from app.ingestion.cleaning.schemas import BudgetRecord

        return BudgetRecord
    if name == "ValidationResult":
        from app.ingestion.cleaning.policy import ValidationResult

        return ValidationResult
    if name == "validate_with_policy":
        from app.ingestion.cleaning.policy import validate_with_policy

        return validate_with_policy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
