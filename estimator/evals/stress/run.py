"""CLI runner for multi-turn CAG stress evaluation (Block 5).

Usage::

    uv run python -m evals.stress.run --scenarios growing --attachment-sizes 0 --repeats 1 --max-turns 3
    uv run python -m evals.stress.run --http http://localhost:8000 --scenarios growing,pivot
    uv run python -m evals.stress.run --http http://localhost:8000 --resume --output /tmp/results.csv

Each turn appends one row to the CSV (flush + fsync). Use ``--resume`` after a crash
to skip cells already present in the output file.
"""

from __future__ import annotations

import argparse
import csv
import os
import signal
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable  # noqa: TC003 — used in type hints for callables

import httpx
from fastapi.testclient import TestClient

from app.dependencies import get_session_store
from app.main import app
from app.schemas.estimation import EstimationResult
from app.sessions.store import SessionStore
from evals.stress.attachment_sizes import (
    ATTACHMENT_SIZE_KB,
    FIXTURES_DIR,
    PDF_FILENAMES,
    RECALL_MARKERS,
)
from evals.stress.fixtures.build_pdfs import build_all
from evals.stress.metrics import (
    AttachmentRecallMetric,
    CostBudgetMetric,
    LatencyBudgetMetric,
    evaluate_memory_drift,
    recall_marker_token,
)
from evals.stress.observation import TurnObservation, snapshot_from_session_info
from evals.stress.scenarios import ProfileId, StressProfile, facts_introduced_up_to, get_profile

_PROFILE_ALIASES: dict[str, ProfileId] = {
    "growing": "growing",
    "pivot": "pivot",
    "contradicting": "contradicting",
    "contradiction": "contradicting",
}

CSV_FIELDNAMES: list[str] = [
    "run_id",
    "scenario",
    "attachment_size_kb",
    "repeat",
    "turn_index",
    "session_id",
    "enriched_transcript_chars",
    "attachments_total_chars",
    "messages_in_window",
    "anchors_count",
    "summary_chars",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "latency_ms",
    "cache_hit_kind",
    "last_resolved_tier",
    "memory_drift_pass",
    "memory_drift_score",
    "latency_budget_pass",
    "cost_budget_pass",
    "attachment_recall_pass",
    "estimation_cached",
    "http_status",
    "error_type",
    "error_message",
]


@dataclass(frozen=True)
class TurnMatrixKey:
    """Stable id for one cell in the stress matrix (used for --resume)."""

    scenario: str
    attachment_size_kb: int
    repeat: int
    turn_index: int


@dataclass
class StressRunConfig:
    scenarios: list[ProfileId]
    attachment_sizes: list[int]
    repeats: int
    max_turns: int
    latency_budget_ms: int
    cost_budget_usd: float
    output: Path
    report: Path | None
    http_base: str | None
    resume: bool = False


def _normalize_scenarios(raw: str) -> list[ProfileId]:
    ids: list[ProfileId] = []
    for part in raw.split(","):
        key = part.strip().lower()
        if not key:
            continue
        if key not in _PROFILE_ALIASES:
            raise ValueError(f"unknown scenario {part!r}; expected one of {list(_PROFILE_ALIASES)}")
        profile_id = _PROFILE_ALIASES[key]
        if profile_id not in ids:
            ids.append(profile_id)
    if not ids:
        raise ValueError("at least one scenario is required")
    return ids


def _normalize_sizes(raw: str) -> list[int]:
    sizes: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        size = int(part)
        if size not in ATTACHMENT_SIZE_KB:
            raise ValueError(f"attachment size {size} not in {ATTACHMENT_SIZE_KB}")
        if size not in sizes:
            sizes.append(size)
    if not sizes:
        raise ValueError("at least one attachment size is required")
    return sizes


def _phases_text(result: EstimationResult) -> str:
    return "\n".join(p.summary for p in result.phases)


