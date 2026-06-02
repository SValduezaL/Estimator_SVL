"""One-shot checks for attach_*.pdf fixtures (run from estimator/)."""

from __future__ import annotations

import sys
from pathlib import Path

from app.attachments.extractor import extract_text
from evals.stress.attachment_sizes import (
    FIXTURES_DIR,
    MAX_ATTACHMENT_CHARS,
    PDF_FILENAMES,
    RECALL_MARKERS,
)

# Ranges aligned with build_pdfs.py header (small tolerance).
EXPECTED = {
    5: {"bytes_min": 4500, "bytes_max": 6000, "extracted_min": 2500, "extracted_max": 3500},
    20: {"bytes_min": 18000, "bytes_max": 23000, "extracted_min": 12000, "extracted_max": 15000},
    50: {"bytes_min": 48000, "bytes_max": 55000, "extracted_min": 30000, "extracted_max": 36000},
    100: {"bytes_min": 85000, "bytes_max": 95000, "extracted_min": 59000, "extracted_max": 61000},
}


def main() -> int:
    errors: list[str] = []
    for kb in sorted(PDF_FILENAMES):
        name = PDF_FILENAMES[kb]
        path = FIXTURES_DIR / name
        if not path.exists():
            errors.append(f"{name}: missing at {path}")
            continue

        raw = path.read_bytes()
        full_text = extract_text(filename=name, content=raw, max_chars=10**9)
        capped = extract_text(filename=name, content=raw, max_chars=MAX_ATTACHMENT_CHARS)
        exp = EXPECTED[kb]

        if not exp["bytes_min"] <= len(raw) <= exp["bytes_max"]:
            errors.append(
                f"{name}: file size {len(raw)} not in "
                f"[{exp['bytes_min']}, {exp['bytes_max']}]"
            )
        if not exp["extracted_min"] <= len(full_text) <= exp["extracted_max"]:
            errors.append(
                f"{name}: extracted {len(full_text)} not in "
                f"[{exp['extracted_min']}, {exp['extracted_max']}]"
            )
        if RECALL_MARKERS[kb] not in full_text:
            errors.append(f"{name}: recall marker missing from extracted text")
        if kb == 100:
            if len(capped) != MAX_ATTACHMENT_CHARS:
                errors.append(
                    f"{name}: capped length {len(capped)} != MAX_ATTACHMENT_CHARS "
                    f"({MAX_ATTACHMENT_CHARS})"
                )
        elif len(capped) != len(full_text):
            errors.append(f"{name}: unexpected truncation at app limit")

        print(
            f"OK {name}: {len(raw)} bytes, {len(full_text)} chars, "
            f"capped={len(capped)}, marker present"
        )

    if errors:
        print("\nFAILURES:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nAll PDF fixture checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
