#!/usr/bin/env python3
"""Export EN/KO resource pairs as TSV for human review."""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "_extract" / "review"

SETS = [
    ("LogResources", "Devolutions.Resources.Properties.LogResources.json", "LogResources.ko.json"),
    ("MsgResources", "Devolutions.Resources.Properties.MsgResources.json", "MsgResources.ko.json"),
    ("UIResources", "Devolutions.Resources.Properties.UIResources.json", "UIResources.ko.json"),
]

FIELDS = ["resource", "key", "en", "ko", "unchanged", "has_hangul"]


def write_tsv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=FIELDS,
            delimiter="\t",
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
        )
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict] = []

    for set_name, en_name, ko_name in SETS:
        en = json.loads((ROOT / "_extract" / "en" / en_name).read_text(encoding="utf-8"))
        ko = json.loads((ROOT / "_extract" / "ko" / ko_name).read_text(encoding="utf-8"))
        rows = []
        for key, en_v in en.items():
            ko_v = ko.get(key, "")
            row = {
                "resource": set_name,
                "key": key,
                "en": en_v,
                "ko": ko_v,
                "unchanged": "1" if en_v == ko_v else "0",
                "has_hangul": "1"
                if any("\uac00" <= c <= "\ud7a3" for c in ko_v)
                else "0",
            }
            rows.append(row)
            all_rows.append(row)

        path = OUT_DIR / f"{set_name}.tsv"
        write_tsv(path, rows)
        print(f"{path.name}: {len(rows)}")

    write_tsv(OUT_DIR / "ALL.tsv", all_rows)
    print(f"ALL.tsv: {len(all_rows)}")

    unchanged = [
        r
        for r in all_rows
        if r["unchanged"] == "1" and sum(c.isalpha() for c in r["en"]) >= 2
    ]
    write_tsv(OUT_DIR / "UNCHANGED_EN.tsv", unchanged)
    print(f"UNCHANGED_EN.tsv: {len(unchanged)}")
    print(f"OUT={OUT_DIR}")


if __name__ == "__main__":
    main()