def _row_from_turn(
    *,
    run_id: str,
    scenario: str,
    attachment_size_kb: int,
    repeat: int,
    turn_index: int,
    session_id: str,
    observability: dict[str, Any],
    memory_drift_pass: bool,
    memory_drift_score: float,
    latency_budget_pass: bool,
    cost_budget_pass: bool,
    attachment_recall_pass: str,
    estimation_cached: bool,
    http_status: int | None = None,
    error_type: str = "",
    error_message: str = "",
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "scenario": scenario,
        "attachment_size_kb": attachment_size_kb,
        "repeat": repeat,
        "turn_index": turn_index,
        "session_id": session_id,
        "enriched_transcript_chars": observability.get("enriched_transcript_chars", 0),
        "attachments_total_chars": observability.get("attachments_total_chars", 0),
        "messages_in_window": observability.get("messages_in_window", 0),
        "anchors_count": observability.get("anchors_count", 0),
        "summary_chars": observability.get("summary_chars", 0),
        "tokens_in": observability.get("tokens_in", 0),
        "tokens_out": observability.get("tokens_out", 0),
        "cost_usd": observability.get("cost_usd", 0.0),
        "latency_ms": observability.get("latency_ms", 0),
        "cache_hit_kind": observability.get("cache_hit_kind", "none"),
        "last_resolved_tier": observability.get("last_resolved_tier"),
        "memory_drift_pass": int(memory_drift_pass),
        "memory_drift_score": round(memory_drift_score, 4),
        "latency_budget_pass": int(latency_budget_pass),
        "cost_budget_pass": int(cost_budget_pass),
        "attachment_recall_pass": attachment_recall_pass,
        "estimation_cached": int(estimation_cached),
        "http_status": "" if http_status is None else http_status,
        "error_type": error_type,
        "error_message": error_message,
    }


def _truncate_error_message(message: str, *, limit: int = 400) -> str:
    msg = message.strip().replace("\n", " ")
    return msg[:limit]


def _matrix_key_from_row(row: dict[str, Any]) -> TurnMatrixKey:
    return TurnMatrixKey(
        scenario=str(row["scenario"]),
        attachment_size_kb=int(row["attachment_size_kb"]),
        repeat=int(row["repeat"]),
        turn_index=int(row["turn_index"]),
    )


