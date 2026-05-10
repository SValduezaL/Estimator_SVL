# Ejemplos few-shot para CAG: estimaciones de referencia expresadas como datos
# estructurados y como Markdown precomputado (misma fuente de verdad).

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

ExampleFormat = Literal["markdown", "json", "narrative"]


@dataclass
class CanonicalExample:
    """Estimación de referencia en datos estructurados y en Markdown.

    Los campos estructurados (`breakdown`, totales, `team`) son la fuente de verdad
    que usan los formateadores JSON y narrativo. `estimation_markdown` está precomputado
    para que el formateador Markdown reproduzca exactamente la salida esperada.
    """

    title: str
    meeting_summary: str
    breakdown: list[tuple[str, int, int]]
    total_hours: int
    total_cost: int
    team: list[str]
    duration_weeks: int
    estimation_markdown: str


# Tarifas de referencia (EUR/h).
_ONBOARD_HOURLY_EUR = 62
_WOOCOMMERCE_HOURLY_EUR = 58
_FIELD_APP_HOURLY_EUR = 60

CANONICAL_EXAMPLES: list[CanonicalExample] = [
    CanonicalExample(
        title="Módulo de onboarding SaaS B2B",
        meeting_summary=(
            "Startup SaaS B2B solicita un módulo de onboarding con autenticación "
            "email/OAuth, wizard de configuración inicial, gestión de roles básicos "
            "y dashboard de actividad para administradores."
        ),
        breakdown=[
            ("Discovery funcional y arquitectura técnica", 10, 10 * _ONBOARD_HOURLY_EUR),
            ("UI/UX (wireframes + componentes base)", 18, 18 * _ONBOARD_HOURLY_EUR),
            ("Backend API (usuarios, roles, sesiones)", 34, 34 * _ONBOARD_HOURLY_EUR),
            (
                "Autenticación (email + OAuth Google + recuperación de contraseña)",
                20,
                20 * _ONBOARD_HOURLY_EUR,
            ),
            ("Dashboard inicial de actividad y métricas", 16, 16 * _ONBOARD_HOURLY_EUR),
            (
                "QA, pruebas E2E y hardening de seguridad básica",
                18,
                18 * _ONBOARD_HOURLY_EUR,
            ),
            (
                "DevOps ligero (CI, despliegue y observabilidad mínima)",
                8,
                8 * _ONBOARD_HOURLY_EUR,
            ),
        ],
        total_hours=124,
        total_cost=7688,
        team=[
            "1 desarrollador/a full-stack senior",
            "1 QA a tiempo parcial",
        ],
        duration_weeks=5,
        estimation_markdown="""\
## Módulo de onboarding SaaS B2B

### Desglose de tareas

| Tarea | Horas | Coste (EUR) |
|------|------:|------------|
| Discovery funcional y arquitectura técnica | 10 | 620 |
| UI/UX (wireframes + componentes base) | 18 | 1.116 |
| Backend API (usuarios, roles, sesiones) | 34 | 2.108 |
| Autenticación (email + OAuth Google + recuperación de contraseña) | 20 | 1.240 |
| Dashboard inicial de actividad y métricas | 16 | 992 |
| QA, pruebas E2E y hardening de seguridad básica | 18 | 1.116 |
| DevOps ligero (CI, despliegue y observabilidad mínima) | 8 | 496 |

### Totales

- **Total de horas:** 124
- **Coste total:** 7.688 EUR

### Equipo recomendado

- 1 desarrollador/a full-stack senior
- 1 QA a tiempo parcial

### Duración estimada

**5 semanas** con un desarrollador/a full-stack senior y QA a tiempo parcial.""",
    ),
    CanonicalExample(
        title="Plugin eCommerce para WooCommerce (packs y descuentos)",
        meeting_summary=(
            "Comercio online en WooCommerce necesita un plugin a medida para packs "
            "de productos, reglas de descuento por volumen, compatibilidad con cupones, "
            "sincronización de stock y panel de configuración para marketing."
        ),
        breakdown=[
            (
                "Análisis funcional y modelado de reglas de negocio",
                12,
                12 * _WOOCOMMERCE_HOURLY_EUR,
            ),
            (
                "Estructura del plugin (arquitectura, hooks y settings)",
                20,
                20 * _WOOCOMMERCE_HOURLY_EUR,
            ),
            (
                "Lógica de packs, bundles y descuentos por tramos",
                38,
                38 * _WOOCOMMERCE_HOURLY_EUR,
            ),
            ("Compatibilidad con cupones, carrito y checkout", 26, 26 * _WOOCOMMERCE_HOURLY_EUR),
            (
                "Sincronización de stock y validaciones en catálogo",
                18,
                18 * _WOOCOMMERCE_HOURLY_EUR,
            ),
            (
                "Panel admin del plugin (parametrización y mensajes)",
                16,
                16 * _WOOCOMMERCE_HOURLY_EUR,
            ),
            (
                "Testing (unitario/integración), performance y QA en staging",
                24,
                24 * _WOOCOMMERCE_HOURLY_EUR,
            ),
            ("Documentación técnica y handover", 8, 8 * _WOOCOMMERCE_HOURLY_EUR),
        ],
        total_hours=162,
        total_cost=9396,
        team=[
            "1 desarrollador/a WordPress/WooCommerce senior",
            "1 QA a tiempo parcial",
        ],
        duration_weeks=6,
        estimation_markdown="""\
## Plugin eCommerce para WooCommerce (packs y descuentos)

### Desglose de tareas

| Tarea | Horas | Coste (EUR) |
|------|------:|------------|
| Análisis funcional y modelado de reglas de negocio | 12 | 696 |
| Estructura del plugin (arquitectura, hooks y settings) | 20 | 1.160 |
| Lógica de packs, bundles y descuentos por tramos | 38 | 2.204 |
| Compatibilidad con cupones, carrito y checkout | 26 | 1.508 |
| Sincronización de stock y validaciones en catálogo | 18 | 1.044 |
| Panel admin del plugin (parametrización y mensajes) | 16 | 928 |
| Testing (unitario/integración), performance y QA en staging | 24 | 1.392 |
| Documentación técnica y handover | 8 | 464 |

### Totales

- **Total de horas:** 162
- **Coste total:** 9.396 EUR

### Equipo recomendado

- 1 desarrollador/a WordPress/WooCommerce senior
- 1 QA a tiempo parcial

### Duración estimada

**6 semanas** con un perfil WooCommerce senior y QA a tiempo parcial.""",
    ),
    CanonicalExample(
        title="App móvil de inspecciones industriales (offline-first)",
        meeting_summary=(
            "Empresa de mantenimiento industrial necesita una app para técnicos en planta "
            "que registren inspecciones con checklist, fotos y firma digital, funcionando "
            "offline y sincronizando al recuperar cobertura; además un back-office web para "
            "supervisores con reporting básico y exportación a CSV."
        ),
        breakdown=[
            ("Análisis funcional, UX móvil y flujo offline", 14, 14 * _FIELD_APP_HOURLY_EUR),
            ("Modelo de datos y API REST (conflictos, versionado)", 22, 22 * _FIELD_APP_HOURLY_EUR),
            (
                "App móvil: formularios, cámara, almacenamiento local y colas de sync",
                40,
                40 * _FIELD_APP_HOURLY_EUR,
            ),
            ("Sincronización offline/online y resolución de conflictos", 18, 18 * _FIELD_APP_HOURLY_EUR),
            ("Portal web de supervisión y reporting", 24, 24 * _FIELD_APP_HOURLY_EUR),
            ("Autenticación y roles (técnicos / supervisores)", 12, 12 * _FIELD_APP_HOURLY_EUR),
            ("Testing en dispositivos reales y E2E", 20, 20 * _FIELD_APP_HOURLY_EUR),
            ("CI/CD, publicación en stores y hardening", 14, 14 * _FIELD_APP_HOURLY_EUR),
        ],
        total_hours=164,
        total_cost=9840,
        team=[
            "1 desarrollador/a móvil senior",
            "1 desarrollador/a backend mid-level",
            "1 QA a tiempo parcial",
        ],
        duration_weeks=8,
        estimation_markdown="""\
## App móvil de inspecciones industriales (offline-first)

### Desglose de tareas

| Tarea | Horas | Coste (EUR) |
|------|------:|------------|
| Análisis funcional, UX móvil y flujo offline | 14 | 840 |
| Modelo de datos y API REST (conflictos, versionado) | 22 | 1.320 |
| App móvil: formularios, cámara, almacenamiento local y colas de sync | 40 | 2.400 |
| Sincronización offline/online y resolución de conflictos | 18 | 1.080 |
| Portal web de supervisión y reporting | 24 | 1.440 |
| Autenticación y roles (técnicos / supervisores) | 12 | 720 |
| Testing en dispositivos reales y E2E | 20 | 1.200 |
| CI/CD, publicación en stores y hardening | 14 | 840 |

### Totales

- **Total de horas:** 164
- **Coste total:** 9.840 EUR

### Equipo recomendado

- 1 desarrollador/a móvil senior
- 1 desarrollador/a backend mid-level
- 1 QA a tiempo parcial

### Duración estimada

**8 semanas** con núcleo móvil + backend y QA de apoyo.""",
    ),
]


