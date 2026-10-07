import json
from pathlib import Path

import dnfile

areas = []
areas.append(("로캘 폴더/구조", 100 if Path("ko").is_dir() else 0, "ko/"))
en = list(Path("_extract/en").glob("*.json")) if Path("_extract/en").exists() else []
areas.append(("영문 리소스 추출", 100 if len(en) >= 3 else int(len(en) / 3 * 100), f"{len(en)} files"))

trans_rows = []
for name in ["LogResources", "MsgResources", "UIResources"]:
    p = Path("_extract/ko") / f"{name}.ko.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    hangul = sum(1 for v in d.values() if any("\uac00" <= c <= "\ud7a3" for c in v))
    letterful = sum(1 for v in d.values() if sum(ch.isalpha() for ch in v) >= 2)
    pct = round(hangul / letterful * 100, 1) if letterful else 100.0
    areas.append((f"번역 {name}", pct, f"{hangul}/{len(d)}"))
    trans_rows.append((hangul, letterful, len(d)))

ah = sum(x[0] for x in trans_rows)
al = sum(x[1] for x in trans_rows)
at = sum(x[2] for x in trans_rows)
areas.append(("번역 전체(문자포함 기준)", round(ah / al * 100, 1) if al else 0, f"{ah}/{at}"))

ko_dll = Path("ko/Devolutions.Resources.resources.dll")
ok = False
detail = "없음"
if ko_dll.exists():
    pe = dnfile.dnPE(str(ko_dll))
    cult = str(list(pe.net.mdtables.Assembly)[0].Culture)
    mrs = list(pe.net.mdtables.ManifestResource or [])
    ok = cult == "ko" and len(mrs) == 3
    detail = f"{ko_dll.stat().st_size} bytes, culture={cult}, resources={len(mrs)}"
areas.append(("위성 DLL 빌드/배치", 100 if ok else 50, detail))

deps_ok = sum(
    1
    for f in ["Devolutions.Resources.deps.json", "RemoteDesktopManager.deps.json"]
    if "ko/Devolutions.Resources.resources.dll" in Path(f).read_text(encoding="utf-8")
)
areas.append(("deps.json 등록", int(deps_ok / 2 * 100), f"{deps_ok}/2"))

pipeline = all(
    Path(p).exists()
    for p in ["_build_ko.ps1", "_translate_ko.py", "_tools/ResWriter", "_tools/KoSatellite"]
)
areas.append(("빌드 파이프라인", 100 if pipeline else 70, "스크립트/도구"))
areas.append(("문서(readme)", 100 if Path("readme.md").exists() else 0, "readme.md"))
areas.append(("런타임 검증(수동)", 0, "RDM 실행 + 언어=한국어 확인 필요"))

weights = {
    "로캘 폴더/구조": 5,
    "영문 리소스 추출": 10,
    "번역 LogResources": 5,
    "번역 MsgResources": 20,
    "번역 UIResources": 30,
    "번역 전체(문자포함 기준)": 0,
    "위성 DLL 빌드/배치": 20,
    "deps.json 등록": 5,
    "빌드 파이프라인": 3,
    "문서(readme)": 2,
    "런타임 검증(수동)": 0,
}
tw = sum(weights[n] for n, _, __ in areas if weights.get(n, 0))
overall = round(sum(pct * weights[n] for n, pct, _ in areas if weights.get(n, 0)) / tw, 1)

print(f"OVERALL|{overall}")
for name, pct, detail in areas:
    print(f"{name}|{pct}|{detail}")
