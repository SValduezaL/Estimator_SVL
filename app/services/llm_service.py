"""Servicio de integracion LLM para estimaciones con arquitectura CAG.

Este modulo centraliza:
- Contratos de proveedor LLM.
- Adaptadores concretos (OpenAI, Anthropic).
- Construccion de prompts (system + user) con contexto estatico few-shot.
- Normalizacion de respuesta y uso de tokens en un formato uniforme.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass

from anthropic import Anthropic
from fastapi.concurrency import run_in_threadpool
from openai import OpenAI

from app.config import Settings, get_settings
from app.context.examples import ESTIMATION_EXAMPLES


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
        estimation: Texto final de estimacion devuelto por el modelo.
        usage: Metricas de consumo de tokens de la llamada.
    """
    estimation: str
    usage: TokenUsage


class BaseProviderClient(ABC):
    """Contrato comun para cualquier proveedor LLM integrado en el servicio."""

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
            user_message: Mensaje con la transcripcion a estimar.
            temperature: Temperatura de generacion.
            max_tokens: Limite maximo de tokens de salida.

        Returns:
            Resultado normalizado con texto y consumo de tokens.
        """


class OpenAIProviderClient(BaseProviderClient):
    """Adaptador OpenAI con patron de mensajes system/user."""

    def __init__(self, settings: Settings) -> None:
        """Inicializa cliente OpenAI con validacion de credenciales."""
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
        """Llama a Chat Completions y adapta la salida al contrato comun.

        Args:
            model: Modelo OpenAI (por ejemplo `gpt-4o-mini`).
            system_prompt: Instrucciones de sistema con contexto CAG.
            user_message: Transcripcion a estimar.
            temperature: Temperatura de inferencia.
            max_tokens: Limite de salida para completion.

        Returns:
            `GenerationResult` con estimacion y desglose de tokens.
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
        return GenerationResult(
            estimation=(response.choices[0].message.content or "").strip(),
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
            ),
        )


class AnthropicProviderClient(BaseProviderClient):
    """Adaptador Anthropic con soporte de system prompt dedicado."""

    def __init__(self, settings: Settings) -> None:
        """Inicializa cliente Anthropic con validacion de credenciales."""
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
            user_message: Mensaje de usuario con la transcripcion.
            temperature: Temperatura de generacion.
            max_tokens: Limite maximo de tokens de salida.

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
        return GenerationResult(
            estimation="".join(
                block.text for block in response.content if getattr(block, "type", "") == "text"
            ).strip(),
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
            ),
        )


# Registro central: para agregar un nuevo proveedor solo hay que añadir
# un nuevo adaptador y declararlo aqui.
PROVIDER_CLIENTS: dict[str, type[BaseProviderClient]] = {
    "openai": OpenAIProviderClient,
    "anthropic": AnthropicProviderClient,
}


class LLMService:
    """Encapsula la generacion de estimaciones via LLM usando patron CAG.

    Esta clase orquesta:
    1) Seleccion de proveedor.
    2) Construccion del system prompt con contexto estatico.
    3) Construccion del user message con la transcripcion.
    4) Ejecucion y retorno de un resultado uniforme.
    """

    def __init__(self, *, settings: Settings | None = None) -> None:
        """Inicializa el servicio resolviendo el proveedor configurado.

        Args:
            settings: Configuracion explícita (tests o overrides). Si es None,
                se usa `get_settings()` (cacheado a nivel de proceso).

        Raises:
            ValueError: Si el proveedor no esta registrado en `PROVIDER_CLIENTS`.
        """
        self._settings = settings if settings is not None else get_settings()
        # El proveedor se determina por configuracion y se resuelve contra
        # un registro de adaptadores para facilitar futuras extensiones.
        self.provider = self._settings.llm_provider.lower()
        provider_cls = PROVIDER_CLIENTS.get(self.provider)
        if not provider_cls:
            available = ", ".join(sorted(PROVIDER_CLIENTS.keys()))
            raise ValueError(
                f"Proveedor '{self.provider}' no soportado por el servicio. "
                f"Disponibles: {available}."
            )
        self.client = provider_cls(self._settings)

    def build_system_prompt(self) -> str:
        """Construye el mensaje `system` con instrucciones y ejemplos CAG.

        Returns:
            Prompt de sistema con rol del estimador, formato de salida
            esperado y ejemplos historicos serializados.
        """
        examples_json = json.dumps(ESTIMATION_EXAMPLES, ensure_ascii=True, indent=2)
        return (
            "Eres un estimador senior de software especializado en discovery tecnico, "
            "estimacion por tareas y analisis de riesgos.\n\n"
            "Tu objetivo es generar estimaciones accionables y realistas basadas en "
            "ejemplos historicos y en la transcripcion de una nueva reunion.\n\n"
            "Usa como referencia los siguientes ejemplos historicos:\n"
            f"{examples_json}\n\n"
            "Responde en espanol y con este formato exacto:\n"
            "1) Resumen del requerimiento (max 5 lineas)\n"
            "2) Alcance funcional\n"
            "3) Supuestos\n"
            "4) Riesgos\n"
            "5) Estimacion de esfuerzo en horas (rango)\n"
            "6) Coste estimado (EUR)\n"
            "7) Timeline sugerido (semanas)\n"
            "8) Equipo recomendado\n\n"
            "No inventes integraciones no mencionadas. Si hay ambiguedad, "
            "declara supuestos explicitamente."
        )

    def build_user_message(self, transcription: str) -> str:
        """Construye el mensaje `user` con la transcripcion a estimar.

        Args:
            transcription: Texto bruto de la reunion con el cliente.

        Returns:
            Mensaje final de usuario para enviar al LLM.
        """
        return (
            "Genera una estimacion para la siguiente transcripcion de reunion:\n\n"
            f"{transcription}"
        )

    def estimate(self, transcription: str) -> GenerationResult:
        """Ejecuta el flujo CAG completo y devuelve resultado normalizado.

        Args:
            transcription: Texto de transcripcion usado como input de negocio.

        Returns:
            `GenerationResult` con estimacion y consumo de tokens.
        """
        system_prompt = self.build_system_prompt()
        user_message = self.build_user_message(transcription=transcription)
        return self.client.generate(
            model=self._settings.llm_model,
            system_prompt=system_prompt,
            user_message=user_message,
            temperature=self._settings.temperature,
            max_tokens=self._settings.max_tokens,
        )


async def generate_estimation(
    transcription: str,
    *,
    settings: Settings | None = None,
) -> dict[str, object]:
    """Fachada async para la capa de transporte."""
    service = LLMService(settings=settings)
    result = await run_in_threadpool(service.estimate, transcription)
    return {
        "estimation": result.estimation,
        "usage": {
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "total_tokens": result.usage.total_tokens,
        },
    }