def _format_currency_es(n: int) -> str:
    """Formatea un entero EUR con separador de miles estilo español (punto)."""
    return f"{n:,}".replace(",", ".")


def select_examples(n: int) -> list[CanonicalExample]:
    """Devuelve los primeros n ejemplos canónicos, sin superar los disponibles."""
    return CANONICAL_EXAMPLES[: max(0, min(n, len(CANONICAL_EXAMPLES)))]


def format_examples_for_prompt(
    examples: list[CanonicalExample],
    fmt: ExampleFormat = "markdown",
) -> str:
    """Serializa ejemplos canónicos al formato pedido para inyectarlos en el prompt."""
    if not examples:
        return ""
    if fmt == "markdown":
        return _format_markdown(examples)
    if fmt == "json":
        return _format_json(examples)
    if fmt == "narrative":
        return _format_narrative(examples)
    raise ValueError(f"Formato de ejemplo desconocido: {fmt}")


def _format_markdown(examples: list[CanonicalExample]) -> str:
    parts: list[str] = []
    for i, ex in enumerate(examples, start=1):
        parts.append(
            f"--- EJEMPLO {i} ---\n"
            f"Resumen de la reunión:\n{ex.meeting_summary}\n\n"
            f"Estimación:\n{ex.estimation_markdown}\n"
        )
    return "\n".join(parts)


