# -*- coding: utf-8 -*-
"""Stamp Korean patch version into About / Product Version UI labels."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UI_JSON = ROOT / "_extract" / "ko" / "UIResources.ko.json"
CSPROJ = ROOT / "_tools" / "KoSatellite" / "KoSatellite.csproj"


def read_version() -> str:
    if len(sys.argv) > 1 and sys.argv[1].strip():
        return sys.argv[1].strip()
    text = CSPROJ.read_text(encoding="utf-8")
    m = re.search(r"<Version>([^<]+)</Version>", text)
    if not m:
        raise SystemExit("Could not read <Version> from KoSatellite.csproj")
    return m.group(1)


def main() -> None:
    ver = read_version()
    data = json.loads(UI_JSON.read_text(encoding="utf-8"))
    data["lblCopyrightX"] = f"저작권 {{0}}  ·  한국어 패치 {ver} (비공식)"
    data["lblProductVersion"] = f"제품 버전 · KO 패치 {ver}"
    UI_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Stamped patch version {ver} into lblCopyrightX / lblProductVersion")


if __name__ == "__main__":
    main()
