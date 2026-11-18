# agy-statusline

[English](../README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | 한국어

Google Antigravity CLI(`agy`)를 위한 가볍고 외부 의존성이 없는 로컬 하단 상태 표시줄(`statusLine`) HUD 스크립트입니다.

- **서드파티 의존성 제로**: Python 3 표준 라이브러리만 사용하며 `npm`이나 `jq` 설치가 필요하지 않습니다.
- **네트워크 요청 제로 & 자격 증명 접근 제로**: `agy`가 `stdin`으로 네이티브하게 전달하는 텔레메트리 JSON과 로컬 `.git` 상태만 파싱합니다. 단일 새로고침에 약 30~90ms(`agy`의 300ms 스로틀 주기보다 훨씬 빠름)만 소요되며, 상주하는 백그라운드 데몬이 없습니다.
- **크로스 플랫폼 & 다국어 지원(i18n)**: macOS, Linux, Windows에서 매끄럽게 동작합니다. OS 언어를 자동으로 감지하며(`en`, `zh-CN`, `zh-TW`, `ja`, `ko` 지원, 그 외 로케일은 영어로 폴백), 레거시 터미널 폰트를 위한 순수 ASCII 모드(`--ascii`)도 지원합니다.
- **기본 상태 표시줄 유지**: 기본적으로 `stack_with_default: true`로 설정되어 `agy` 기본 하단 바 아래에 간결한 두 줄을 추가합니다:
  1. **현재 디렉터리**(스마트 경로 축약) │ **Git 브랜치 및 상태**(`*` 수정됨, `?` 추적되지 않음, `↑/↓` 앞섬/뒤처짐) │ **컨텍스트 윈도우 진행률 바**(85% 도달 시 빨간색으로 변하며 핸드오프 권장)
  2. **실시간 할당량 상태**: `Gemini 5h / 주간 / Argon 주간` 및 `Claude/GPT 5h / 주간` 잔여 비율(%), 미니 진행률 바, 초기화 카운트다운(좁은 터미널에서는 줄바꿈 방지를 위해 미니 바 자동 숨김)

## 미리보기

```text
~/Projects/agy-statusline │ ⎇ main* │ 컨텍스트 [██░░░░░░░░] 18% (193k/1M)
할당량  Gemini 5h [████░] 87%(2h11m) · 주간 [████░] 74%(4d3h) │ Claude/GPT 주간 [█████] 92%(3d19h)
```

## 빠른 설치

설치 스크립트는 기존 `~/.gemini/antigravity-cli/settings.json` 파일을 `.bak`으로 자동 백업한 뒤 `statusLine` 필드만 병합하므로, 기존에 설정된 모델, 권한 및 신뢰할 수 있는 작업 공간(trusted workspaces) 설정은 그대로 유지됩니다. 설치 후 `agy`를 재시작하거나 세션 내에서 `/statusline on`을 실행하세요.

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1 | iex
```

### 저장소 클론 및 로컬 설치

```bash
git clone https://github.com/kkrr6840/agy-statusline.git
cd agy-statusline
python3 install.py   # Windows: python install.py
```

## 옵션, 언어 설정 및 제거

- **기본 내장 상태 표시줄 대체**(`--replace-default`: 기본 바와 겹치지 않는 단일 바 모드로 동작하며 첫 줄에 현재 모델명 자동 표시):
  - macOS / Linux:
    ```bash
    curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash -s -- --replace-default
    ```
  - Windows PowerShell:
    ```powershell
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1))) --replace-default
    ```
- **표시 언어 지정**(기본값은 자동 감지, 지원 언어: `en`, `zh-CN`, `zh-TW`, `ja`, `ko`):
  - 설치 옵션: `--lang ko` / `--lang ja` / `--lang en` (예: `python3 install.py --lang ko`)
  - 환경 변수: `AGY_STATUSLINE_LANG=ko` (또는 `ja`, `en` 등)
- **ASCII 전용 모드**(유니코드 기호를 지원하지 않는 터미널용):
  - 설치 옵션 `--ascii` (예: `python3 install.py --ascii`) 또는 환경 변수 `AGY_STATUSLINE_ASCII=1`
- **`agy` 세션 내 토글**:
  - `/statusline off` / `/statusline on`
- **제거(Uninstall)**:
  ```bash
  python3 install.py --uninstall   # Windows: python install.py --uninstall
  ```
  (또는 `agy` 세션 내에서 `/statusline reset` 실행)
- **기타 환경 변수**:
  - `AGY_STATUSLINE_WARN_PCT=85`: 컨텍스트 경고(빨간색 전환) 임계값(%) 사용자 지정 (기본값: `85`)
  - `AGY_STATUSLINE_SHOW_MODEL=1`: 첫 번째 줄에 현재 모델명 추가 표시 (`--replace-default` 모드에서는 기본 활성화됨)
  - `NO_COLOR=1`: ANSI 색상 출력 비활성화

## 로컬 테스트

```bash
python3 -m unittest discover -s tests -v   # Windows: python -m unittest discover -s tests -v
```

## 라이선스

MIT
