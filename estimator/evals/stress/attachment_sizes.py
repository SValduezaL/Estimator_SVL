"""Constants for the large-attachment stress corpus (Block 3).

Used by ``build_pdfs`` and the future attachment stress runner.
"""

from __future__ import annotations

from pathlib import Path

ATTACHMENT_SIZE_KB: tuple[int, ...] = (0, 5, 20, 50, 100)

PDF_FILENAMES: dict[int, str] = {
    5: "attach_5kb.pdf",
    20: "attach_20kb.pdf",
    50: "attach_50kb.pdf",
    100: "attach_100kb.pdf",
}

# Same short transcript for every variant; stress is in the attachment.
BASELINE_TRANSCRIPT: str = (
    "Please estimate this greenfield web SaaS project using the attached "
    "technical specification as the primary source of scope and constraints."
)

RECALL_MARKERS: dict[int, str] = {
    5: "STRESS_RECALL_MARKER_5KB: unique-scope-token-5kb-7f3a",
    20: "STRESS_RECALL_MARKER_20KB: unique-scope-token-20kb-9c2e",
    50: "STRESS_RECALL_MARKER_50KB: unique-scope-token-50kb-4b81",
    100: "STRESS_RECALL_MARKER_100KB: unique-scope-token-100kb-d6c0",
}

FIXTURES_DIR: Path = Path(__file__).resolve().parent / "fixtures"

# Default MAX_ATTACHMENT_CHARS in app.config (documented for stress design).
MAX_ATTACHMENT_CHARS: int = 60_000
