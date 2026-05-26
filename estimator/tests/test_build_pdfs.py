"""Unit tests for deterministic stress PDF fixtures (Block 3)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.attachments.extractor import extract_text
from evals.stress.attachment_sizes import (
    MAX_ATTACHMENT_CHARS,
    PDF_FILENAMES,
    RECALL_MARKERS,
)
from evals.stress.fixtures.build_pdfs import PDF_SIZE_LABELS_KB, build_all, build_pdf

_TOLERANCE = 0.15


def _size_bounds(label_kb: int) -> tuple[int, int]:
    target = label_kb * 1024
    if label_kb == 100:
        # Plan: large attachment; accept >= 85 KB on disk.
        return int(85 * 1024), int(target * (1 + _TOLERANCE))
    low = int(target * (1 - _TOLERANCE))
    high = int(target * (1 + _TOLERANCE))
    return low, high


@pytest.fixture
def built_results(tmp_path: Path):
    return build_all(output_dir=tmp_path, force=True)


def test_build_pdfs_produces_four_files(built_results, tmp_path: Path) -> None:
    assert len(built_results) == 4
    for label_kb in PDF_SIZE_LABELS_KB:
        path = tmp_path / PDF_FILENAMES[label_kb]
        assert path.is_file()
        assert path.stat().st_size > 0


def test_file_sizes_within_tolerance(built_results) -> None:
    for result in built_results:
        low, high = _size_bounds(result.label_kb)
        assert low <= result.file_bytes <= high, (
            f"{result.path.name}: {result.file_bytes} bytes not in [{low}, {high}]"
        )


def test_extracted_text_contains_recall_marker(built_results) -> None:
    for result in built_results:
        marker = RECALL_MARKERS[result.label_kb]
        token = marker.split(": ", 1)[1]
        content = result.path.read_bytes()
        text = extract_text(
            filename=result.path.name, content=content, max_chars=10**9
        )
        assert token in text
        assert marker in text


def test_100kb_extracted_exceeds_max_attachment_chars(built_results) -> None:
    path = next(r.path for r in built_results if r.label_kb == 100)
    content = path.read_bytes()
    full = extract_text(filename=path.name, content=content, max_chars=10**9)
    assert len(full) > MAX_ATTACHMENT_CHARS

    truncated = extract_text(
        filename=path.name, content=content, max_chars=MAX_ATTACHMENT_CHARS
    )
    assert len(truncated) == MAX_ATTACHMENT_CHARS
    assert truncated == full[:MAX_ATTACHMENT_CHARS]


def test_build_is_deterministic(tmp_path: Path) -> None:
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    results_a = build_all(output_dir=dir_a, force=True)
    results_b = build_all(output_dir=dir_b, force=True)

    for a, b in zip(results_a, results_b, strict=True):
        hash_a = hashlib.sha256(a.path.read_bytes()).hexdigest()
        hash_b = hashlib.sha256(b.path.read_bytes()).hexdigest()
        assert hash_a == hash_b == a.sha256
        assert a.extracted_chars == b.extracted_chars


def test_build_pdf_single_label(tmp_path: Path) -> None:
    path = tmp_path / "attach_5kb.pdf"
    result = build_pdf(label_kb=5, output_path=path)
    assert result.page_count == 1 + 5
    assert result.label_kb == 5
