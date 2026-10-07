#!/usr/bin/env python3
"""Apply reviewed TSV back into _extract/ko/*.ko.json then optionally rebuild DLL."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KO_DIR = ROOT / "_extract" / "ko"

RESOURCE_TO_JSON = {
    "LogResources": "LogResources.ko.json",
    "MsgResources": "MsgResources.ko.json",
    "UIResources": "UIResources.ko.json",
}


def load_tsv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        # sniff delimiter: tab or comma
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters="\t,")
        reader = csv.DictReader(f, dialect=dialect)
        return list(reader)


def apply_rows(rows: list[dict]) -> dict[str, int]:
    # load existing
    data = {}
    for res, fname in RESOURCE_TO_JSON.items():
        data[res] = json.loads((KO_DIR / fname).read_text(encoding="utf-8"))

    updated = {res: 0 for res in RESOURCE_TO_JSON}
    for row in rows:
        res = (row.get("resource") or "").strip()
        key = (row.get("key") or "").strip()
        ko = row.get("ko")
        if ko is None:
            continue
        if res not in data or key not in data[res]:
            continue
        if data[res][key] != ko:
            data[res][key] = ko
            updated[res] += 1

    for res, fname in RESOURCE_TO_JSON.items():
        (KO_DIR / fname).write_text(
            json.dumps(data[res], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return updated


def main() -> None:
    ap = argparse.ArgumentParser(description="Import reviewed TSV into ko JSON")
    ap.add_argument(
        "tsv",
        nargs="?",
        default=str(ROOT / "_extract" / "review" / "ALL.tsv"),
        help="Reviewed TSV/CSV path (default: _extract/review/ALL.tsv)",
    )
    args = ap.parse_args()
    path = Path(args.tsv)
    if not path.exists():
        raise SystemExit(f"Not found: {path}")

    rows = load_tsv(path)
    updated = apply_rows(rows)
    total = sum(updated.values())
    for res, n in updated.items():
        print(f"{res}: updated {n}")
    print(f"TOTAL updated: {total}")
    print("Next: powershell -ExecutionPolicy Bypass -File .\\_build_ko.ps1")


if __name__ == "__main__":
    main()
