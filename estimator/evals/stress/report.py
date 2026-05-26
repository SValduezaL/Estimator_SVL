"""Generate REPORT.md from stress run CSV (Block 5)."""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct / 100.0
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return ordered[f]
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _float(row: dict[str, str], key: str) -> float:
    raw = row.get(key, "") or "0"
    try:
        return float(raw)
    except ValueError:
        return 0.0


def _int(row: dict[str, str], key: str) -> int:
    return int(_float(row, key))


def _summary_table(rows: list[dict[str, str]]) -> list[str]:
    groups: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row["scenario"], _int(row, "attachment_size_kb"))
        groups[key].append(row)

    lines = [
        "## Summary by scenario and attachment size",
        "",
        "| scenario | attachment_kb | turns | P50 latency_ms | P95 latency_ms | "
        "mean cost_usd/turn | mean drift score | drift pass rate | "
        "latency budget pass | cost budget pass | attachment recall |",
        "|----------|---------------|-------|----------------|----------------|"
        "--------------------|------------------|-----------------|"
        "---------------------|------------------|-------------------|",
    ]
    for (scenario, size_kb), group in sorted(groups.items()):
        latencies = [_float(r, "latency_ms") for r in group]
        costs = [_float(r, "cost_usd") for r in group]
        drift_scores = [_float(r, "memory_drift_score") for r in group]
        drift_pass = [_int(r, "memory_drift_pass") for r in group]
        lat_pass = [_int(r, "latency_budget_pass") for r in group]
        cost_pass = [_int(r, "cost_budget_pass") for r in group]
        recall_rows = [r for r in group if r.get("attachment_recall_pass", "") != ""]
        recall_pass = [_int(r, "attachment_recall_pass") for r in recall_rows]
        recall_cell = (
            f"{sum(recall_pass) / len(recall_pass):.0%}"
            if recall_pass
            else "n/a"
        )
        lines.append(
            f"| {scenario} | {size_kb} | {len(group)} | "
            f"{statistics.median(latencies):.0f} | {_percentile(latencies, 95):.0f} | "
            f"{statistics.mean(costs):.4f} | {statistics.mean(drift_scores):.2f} | "
            f"{sum(drift_pass) / len(drift_pass):.0%} | "
            f"{sum(lat_pass) / len(lat_pass):.0%} | "
            f"{sum(cost_pass) / len(cost_pass):.0%} | {recall_cell} |"
        )
    return lines


def _latency_vs_tokens(rows: list[dict[str, str]]) -> list[str]:
    bins: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        tokens = _int(row, "tokens_in")
        bucket = (tokens // 500) * 500
        bins[bucket].append(_float(row, "latency_ms"))

    lines = [
        "## Latency vs tokens_in",
        "",
        "| tokens_in bin | samples | mean latency_ms | P95 latency_ms |",
        "|---------------|---------|-----------------|----------------|",
    ]
    for bucket in sorted(bins):
        values = bins[bucket]
        lines.append(
            f"| {bucket}-{bucket + 499} | {len(values)} | "
            f"{statistics.mean(values):.0f} | {_percentile(values, 95):.0f} |"
        )
    return lines


def _cost_vs_turn(rows: list[dict[str, str]]) -> list[str]:
    by_scenario_turn: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        by_scenario_turn[(row["scenario"], _int(row, "turn_index"))].append(
            _float(row, "cost_usd")
        )

    lines = [
        "## Mean cost per turn (by scenario)",
        "",
        "| scenario | turn | mean cost_usd |",
        "|----------|------|---------------|",
    ]
    for key in sorted(by_scenario_turn):
        scenario, turn = key
        values = by_scenario_turn[key]
        lines.append(f"| {scenario} | {turn} | {statistics.mean(values):.4f} |")
    return lines


def _drift_vs_turn(rows: list[dict[str, str]]) -> list[str]:
    by_scenario_turn: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        by_scenario_turn[(row["scenario"], _int(row, "turn_index"))].append(
            _float(row, "memory_drift_score")
        )

    lines = [
        "## Memory drift score vs turn",
        "",
        "| scenario | turn | mean drift score |",
        "|----------|------|------------------|",
    ]
    for key in sorted(by_scenario_turn):
        scenario, turn = key
        values = by_scenario_turn[key]
        lines.append(f"| {scenario} | {turn} | {statistics.mean(values):.2f} |")
    return lines


def _narrative_paragraphs(rows: list[dict[str, str]]) -> list[str]:
    drift_by_turn: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        drift_by_turn[_int(row, "turn_index")].append(_float(row, "memory_drift_score"))

    break_turn = None
    for turn in sorted(drift_by_turn):
        if statistics.mean(drift_by_turn[turn]) < 0.8:
            break_turn = turn
            break

    trunc_note = ""
    for row in rows:
        if _int(row, "attachment_size_kb") == 100 and _int(row, "attachments_total_chars") >= 60_000:
            trunc_note = (
                " At 100 KB attachment size, extracted text hits the 60k character "
                "truncation cap — recall and context pressure are dominated by that limit."
            )
            break

    p1 = "**Memory drift.** "
    if break_turn is not None:
        p1 += (
            f"Mean drift score drops below 0.8 starting at turn {break_turn}; "
            "compression and metadata extraction begin losing earlier facts."
        )
    else:
        p1 += "Mean drift score stays at or above 0.8 across measured turns in this run."

    latencies = [_float(r, "latency_ms") for r in rows]
    costs = [_float(r, "cost_usd") for r in rows]
    p2 = (
        f"**Latency vs cost.** P95 latency is {_percentile(latencies, 95):.0f} ms; "
        f"mean cost per turn is {statistics.mean(costs):.4f} USD."
    )
    if break_turn is not None and break_turn >= 10:
        p2 += " Drift degradation at turn 10+ suggests RAG over full-history replay."
    elif any(_float(r, "memory_drift_score") < 0.5 for r in rows):
        p2 += " Severe drift failures indicate RAG would help anchor long-range facts."
    p2 += trunc_note

    return [
        "## Reading",
        "",
        p1,
        "",
        p2,
        "",
        "_Note: conversational path reports cache_hit_kind=none; exact/semantic cache "
        "rates are expected at 0% here._",
        "",
    ]


def write_report(csv_path: Path, report_path: Path) -> str:
    rows = _read_rows(csv_path)
    sections: list[str] = [
        "# CAG stress evaluation report",
        "",
        f"Source: `{csv_path}` ({len(rows)} turn rows)",
        "",
    ]
    if not rows:
        sections.append("_No data rows._")
    else:
        sections.extend(_summary_table(rows))
        sections.append("")
        sections.extend(_latency_vs_tokens(rows))
        sections.append("")
        sections.extend(_cost_vs_turn(rows))
        sections.append("")
        sections.extend(_drift_vs_turn(rows))
        sections.append("")
        sections.extend(_narrative_paragraphs(rows))

    text = "\n".join(sections) + "\n"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text, encoding="utf-8")
    return text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("evals/stress/results.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evals/stress/REPORT.md"),
    )
    args = parser.parse_args()
    write_report(args.input, args.output)
    print(f"Report written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
