"""Servicio de integración LLM para estimaciones con arquitectura CAG.

Este módulo centraliza:
- Contratos de proveedor LLM.
- Adaptadores concretos (OpenAI, Anthropic).
- Construcción de prompts (system + user) con contexto estático few-shot.
- Normalización de respuesta y uso de tokens en un formato uniforme.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator, Literal

from anthropic import Anthropic
from openai import OpenAI

from app.config import Settings, get_settings
from app.context.examples import (
    CANONICAL_EXAMPLES,
    ExampleFormat,
    format_examples_for_prompt,
    select_examples,
)


class LLMServiceError(Exception):
    """Error de negocio al generar una estimación (p. ej. proveedor o validación)."""


@dataclass
class GenerationOptions:
    """Opciones por solicitud para construir el prompt y la llamada al LLM."""

    preprocessing: str = "none"
    example_format: ExampleFormat = "markdown"
    num_examples: int | None = None
    use_examples: bool = True
    model: str | None = None
    max_tokens: int | None = None
    thinking_budget: int | None = None
    skip_cache: bool = False


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


def build_system_prompt(opts: GenerationOptions | None = None) -> str:
    """Construye el mensaje `system` con instrucciones y ejemplos CAG."""
    opts = opts or GenerationOptions()
    if not opts.use_examples:
        examples_block = ""
    else:
        n = len(CANONICAL_EXAMPLES) if opts.num_examples is None else opts.num_examples
        examples_block = format_examples_for_prompt(select_examples(n), fmt=opts.example_format)

    examples_section = (
        f"Usa como referencia los siguientes ejemplos históricos:\n{examples_block}\n\n"
        if examples_block
        else ""
    )
    return (
        "Eres un estimador senior de software especializado en discovery técnico, "
        "estimación por tareas y análisis de riesgos.\n\n"
        "Tu objetivo es generar estimaciones accionables y realistas basadas en "
        "ejemplos históricos y en la transcripción de una nueva reunion.\n\n"
        f"{examples_section}"
        "Responde en español y con este formato exacto:\n"
        "1) Resumen del requerimiento (max 5 lineas)\n"
        "2) Alcance funcional\n"
        "3) Supuestos\n"
        "4) Riesgos\n"
        "5) Estimación de esfuerzo en horas (rango)\n"
        "6) Coste estimado (EUR)\n"
        "7) Timeline sugerido (semanas)\n"
        "8) Equipo recomendado\n\n"
        "No inventes integraciones no mencionadas. Si hay ambigüedad, "
        "declara supuestos explícitamente."
    )


def build_estimation_user_message(transcription: str) -> str:
    """Mensaje de usuario estándar para estimación (alineado con `LLMService.build_user_message`)."""
    return (
        "Genera una estimación para la siguiente transcripción de reunión:\n\n"
        f"{transcription}"
    )


def build_estimation_cache_inputs(
    *,
    settings: Settings,
    transcription: str,
    opts: GenerationOptions,
) -> tuple[str, str, str, int, int | None]:
    """Textos y parámetros que entran en la clave de caché y en la llamada al modelo."""
    system_prompt = build_system_prompt(opts)
    user_message = build_estimation_user_message(transcription)
    model = opts.model if opts.model is not None else settings.llm_model
    max_tokens = opts.max_tokens if opts.max_tokens is not None else settings.max_tokens
    return system_prompt, user_message, model, max_tokens, opts.thinking_budget


class LLMService:
    """Encapsula la generación de estimaciones via LLM usando patron CAG.
    Esta clase orquesta:
    1) Seleccion de proveedor.
    2) Construcción del system prompt con contexto estático.
    3) Construcción del user message con la transcripción.
    4) Ejecución y retorno de un resultado uniforme.
    """

    def __init__(self, *, settings: Settings | None = None) -> None:
        """Inicializa el servicio resolviendo el proveedor configurado.
        Args:
            settings: Configuración explícita (tests o overrides). Si es None,
                se usa `get_settings()` (cacheado a nivel de proceso).
        Raises:
            ValueError: Si el proveedor no esta registrado en `PROVIDER_CLIENTS`.
        """
        self._settings = settings if settings is not None else get_settings()
        self.client = get_provider_client(self._settings)

    @staticmethod
    def build_system_prompt(opts: GenerationOptions | None = None) -> str:
        """Delega en `build_system_prompt` de módulo (compatibilidad)."""
        return build_system_prompt(opts)

    def build_user_message(self, transcription: str) -> str:
        """Construye el mensaje `user` con la transcripción a estimar.
        Args:
            transcription: Texto bruto de la reunion con el cliente.
        Returns:
            Mensaje final de usuario para enviar al LLM.
        """
        return build_estimation_user_message(transcription)

    def estimate(self, transcription: str, *, opts: GenerationOptions | None = None) -> GenerationResult:
        """Ejecuta el flujo CAG completo y devuelve resultado normalizado.
        Args:
            transcription: Texto de transcripción usado como input de negocio.
            opts: Opciones de generación; por defecto todas las predeterminadas.
        Returns:
            `GenerationResult` con estimación y consumo de tokens.
        """
        opts = opts or GenerationOptions()
        system_prompt = build_system_prompt(opts)
        user_message = self.build_user_message(transcription=transcription)
        model = opts.model if opts.model is not None else self._settings.llm_model
        max_tokens = opts.max_tokens if opts.max_tokens is not None else self._settings.max_tokens
        return self.client.generate(
            model=model,
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=self._settings.temperature,
            max_tokens=max_tokens,
        )

    def stream_estimate(
        self,
        transcription: str,
        *,
        opts: GenerationOptions | None = None,
    ) -> Iterator[StreamEvent]:
        """Ejecuta flujo CAG completo en modo streaming incremental."""
        opts = opts or GenerationOptions()
        system_prompt = build_system_prompt(opts)
        user_message = self.build_user_message(transcription=transcription)
        model = opts.model if opts.model is not None else self._settings.llm_model
        max_tokens = opts.max_tokens if opts.max_tokens is not None else self._settings.max_tokens
        start_time = time.perf_counter()
        done_sent = False
        for event in self.client.stream_generate(
            model=model,
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=self._settings.temperature,
            max_tokens=max_tokens,
        ):
            if event.type == "done":
                done_sent = True
                merged_data = dict(event.data)
                merged_data["model"] = model
                merged_data["response_seconds"] = time.perf_counter() - start_time
                yield StreamEvent(type="done", data=merged_data)
                continue
            yield event

        if not done_sent:
            yield StreamEvent(
                type="done",
                data={
                    "model": model,
                    "response_seconds": time.perf_counter() - start_time,
                    "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                    "usage_available": False,
                },
            )


def generate_estimation(
    transcription: str,
    opts: GenerationOptions,
    *,
    settings: Settings | None = None,
    llm_wrapper: Any,
) -> dict[str, Any]:
    """Ejecuta estimación síncrona vía LiteLLM (wrapper); elevando `LLMServiceError` ante errores."""
    if opts.preprocessing != "none":
        raise LLMServiceError(
            f"Solo se admite preprocessing='none'; recibido: {opts.preprocessing!r}."
        )
    settings = settings if settings is not None else get_settings()
    system_prompt, user_message, _model, max_tokens, thinking_budget = build_estimation_cache_inputs(
        settings=settings,
        transcription=transcription,
        opts=opts,
    )

    try:
        raw = llm_wrapper.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            model_override=opts.model,
            max_tokens=max_tokens,
            thinking_budget=thinking_budget,
            skip_cache=opts.skip_cache,
        )
    except ValueError as exc:
        raise LLMServiceError(str(exc)) from exc
    except Exception as exc:  # pragma: no cover - APIs externas
        raise LLMServiceError(f"Fallo al llamar al proveedor LLM: {exc}") from exc

    return raw