# Remote Desktop Manager 한국어 패치 (비공식)

Devolutions **Remote Desktop Manager(RDM)** UI를 한국어로 쓰기 위한 **비공식 커뮤니티 패치**입니다.  
RDM 설치 프로그램 전체가 아니라, **한국어 위성(satellite) DLL** 과 번역·빌드 도구만 포함합니다.

> **이 프로젝트는 Devolutions 사와 무관합니다.**  
> 공식 제품이 아니며, 보증·지원을 제공하지 않습니다. 중요 환경에서는 적용 전에 반드시 백업하세요.

---

## 한눈에 보기

| 항목 | 내용 |
|------|------|
| 대상 버전 | Remote Desktop Manager **win-x64 2026.3.10.0** (패치 **2026.3.10.2**) |
| 배포물 | `deploy/ko/Devolutions.Resources.resources.dll` |
| 번역 원본 | `_extract/ko/*.ko.json` (Log / Msg / UI) |
| 재빌드 | .NET 8 SDK + `_build_ko.ps1` |
| 라이선스 | 도구·스크립트는 MIT (하단 NOTICE 참고) |

다른 RDM 버전에서는 리소스 키가 달라져 **일부 문구가 영문으로 남거나** 로드에 실패할 수 있습니다. 그때는 해당 버전용으로 다시 추출·번역·빌드가 필요합니다.

---

## 다운로드 (일반 사용자)

소스 전체를 clone 할 필요 없습니다. **GitHub Releases** 에서 zip만 받으면 됩니다.

