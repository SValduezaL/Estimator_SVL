"""Validación heurística de la estructura de una estimación en Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


def _parse_money_eur(token: str) -> int:
    """Convierte un literal monetario entero (EUR) a entero, admitiendo . o , como miles."""
    t = token.strip().replace(" ", "")
    if not t:
        raise ValueError("empty")
    if "," in t and "." in t:
        # p. ej. 1.234,56 — no esperado aquí (enteros)
        t = t.replace(".", "").split(",", maxsplit=1)[0]
    elif "," in t:
        parts = t.split(",")
        if len(parts[-1]) == 3 and len(parts) > 1:
            t = "".join(parts)  # miles estilo US: 1,116
        else:
            t = t.replace(",", ".")
            if "." in t:
                t = t.split(".", maxsplit=1)[0]
    else:
        t = t.replace(".", "")  # miles estilo ES: 1.116
    return int(t)


def _table_numeric_cells(body: str) -> tuple[list[int], list[int]]:
    """Extrae listas de horas y costes desde filas de tabla Markdown (3 columnas)."""
    hours_cols: list[int] = []
    cost_cols: list[int] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if set(cells[0]) <= {"-"} or cells[0].lower().startswith("tarea") or cells[0].lower() == "task":
            continue
        try:
            hours_cols.append(int(cells[1]))
            cost_cols.append(_parse_money_eur(cells[2]))
        except (ValueError, IndexError):
            continue
    return hours_cols, cost_cols


# Finalizaciones que tratamos como respuesta completa (no truncada por límite de tokens).
# OpenAI Chat Completions (`finish_reason`): "stop" = mensaje terminado de forma natural.
# Anthropic Messages (`stop_reason`): "end_turn" = turno normal; "stop_sequence" = parada por secuencia configurada.
COMPLETE_FINISH_REASONS: frozenset[str] = frozenset({"stop", "end_turn", "stop_sequence"})


@dataclass
class EstimationStructureResult:
    """Resultado de comprobar título, tabla, totales, equipo, duración y coherencia numérica."""

    has_title: bool = False
    has_breakdown_table: bool = False
    has_totals_section: bool = False
    has_team_section: bool = False
    has_duration_section: bool = False
    declared_total_hours: int | None = None
    sum_row_hours: int | None = None
    hours_match: bool = False
    declared_total_cost: int | None = None
    sum_row_cost: int | None = None
    cost_match: bool = False
    finish_reason_ok: bool = True
    score: float = 0.0
    issues: list[str] = field(default_factory=list)


def evaluate_estimation_structure(text: str, *, finish_reason: str) -> EstimationStructureResult:
    """Analiza texto de estimación y devuelve métricas para scoring y depuración."""
    r = EstimationStructureResult()
    issues: list[str] = []

    if not text or not text.strip():
        r.issues = [
            "empty estimation text",
            "missing title",
            "missing breakdown table",
            "missing totals section",
            "missing team section",
            "missing duration section",
        ]
        r.finish_reason_ok = finish_reason in COMPLETE_FINISH_REASONS
        if not r.finish_reason_ok:
            r.issues.append("truncated output (finish_reason)")
        r.score = 0.0
        return r

    r.has_title = bool(re.search(r"(?m)^##\s+.+", text))
    if not r.has_title:
        issues.append("missing ## title")

    pipe_lines = [ln for ln in text.splitlines() if ln.strip().startswith("|")]
    r.has_breakdown_table = len(pipe_lines) >= 3 and any("---" in ln for ln in pipe_lines)
    if not r.has_breakdown_table:
        issues.append("missing breakdown table")

    r.has_totals_section = bool(
        re.search(r"(?m)^###\s+(Totales|Totals)\s*$", text)
    )
    if not r.has_totals_section:
        issues.append("missing totals section")

    r.has_team_section = bool(
        re.search(r"(?m)^###\s+(Equipo recomendado|Recommended Team)\s*$", text)
    )
    if not r.has_team_section:
        issues.append("missing team section")

    r.has_duration_section = bool(
        re.search(r"(?m)^###\s+(Duración estimada|Estimated Duration)\s*$", text)
    )
    if not r.has_duration_section:
        issues.append("missing duration section")

    # Totales declarados
    m_hours = re.search(
        r"\*\*Total de horas:\*\*\s*(\d+)|\*\*Total hours:\*\*\s*(\d+)",
        text,
        re.IGNORECASE,
    )
    if m_hours:
        r.declared_total_hours = int(next(g for g in m_hours.groups() if g))
    else:
        issues.append("could not parse declared total hours")

    m_cost = re.search(
        r"\*\*Coste total:\*\*\s*([\d.,]+)\s*EUR|\*\*Total cost:\*\*\s*([\d.,]+)\s*EUR",
        text,
        re.IGNORECASE,
    )
    if m_cost:
        raw = next(g for g in m_cost.groups() if g)
        try:
            r.declared_total_cost = _parse_money_eur(raw)
        except ValueError:
            issues.append("could not parse declared total cost")
    else:
        issues.append("could not parse declared total cost")

    # Suma filas de tabla
    table_block = text
    for marker in ("### Totales", "### Totals"):
        if marker in table_block:
            table_block = table_block.split(marker, maxsplit=1)[0]
            break
    h_list, c_list = _table_numeric_cells(table_block)
    if h_list and c_list and len(h_list) == len(c_list):
        r.sum_row_hours = sum(h_list)
        r.sum_row_cost = sum(c_list)
    else:
        r.sum_row_hours = None
        r.sum_row_cost = None
        if r.has_breakdown_table:
            issues.append("could not sum breakdown table rows")

    if (
        r.declared_total_hours is not None
        and r.sum_row_hours is not None
        and r.declared_total_hours == r.sum_row_hours
    ):
        r.hours_match = True
    else:
        r.hours_match = False
        if r.declared_total_hours is not None and r.sum_row_hours is not None:
            issues.append("Total hours mismatch (declared vs table sum)")

    if (
        r.declared_total_cost is not None
        and r.sum_row_cost is not None
        and r.declared_total_cost == r.sum_row_cost
    ):
        r.cost_match = True
    else:
        r.cost_match = False
        if r.declared_total_cost is not None and r.sum_row_cost is not None:
            issues.append("Total cost mismatch (declared vs table sum)")

    r.finish_reason_ok = finish_reason in COMPLETE_FINISH_REASONS
    if not r.finish_reason_ok:
        issues.append("truncated output (finish_reason)")

    r.issues = issues
    r.score = 1.0 if not issues else max(0.0, 1.0 - 0.12 * len(issues))
    return r
