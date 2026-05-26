"""Deterministic synthetic PDF corpus for attachment size stress tests.

Regenerate locally (PDFs are git-ignored)::

    uv run python -m evals.stress.fixtures.build_pdfs

Calibrated repeat counts (fpdf2 Helvetica 11pt, fixed margins) produce
approximately these on-disk sizes on Linux:

- attach_5kb.pdf   ~5.0 KB,   6 pages,  ~3.0k extracted chars
- attach_20kb.pdf  ~20.2 KB, 27 pages, ~13.4k extracted chars
- attach_50kb.pdf  ~50.1 KB, 68 pages, ~33.6k extracted chars
- attach_100kb.pdf ~89.6 KB, 122 pages, ~60.3k extracted chars (truncates at 60k)
"""

from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fpdf import FPDF

# Fixed PDF metadata so regenerating on any machine yields identical bytes.
_FIXED_CREATION_DATE = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

from app.attachments.extractor import extract_text
from evals.stress.attachment_sizes import (
    FIXTURES_DIR,
    PDF_FILENAMES,
    RECALL_MARKERS,
)

# Fixed ASCII body text — no timestamps, no locale-dependent formatting.
LOREM_BLOCK = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod "
    "tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim "
    "veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea "
    "commodo consequat. Duis aute irure dolor in reprehenderit in voluptate "
    "velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint "
    "occaecat cupidatat non proident, sunt in culpa qui officia deserunt "
    "mollit anim id est laborum. Scope item alpha requires OAuth2 and Postgres."
)

# Extra pages (each page = one LOREM_BLOCK) after the marker page. Calibrated once.
REPEAT_COUNTS: dict[int, int] = {
    5: 5,
    20: 26,
    50: 67,
    100: 121,
}

PDF_SIZE_LABELS_KB: tuple[int, ...] = (5, 20, 50, 100)


@dataclass(frozen=True)
class BuildResult:
    label_kb: int
    path: Path
    file_bytes: int
    page_count: int
    extracted_chars: int
    sha256: str


def _write_page(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", size=11)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.multi_cell(0, 5, text)


def build_pdf(*, label_kb: int, output_path: Path) -> BuildResult:
    """Write a single calibrated PDF for ``label_kb``."""
    if label_kb not in REPEAT_COUNTS:
        raise ValueError(f"unsupported label_kb={label_kb}")

    pdf = FPDF()
    pdf.set_creation_date(_FIXED_CREATION_DATE)
    pdf.set_margins(15, 15, 15)

    pdf.add_page()
    _write_page(pdf, RECALL_MARKERS[label_kb] + "\n\n" + LOREM_BLOCK)

    for _ in range(REPEAT_COUNTS[label_kb]):
        pdf.add_page()
        _write_page(pdf, LOREM_BLOCK)

    page_count = 1 + REPEAT_COUNTS[label_kb]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))

    content = output_path.read_bytes()
    extracted = extract_text(
        filename=output_path.name,
        content=content,
        max_chars=10**9,
    )
    return BuildResult(
        label_kb=label_kb,
        path=output_path,
        file_bytes=len(content),
        page_count=page_count,
        extracted_chars=len(extracted),
        sha256=hashlib.sha256(content).hexdigest(),
    )


def build_all(*, output_dir: Path, force: bool = False) -> list[BuildResult]:
    results: list[BuildResult] = []
    for label_kb in PDF_SIZE_LABELS_KB:
        path = output_dir / PDF_FILENAMES[label_kb]
        if path.exists() and not force:
            content = path.read_bytes()
            extracted = extract_text(
                filename=path.name, content=content, max_chars=10**9
            )
            results.append(
                BuildResult(
                    label_kb=label_kb,
                    path=path,
                    file_bytes=len(content),
                    page_count=0,
                    extracted_chars=len(extracted),
                    sha256=hashlib.sha256(content).hexdigest(),
                )
            )
            continue
        results.append(build_pdf(label_kb=label_kb, output_path=path))
    return results


def _print_table(results: list[BuildResult]) -> None:
    print(f"{'file':<22} {'bytes':>8} {'pages':>6} {'extracted':>10} {'sha256':>12}")
    for r in results:
        pages = str(r.page_count) if r.page_count else "—"
        print(
            f"{r.path.name:<22} {r.file_bytes:>8} {pages:>6} "
            f"{r.extracted_chars:>10} {r.sha256[:12]:>12}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=FIXTURES_DIR,
        help="Directory for attach_*.pdf (default: fixtures/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing PDFs",
    )
    args = parser.parse_args()

    results = build_all(output_dir=args.output_dir, force=args.force)
    _print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