1. [Releases 페이지](https://github.com/tomjovi/rdm-korean-patch/releases) 로 이동합니다.
2. 최신(또는 사용 중인 RDM 버전에 맞는) 릴리스를 엽니다.  
   예: [v2026.3.10.2](https://github.com/tomjovi/rdm-korean-patch/releases/tag/v2026.3.10.2)
3. **Assets** 에서 `rdm-korean-patch-2026.3.10.2.zip` 을 다운로드합니다.
4. 압축을 풀면 `ko/Devolutions.Resources.resources.dll` 과 `INSTALL.txt` 가 있습니다.

직접 링크(최신 파일이 바뀌면 Releases에서 확인):

```text
https://github.com/tomjovi/rdm-korean-patch/releases/latest
```

개발·번역 기여용으로 전체 소스가 필요하면 아래처럼 clone 하면 됩니다.

```powershell
git clone https://github.com/tomjovi/rdm-korean-patch.git
```

---

## 사용자용: 한국어 패치 적용하기

RDM을 **직접 설치·보유**하신 분만 적용하세요. 이 저장소에는 RDM 본체가 없습니다.

### 1) 준비

1. 위에서 zip을 받아 압축을 해제합니다.
2. RDM을 **완전히 종료**합니다. (트레이 아이콘까지 종료)
3. RDM 설치(또는 포터블) 폴더를 찾습니다.  
   `Devolutions.Resources.dll` 파일이 있는 폴더가 루트입니다.

### 2) DLL 복사

압축 해제한 `ko` 폴더(또는 그 안의 DLL)를 RDM 루트 아래에 넣습니다.

```text
(RDM 루트)/
  Devolutions.Resources.dll          ← 이미 있음
  ko/
    Devolutions.Resources.resources.dll   ← 여기로 복사
  ja/
  zh-Hans/
  ...
```

zip 안 경로:

```text
ko/Devolutions.Resources.resources.dll
```

(저장소를 clone 한 경우) 동일한 파일은 `deploy/ko/` 에도 있습니다.

### 3) (선택) deps.json 등록

대부분의 경우 **폴더만 있어도** .NET이 `ko` 위성을 로드합니다.  
안 되면 `Devolutions.Resources.deps.json` / `RemoteDesktopManager.deps.json` 의 `resources` 구간에 아래를 추가하세요.  
참고 스니펫: [`deploy/deps-ko-snippet.txt`](deploy/deps-ko-snippet.txt)

```json
"ko/Devolutions.Resources.resources.dll": {
  "locale": "ko"
}
```

### 4) 언어 선택

1. RDM을 실행합니다.
2. 설정에서 UI 언어를 **한국어(ko)** 로 선택하거나, Windows 표시 언어가 한국어인지 확인합니다.
3. 메뉴·메시지·로그가 한글로 보이면 성공입니다.  
   패치 버전은 **도움말 → 소개**의 저작권 줄, 또는 **제품 버전** 라벨에  
   `한국어 패치 2026.3.10.2` / `KO 패치 2026.3.10.2` 형태로 표시됩니다.

### 롤백

`ko` 폴더(또는 넣은 DLL)를 삭제·이름 변경한 뒤 RDM을 다시 실행하면 됩니다.

---

## 기여자용: 번역을 고치고 다시 빌드하기

자동 번역(Bing 등) 기반이라 **어색한 문장·용어 불일치**가 있을 수 있습니다.  
JSON만 고친 뒤 빌드하면 개선분을 바로 DLL로 만들 수 있습니다.

### 저장소 구조

```text
rdm-korean-patch/
├── README.md                 ← 지금 보고 있는 문서
├── LICENSE
├── requirements.txt
├── deploy/                   ← 사용자에게 바로 쓰는 배포물
│   ├── ko/Devolutions.Resources.resources.dll
│   └── deps-ko-snippet.txt
├── _extract/
│   ├── ko/                   ← ★ 번역 수정은 여기
│   │   ├── LogResources.ko.json
│   │   ├── MsgResources.ko.json
│   │   └── UIResources.ko.json
│   └── ko_cache.json         ← 재번역 시 캐시
├── _tools/
│   ├── ResWriter/            ← JSON → .resources
│   └── KoSatellite/          ← 위성 DLL 프로젝트
├── _extract_resources.py     ← (선택) 영문 리소스 추출
├── _translate_ko.py          ← (선택) EN→KO 일괄 번역
├── _export_review_tsv.py     ← 검수용 TSV보내기
├── _import_review_tsv.py     ← 검수 TSV 반영
├── _progress.py              ← 진행률 요약
└── _build_ko.ps1             ← JSON → DLL 빌드
```

### 사전 요구 사항

- Windows
- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- Python 3.10+ (검수·재번역·검증 시)

```powershell
cd D:\_Develop\rdm-korean-patch
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### 번역 수정 워크플로 (가장 흔함)

1. `_extract/ko/UIResources.ko.json` 등에서 원하는 키의 한국어 값을 수정합니다.  
   - `{0}`, `{1}`, `%s` 같은 **플레이스홀더는 절대 지우거나 바꾸지 마세요.**
2. 빌드합니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\_build_ko.ps1
```

3. 결과물
   - `ko/Devolutions.Resources.resources.dll` (로컬 빌드 출력)
   - `deploy/ko/Devolutions.Resources.resources.dll` (배포용으로도 갱신됨)
4. RDM에 다시 복사해 확인합니다.

### 검수 TSV로 나누어 고치기

대량 문구를 스프레드시트에서 보고 싶을 때:

```powershell
.\.venv\Scripts\python.exe _export_review_tsv.py
# → 생성된 TSV를 수정한 뒤
.\.venv\Scripts\python.exe _import_review_tsv.py
powershell -ExecutionPolicy Bypass -File .\_build_ko.ps1
```

### (고급) 새 RDM 버전에서 다시 만들기

1. **본인이 보유한** RDM 폴더의 `Devolutions.Resources.dll` 에서 영문 리소스를 추출합니다.  
   (`_extract_resources.py` 사용 — **해당 DLL을 이 저장소에 올리지 마세요.**)
2. `_translate_ko.py` 로 미번역 항목을 채우거나, 기존 `ko_cache.json` 을 활용합니다.
3. 사람이 검수한 뒤 `_build_ko.ps1` 로 위성 DLL을 만듭니다.
4. `KoSatellite.csproj` 의 `Version` / `AssemblyVersion` 을 대상 RDM 버전에 맞춥니다.

---

## 기여 가이드

환영합니다! 특히 아래 기여가 큰 도움이 됩니다.

- UI에서 어색한 번역을 자연스럽게 다듬기
- 용어 통일 (예: Vault / Entry / Gateway 등의 한국어 표기)
- 새 RDM 버전용 키 동기화·빌드 검증
- 설치/문서 개선

### 제안 규칙

1. **포크 → 브랜치 → PR** 을 권장합니다.
2. 한 PR에는 가능하면 **한 종류의 개선**(용어 통일 / 특정 화면 수정 등)만 담아 주세요.
3. 커밋 메시지 예: `fix(ui): '체크아웃' 용어를 '반출'로 통일`
4. PR 설명에 **어느 화면/메뉴**인지, **적용한 RDM 버전**을 적어 주시면 검수가 쉽습니다.
5. 아래는 **절대 올리지 마세요.**
   - RDM 설치본, `RemoteDesktopManager.exe`, 영문/타언어 공식 DLL
   - `*.cfg`, vault, `Connections.log`, WebView 캐시, 토큰·계정 정보
   - 사내 서버명·IP·개인 이메일이 들어간 로그/스크린샷

---

## 저작권 · 재배포 주의

- Remote Desktop Manager 및 `Devolutions.Resources` 는 **Devolutions Inc.** 의 저작물입니다.
- 이 저장소는 UI 문자열의 **비공식 한국어 번역·빌드 도구**를 다룹니다.
- **RDM 설치본 전체**, 다른 언어 공식 DLL, 라이선스 파일을 묶어 재배포하지 마세요.
- 상업적 재배포·유료 판매 전에는 Devolutions 이용약관·라이선스를 확인하세요.
- 번역문의 2차적 저작물 이슈가 있을 수 있으므로, 공개·공유 시  
  **「비공식 · 무보증 · Devolutions 비제휴」** 를 함께 밝혀 주세요.

---

## 개인정보 · 비밀정보

작업용 PC의 RDM 폴더에는 설정·로그·캐시가 있을 수 있습니다.  
**이 저장소나 zip에 절대 넣지 마세요.**

| 위험 항목 | 이유 |
|-----------|------|
| `RemoteDesktopManager.cfg` | 계정·세션/인증 토큰 가능 |
| `Connections.log` | 서버명, IP, 계정명 |
| vault / `*.rdm` / DB | 접속 정보·암호 저장소 |
| `WebView2.Cache/` | 로그인 흔적 가능 |

배포 전 체크리스트:

- [ ] `deploy/ko/` DLL (+ 문서·소스) 위주인지
- [ ] `*.cfg`, 로그, vault, 캐시가 없는지
- [ ] 이메일·토큰·내부 IP가 문서/경로에 없는지

---

## 무보증

이 패치는 비공식입니다.  
사용으로 인한 데이터 손실, 라이선스 문제, 오번역, RDM 동작 이상에 대해 작성자·기여자는 책임지지 않습니다.  
업무·운영 환경에서는 적용 전 백업과 충분한 검증을 권장합니다.

---

## 감사

- [Devolutions Remote Desktop Manager](https://devolutions.net/remote-desktop-manager/) — 원 제품
- 번역·검수에 참여해 주시는 모든 분들

이슈·PR로 편하게 의견 주세요. 한국어 UI를 함께 다듬어 갑시다!
