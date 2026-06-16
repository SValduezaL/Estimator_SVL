#!/usr/bin/env python3
"""One-off helper to populate data/seed from existing corpus (dev setup)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BUDGETS_DIR = DATA / "seed" / "budgets"
TRANSCRIPTS_DIR = DATA / "seed" / "transcripts"


def main() -> None:
    BUDGETS_DIR.mkdir(parents=True, exist_ok=True)
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

    sample = json.loads((DATA / "budgets_sample.json").read_text(encoding="utf-8"))
    for budget in sample:
        path = BUDGETS_DIR / f"{budget['budget_id']}.json"
        path.write_text(json.dumps(budget, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for src in (ROOT / "examples" / "transcripts").glob("*.txt"):
        shutil.copy2(src, TRANSCRIPTS_DIR / src.name)

    print(f"budgets: {len(list(BUDGETS_DIR.glob('*.json')))}")
    print(f"transcripts: {len(list(TRANSCRIPTS_DIR.glob('*.txt')))}")


if __name__ == "__main__":
    main()