def _format_json(examples: list[CanonicalExample]) -> str:
    payload = [
        {
            "meeting_summary": ex.meeting_summary,
            "title": ex.title,
            "breakdown": [
                {"task": task, "hours": hours, "cost_eur": cost}
                for task, hours, cost in ex.breakdown
            ],
            "totals": {"hours": ex.total_hours, "cost_eur": ex.total_cost},
            "team": ex.team,
            "duration_weeks": ex.duration_weeks,
        }
        for ex in examples
    ]
    return "Ejemplos de referencia (JSON):\n" + json.dumps(payload, indent=2, ensure_ascii=False)


def _format_narrative(examples: list[CanonicalExample]) -> str:
    parts: list[str] = []
    for i, ex in enumerate(examples, start=1):
        items = "; ".join(f"{task} ({hours} h)" for task, hours, _ in ex.breakdown)
        cost_es = _format_currency_es(ex.total_cost)
        parts.append(
            f"En un proyecto anterior (#{i}), el cliente solicitó: {ex.meeting_summary} "
            f"Propusimos «{ex.title}», estimando {ex.total_hours} horas y un coste de "
            f"{cost_es} EUR en unas {ex.duration_weeks} semanas con el equipo: "
            f"{', '.join(ex.team)}. Principales partidas: {items}."
        )
    return "\n\n".join(parts)
