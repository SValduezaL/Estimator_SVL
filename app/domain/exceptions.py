"""Excepciones de dominio para el pipeline de estimación."""


class PromptGuardrailError(Exception):
    """El prompt renderizado no pasó la validación de guardrails."""


class EstimationFailedError(Exception):
    """Fallo irrecuperable en la generación estructurada."""

    def __init__(self, message: str = "Structured estimation failed") -> None:
        super().__init__(message)
        self.message = message
