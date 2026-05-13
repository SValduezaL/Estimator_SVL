"""Servicio de integración LLM para estimaciones con arquitectura CAG.

Este módulo centraliza:
- Contratos de proveedor LLM.
- Adaptadores concretos (OpenAI, Anthropic).
- Normalización de respuesta y uso de tokens en un formato uniforme.

La composición de prompts (system/user) vive en ``app/prompts/`` y se invoca vía
``render_estimation_prompt`` desde ``build_estimation_cache_inputs``.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator, Literal

from anthropic import Anthropic
from openai import OpenAI

from app.config import Settings, get_settings
from app.prompts.loader import render_estimation_prompt
from app.prompts.registry import DEFAULT_ESTIMATION_BUNDLE, PromptBundle
from app.schemas.estimation import EstimationRequest


@dataclass
class TokenUsage:
    """Representa consumo de tokens con desglose entrada/salida/total.
    Attributes:
        input_tokens: Tokens enviados al modelo.
        output_tokens: Tokens generados por el modelo.
        total_tokens: Suma total consumida en la llamada.
    """
    input_tokens: int
    output_tokens: int
    total_tokens: int


@dataclass
class GenerationResult:
    """Payload de salida uniforme para cualquier proveedor LLM.
    Attributes:
        estimation: Texto final de estimación devuelto por el modelo.
        usage: Métricas de consumo de tokens de la llamada.
        finish_reason: Motivo de fin según el proveedor (p. ej. stop, end_turn).
    """
    estimation: str
    usage: TokenUsage
    finish_reason: str


@dataclass
class StreamEvent:
    """Evento normalizado para streaming incremental y cierre con métricas."""

    type: Literal["chunk", "done", "error"]
    data: dict[str, Any]


class BaseProviderClient(ABC):
    """Contrato común para cualquier proveedor LLM integrado en el servicio."""

    @abstractmethod
    def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> GenerationResult:
        """Genera una respuesta del modelo a partir de mensajes estructurados.
        Args:
            model: Identificador del modelo a invocar.
            system_prompt: Instrucciones globales y contexto CAG.
            user_message: Mensaje con la transcripción a estimar.
            temperature: Temperatura de generación.
            max_tokens: Límite máximo de tokens de salida.
        Returns:
            Resultado normalizado con texto y consumo de tokens.
        """

    @abstractmethod
    def stream_generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> Iterator[StreamEvent]:
        """Emite eventos de streaming incremental y cierre con métricas."""


class OpenAIProviderClient(BaseProviderClient):
    """Adaptador OpenAI con patrón de mensajes system/user."""

    def __init__(self, settings: Settings) -> None:
        """Inicializa cliente OpenAI con validación de credenciales."""
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY no configurada en variables de entorno.")
        self.client = OpenAI(api_key=settings.openai_api_key)

    def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> GenerationResult:
        """Llama a Chat Completions y adapta la salida al contrato común.
        Args:
            model: Modelo OpenAI (por ejemplo `gpt-4o-mini`).
            system_prompt: Instrucciones de sistema con contexto CAG.
            user_message: Transcripción a estimar.
            temperature: Temperatura de inferencia.
            max_tokens: Límite de salida para completion.
        Returns:
            `GenerationResult` con estimación y desglose de tokens.
        """
        response = self.client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        usage = response.usage
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        total_tokens = int(getattr(usage, "total_tokens", input_tokens + output_tokens) or 0)
        choice = response.choices[0]
        finish = getattr(choice, "finish_reason", None) or "unknown"
        return GenerationResult(
            estimation=(choice.message.content or "").strip(),
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
            finish_reason=str(finish),
        )

    def stream_generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> Iterator[StreamEvent]:
        """Hace streaming de tokens/chunks usando Chat Completions."""
        stream = self.client.chat.completions.create(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        input_tokens = 0
        output_tokens = 0
        usage_available = False
        for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                usage_available = True
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield StreamEvent(type="chunk", data={"text": str(content)})

        yield StreamEvent(
            type="done",
            data={
                "usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
                "usage_available": usage_available,
            },
        )


class AnthropicProviderClient(BaseProviderClient):
    """Adaptador Anthropic con soporte de system prompt dedicado."""

    def __init__(self, settings: Settings) -> None:
        """Inicializa cliente Anthropic con validación de credenciales."""
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY no configurada en variables de entorno.")
        self.client = Anthropic(api_key=settings.anthropic_api_key)

    def generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> GenerationResult:
        """Llama a Messages API de Anthropic y normaliza el resultado.
        Args:
            model: Modelo Anthropic (por ejemplo `claude-haiku-4-5`).
            system_prompt: Instrucciones de sistema con ejemplos CAG.
            user_message: Mensaje de usuario con la transcripción.
            temperature: Temperatura de generación.
            max_tokens: Límite máximo de tokens de salida.
        Returns:
            `GenerationResult` con texto estimado y tokens de uso.
        """
        response = self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        input_tokens = int(getattr(response.usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(response.usage, "output_tokens", 0) or 0)
        finish = getattr(response, "stop_reason", None) or "unknown"
        return GenerationResult(
            estimation="".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            ).strip(),
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
            finish_reason=str(finish),
        )

    def stream_generate(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> Iterator[StreamEvent]:
        """Hace streaming incremental usando Messages API de Anthropic."""
        with self.client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            for text in stream.text_stream:
                if text:
                    yield StreamEvent(type="chunk", data={"text": text})
            final_message = stream.get_final_message()
            usage = getattr(final_message, "usage", None)
            input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
            output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
            usage_available = usage is not None
            yield StreamEvent(
                type="done",
                data={
                    "usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                    "usage_available": usage_available,
                },
            )


# Registro central: para agregar un nuevo proveedor solo hay que añadir
# un nuevo adaptador y declararlo aqui.
PROVIDER_CLIENTS: dict[str, type[BaseProviderClient]] = {
    "openai": OpenAIProviderClient,
    "anthropic": AnthropicProviderClient,
}


def get_provider_client(settings: Settings) -> BaseProviderClient:
    """Instancia el adaptador LLM según `settings.llm_provider`."""
    provider = settings.llm_provider.lower()
    provider_cls = PROVIDER_CLIENTS.get(provider)
    if not provider_cls:
        available = ", ".join(sorted(PROVIDER_CLIENTS.keys()))
        raise ValueError(
            f"Proveedor '{provider}' no soportado por el servicio. "
            f"Disponibles: {available}."
        )
    return provider_cls(settings)


def build_estimation_cache_inputs(
    *,
    settings: Settings,
    request: EstimationRequest,
    bundle: PromptBundle | None = None,
) -> tuple[str, str, str, int, int | None, PromptBundle]:
    """Textos y parámetros que entran en la clave de caché y en la llamada al modelo."""
    b = bundle or DEFAULT_ESTIMATION_BUNDLE
    system_prompt, user_message = render_estimation_prompt(request, bundle=b)
    opts = request.to_generation_options()
    model = opts.model if opts.model is not None else settings.llm_model
    max_tokens = opts.max_tokens if opts.max_tokens is not None else settings.max_tokens
    return system_prompt, user_message, model, max_tokens, opts.thinking_budget, b