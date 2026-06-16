"""Parser for budget JSON using the S7 Budget schema."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, ClassVar

from app.generation.rag.schemas import Budget
from app.ingestion.documents.models import Document, DocumentMetadata
from app.ingestion.loaders.filesystem import LoadedBlob
from app.ingestion.parsers.protocol import ParseContext


class BudgetJsonParser:
    supported_formats: ClassVar[set[str]] = {"json"}

    def parse(self, blob: LoadedBlob, context: ParseContext) -> Iterable[Document]:
        payload = json.loads(blob.bytes_)
        budget = Budget.model_validate(payload)
        text = _render_budget_markdown(budget)
        doc_id = f"{context.source.name}:{budget.budget_id}:{blob.relative_path}"
        yield Document(
            id=doc_id,
            text=text,
            metadata=DocumentMetadata(
                source_name=context.source.name,
                source_version=context.source_version,
                ingested_at=context.ingested_at,
                lineage=list(context.source.lineage),
                sensitivity_pii_flags=list(context.source.sensitivity.pii_flags),
                sensitivity_access_level=context.source.sensitivity.access_level,
                location=blob.relative_path,
                extra={
                    "budget_id": budget.budget_id,
                    "client_sector": budget.client_metadata.sector,
                    "main_technology": budget.main_technology,
                    "year": budget.year,
                    "component_count": len(budget.components),
                },
            ),
        )


def _render_budget_markdown(budget: Budget) -> str:
    lines: list[str] = []
    lines.append(f"# Presupuesto {budget.budget_id}")
    lines.append("")
    lines.append("## Cliente")
    lines.append(f"- Nombre: {budget.client_metadata.name}")
    lines.append(f"- Sector: {budget.client_metadata.sector}")
    lines.append(f"- País: {budget.client_metadata.country}")
    lines.append("")
    lines.append("## Proyecto")
    lines.append(f"- Resumen: {budget.project_summary}")
    lines.append(f"- Tecnología principal: {budget.main_technology}")
    lines.append(f"- Año: {budget.year}")
    lines.append(f"- Horas totales estimadas: {budget.total_estimated_hours}")
    lines.append("")
    lines.append("## Componentes")
    for component in budget.components:
        stack = ", ".join(component.tech_stack)
        deps = ", ".join(component.dependencies) if component.dependencies else "-"
        lines.append(
            f"- **{component.name}** ({component.component_id}) — "
            f"{component.estimated_hours}h · {component.complexity} · [{stack}] · deps: {deps}"
        )
        lines.append(f"  {component.description}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def budget_to_flat_record(budget: Budget) -> dict[str, Any]:
    """Flatten a Budget for tabular cleaning/validation."""
    return {
        "budget_id": budget.budget_id,
        "client_name": budget.client_metadata.name,
        "sector": budget.client_metadata.sector,
        "country": budget.client_metadata.country,
        "project_summary": budget.project_summary,
        "main_technology": budget.main_technology,
        "year": budget.year,
        "total_estimated_hours": budget.total_estimated_hours,
    }