class IncrementalCsvWriter:
    """Append one CSV row per turn with flush/fsync so crashes keep partial results."""

    def __init__(self, path: Path, *, resume: bool) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done: set[TurnMatrixKey] = set()
        self._file = None
        self._writer: csv.DictWriter | None = None

        if resume and self.path.exists() and self.path.stat().st_size > 0:
            with self.path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                if list(reader.fieldnames or []) != CSV_FIELDNAMES:
                    raise ValueError(
                        f"{self.path} header mismatch; delete the file or run without --resume"
                    )
                for existing in reader:
                    self._done.add(_matrix_key_from_row(existing))
            self._file = self.path.open("a", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=CSV_FIELDNAMES)
        else:
            self._file = self.path.open("w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=CSV_FIELDNAMES)
            self._writer.writeheader()
            self._flush()

    def is_done(self, key: TurnMatrixKey) -> bool:
        return key in self._done

    def append(self, row: dict[str, Any]) -> None:
        key = _matrix_key_from_row(row)
        if key in self._done:
            return
        assert self._writer is not None and self._file is not None
        self._writer.writerow(row)
        self._flush()
        self._done.add(key)

    def _flush(self) -> None:
        assert self._file is not None
        self._file.flush()
        os.fsync(self._file.fileno())

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
            self._writer = None

    @property
    def rows_on_disk(self) -> int:
        return len(self._done)


def _read_csv_rows(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _evaluate_turn_metrics(
    *,
    profile: StressProfile,
    turn_index: int,
    snapshot,
    result: EstimationResult,
    observability: dict[str, Any] | None,
    attachment_size_kb: int,
    latency_budget_ms: int,
    cost_budget_usd: float,
) -> tuple[bool, float, bool, bool, str]:
    facts = facts_introduced_up_to(profile, turn_index)
    drift_pass, drift_score = evaluate_memory_drift(snapshot, facts)

    obs = observability or {}
    turn_obs = TurnObservation(
        latency_ms=int(obs.get("latency_ms", 0)),
        cost_usd=float(obs.get("cost_usd", 0.0)),
    )
    latency_pass = LatencyBudgetMetric(latency_budget_ms).evaluate(turn_obs).passed
    cost_pass = CostBudgetMetric(cost_budget_usd).evaluate(turn_obs).passed

    if attachment_size_kb > 0 and turn_index == 1:
        marker = recall_marker_token(RECALL_MARKERS[attachment_size_kb])
        recall_pass = AttachmentRecallMetric(marker).evaluate(
            result.summary,
            phases_text=_phases_text(result),
        ).passed
        attachment_recall_pass = str(int(recall_pass))
    else:
        attachment_recall_pass = ""

    return drift_pass, drift_score, latency_pass, cost_pass, attachment_recall_pass


def _post_estimate_in_process(
    client: TestClient,
    session_id: str,
    *,
    transcript: str,
    profile: StressProfile,
    pdf_path: Path | None,
) -> dict[str, Any]:
    data = {
        "transcript": transcript,
        "project_type": profile.project_type,
        "detail_level": profile.detail_level,
        "output_format": profile.output_format,
    }
    files = None
    if pdf_path is not None:
        files = [
            (
                "attachments",
                (pdf_path.name, pdf_path.read_bytes(), "application/pdf"),
            )
        ]
    response = client.post(
        f"/sessions/{session_id}/estimate",
        data=data,
        files=files,
    )
    response.raise_for_status()
    return response.json()


def _post_estimate_http(
    client: httpx.Client,
    session_id: str,
    *,
    transcript: str,
    profile: StressProfile,
    pdf_path: Path | None,
) -> dict[str, Any]:
    data = {
        "transcript": transcript,
        "project_type": profile.project_type,
        "detail_level": profile.detail_level,
        "output_format": profile.output_format,
    }
    files = None
    if pdf_path is not None:
        files = [
            (
                "attachments",
                (pdf_path.name, pdf_path.read_bytes(), "application/pdf"),
            )
        ]
    response = client.post(f"/sessions/{session_id}/estimate", data=data, files=files)
    response.raise_for_status()
    return response.json()


def run_stress(config: StressRunConfig) -> list[dict[str, Any]]:
    """Execute the stress matrix; append one CSV row per turn (durable on crash)."""
    missing = [
        size
        for size in config.attachment_sizes
        if size > 0 and not (FIXTURES_DIR / PDF_FILENAMES[size]).exists()
    ]
    if missing:
        build_all(output_dir=FIXTURES_DIR, force=False)

    rows: list[dict[str, Any]] = []
    csv_writer = IncrementalCsvWriter(config.output, resume=config.resume)

    def _persist_row(row: dict[str, Any]) -> None:
        csv_writer.append(row)
        rows.append(row)

    def _run_session(
        create_session: Callable[[], str],
        run_turn: Callable[[str, StressProfile, Path | None, str], dict[str, Any]],
        get_session_info: Callable[[str], dict[str, Any]],
        profile: StressProfile,
        attachment_size_kb: int,
        repeat: int,
    ) -> None:
        run_id = uuid.uuid4().hex[:8]
        turns = profile.turns[: config.max_turns]
        pending = [
            turn
            for turn in turns
            if not csv_writer.is_done(
                TurnMatrixKey(
                    scenario=profile.profile_id,
                    attachment_size_kb=attachment_size_kb,
                    repeat=repeat,
                    turn_index=turn.turn_index,
                )
            )
        ]
        if not pending:
            return

        session_id = create_session()
        pdf_path = None
        if attachment_size_kb > 0:
            pdf_path = FIXTURES_DIR / PDF_FILENAMES[attachment_size_kb]

        for turn in pending:
            try:
                payload = run_turn(session_id, profile, pdf_path, turn.transcript)
                info = get_session_info(session_id)
                result = EstimationResult.model_validate(payload["result"])
                snapshot = snapshot_from_session_info(
                    info,
                    estimation_summary=result.summary,
                )
                observability = payload.get("observability") or {}
                drift_pass, drift_score, latency_pass, cost_pass, recall_pass = (
                    _evaluate_turn_metrics(
                        profile=profile,
                        turn_index=turn.turn_index,
                        snapshot=snapshot,
                        result=result,
                        observability=observability,
                        attachment_size_kb=attachment_size_kb,
                        latency_budget_ms=config.latency_budget_ms,
                        cost_budget_usd=config.cost_budget_usd,
                    )
                )
                _persist_row(
                    _row_from_turn(
                        run_id=run_id,
                        scenario=profile.profile_id,
                        attachment_size_kb=attachment_size_kb,
                        repeat=repeat,
                        turn_index=turn.turn_index,
                        session_id=session_id,
                        observability=observability,
                        memory_drift_pass=drift_pass,
                        memory_drift_score=drift_score,
                        latency_budget_pass=latency_pass,
                        cost_budget_pass=cost_pass,
                        attachment_recall_pass=recall_pass,
                        estimation_cached=bool(payload.get("cached", False)),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                # Best-effort drift evaluation even if POST fails: GET session
                # state may still contain previous turns' summary/anchors.
                try:
                    info = get_session_info(session_id)
                except Exception:  # noqa: BLE001
                    info = {}

                snapshot = snapshot_from_session_info(
                    info,
                    estimation_summary=None,
                )
                facts = facts_introduced_up_to(profile, turn.turn_index)
                drift_pass, drift_score = evaluate_memory_drift(snapshot, facts)

                http_status = None
                if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
                    http_status = exc.response.status_code

                _persist_row(
                    _row_from_turn(
                        run_id=run_id,
                        scenario=profile.profile_id,
                        attachment_size_kb=attachment_size_kb,
                        repeat=repeat,
                        turn_index=turn.turn_index,
                        session_id=session_id,
                        observability={},
                        memory_drift_pass=drift_pass,
                        memory_drift_score=drift_score,
                        latency_budget_pass=False,
                        cost_budget_pass=False,
                        attachment_recall_pass="",
                        estimation_cached=False,
                        http_status=http_status,
                        error_type=type(exc).__name__,
                        error_message=_truncate_error_message(str(exc)),
                    )
                )

    try:
        if config.http_base:
            with httpx.Client(base_url=config.http_base, timeout=300.0) as client:
                for profile_id in config.scenarios:
                    profile = get_profile(profile_id)
                    for size_kb in config.attachment_sizes:
                        for repeat in range(config.repeats):

                            def create_session() -> str:
                                return client.post("/sessions").json()["session_id"]

                            def get_session_info(sid: str) -> dict[str, Any]:
                                return client.get(f"/sessions/{sid}").json()

                            def run_turn(
                                sid: str,
                                prof: StressProfile,
                                pdf: Path | None,
                                transcript: str,
                            ) -> dict[str, Any]:
                                return _post_estimate_http(
                                    client, sid, transcript=transcript, profile=prof, pdf_path=pdf
                                )

                            _run_session(
                                create_session,
                                run_turn,
                                get_session_info,
                                profile,
                                size_kb,
                                repeat,
                            )
        else:
            store_was_overridden = get_session_store not in app.dependency_overrides
            if store_was_overridden:
                eval_store = SessionStore(max_turns=6)
                app.dependency_overrides[get_session_store] = lambda: eval_store
            try:
                with TestClient(app) as client:
                    for profile_id in config.scenarios:
                        profile = get_profile(profile_id)
                        for size_kb in config.attachment_sizes:
                            for repeat in range(config.repeats):

                                def create_session() -> str:
                                    return client.post("/sessions").json()["session_id"]

                                def get_session_info(sid: str) -> dict[str, Any]:
                                    return client.get(f"/sessions/{sid}").json()

                                def run_turn(
                                    sid: str,
                                    prof: StressProfile,
                                    pdf: Path | None,
                                    transcript: str,
                                ) -> dict[str, Any]:
                                    return _post_estimate_in_process(
                                        client,
                                        sid,
                                        transcript=transcript,
                                        profile=prof,
                                        pdf_path=pdf,
                                    )

                                _run_session(
                                    create_session,
                                    run_turn,
                                    get_session_info,
                                    profile,
                                    size_kb,
                                    repeat,
                                )
            finally:
                if store_was_overridden:
                    app.dependency_overrides.pop(get_session_store, None)
    finally:
        csv_writer.close()

    if config.report is not None:
        from evals.stress.report import write_report

        write_report(config.output, config.report)

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenarios",
        default="growing,pivot,contradicting",
        help="Comma-separated profile ids (alias: contradiction→contradicting)",
    )
    parser.add_argument(
        "--attachment-sizes",
        default="0,5,20,50,100",
        help=f"Comma-separated sizes in {ATTACHMENT_SIZE_KB}",
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument("--latency-budget-ms", type=int, default=60_000)
    parser.add_argument("--cost-budget-usd", type=float, default=0.50)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("evals/stress/results.csv"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("evals/stress/REPORT.md"),
        help="Markdown report path (pass '' to skip)",
    )
    parser.add_argument("--http", default=None, help="Base URL for HTTP mode")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip matrix cells already present in --output; append new rows",
    )
    args = parser.parse_args()

    report_path = args.report if str(args.report) else None
    config = StressRunConfig(
        scenarios=_normalize_scenarios(args.scenarios),
        attachment_sizes=_normalize_sizes(args.attachment_sizes),
        repeats=args.repeats,
        max_turns=args.max_turns,
        latency_budget_ms=args.latency_budget_ms,
        cost_budget_usd=args.cost_budget_usd,
        output=args.output,
        report=report_path,
        http_base=args.http,
        resume=args.resume,
    )
    rows = run_stress(config)
    on_disk = len(_read_csv_rows(config.output)) if config.output.exists() else 0
    print(f"Wrote {on_disk} rows to {config.output} ({len(rows)} new this run)")
    if config.report:
        print(f"Report written to {config.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
