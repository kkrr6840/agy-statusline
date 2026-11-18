# agy-statusline

[English](../README.md) | [简体中文](README.zh-CN.md) | 繁體中文 | [日本語](README.ja.md) | [한국어](README.ko.md)

專為 Google Antigravity CLI（`agy`）打造的輕量級、零依賴本機底部狀態列（`statusLine` HUD）。

- **零第三方依賴**：純 Python 3 標準函式庫實作，無需安裝 `npm` 或 `jq`。
- **零網路請求 & 零憑證讀取**：直接解析 `agy` 原生透過 `stdin` 串流傳入的遙測 JSON 與本機 `.git` 狀態（單次更新約 30～90ms，遠低於 `agy` 的 300ms 節流間隔，無常駐背景程序）。
- **跨平台 & 多語言（i18n）**：於 macOS、Linux 與 Windows 開箱即用。預設自動偵測系統語系（支援 `en`、`zh-CN`、`zh-TW`、`ja`、`ko`，其他地區自動回退至英文），並支援純 ASCII 模式（`--ascii`）以相容舊版終端機。
- **俐落疊加於預設狀態列下方**：預設啟用 `stack_with_default: true`，在 `agy` 內建狀態列下方緊湊新增兩行資訊：
  1. **目前目錄**（智慧路徑折疊，支援多磁碟機與 Unicode 路徑）│ **Git 分支與同步狀態**（`*` 已修改、`?` 未追蹤、`↑/↓` 領先/落後）│ **上下文視窗進度條**（達 85% 自動變紅並顯示交接提醒）
  2. **即時配額總覽**：`Gemini 5h / 週 / Argon 週` 與 `Claude/GPT 5h / 週` 剩餘百分比、迷你進度條與重置倒數計時（在窄分割視窗終端機中自動隱藏進度條以防換行）

## 預覽

```text
~/Projects/agy-statusline │ ⎇ main* │ 上下文 [██░░░░░░░░] 18% (193k/1M)
配額  Gemini 5h [████░] 87%(2h11m) · 週 [████░] 74%(4d3h) │ Claude/GPT 週 [█████] 92%(3d19h)
```

## 快速安裝

安裝程式會自動將既有的 `~/.gemini/antigravity-cli/settings.json` 備份為 `.bak`，並僅合併寫入 `statusLine` 欄位，完整保留原有的模型、權限與信任工作區設定。安裝完成後請重新啟動 `agy`，或在工作階段內執行 `/statusline on` 即可生效。

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1 | iex
```

### 複製儲存庫本機安裝

```bash
git clone https://github.com/kkrr6840/agy-statusline.git
cd agy-statusline
python3 install.py   # Windows: python install.py
```

## 進階選項、語系指定與解除安裝

- **取代內建預設狀態列**（`--replace-default`，單一狀態列模式，並自動於第一行顯示目前模型名稱）：
  - macOS / Linux：
    ```bash
    curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash -s -- --replace-default
    ```
  - Windows PowerShell：
    ```powershell
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1))) --replace-default
    ```
- **固定顯示語系**（預設依作業系統語系自動偵測；支援代碼：`en`、`zh-CN`、`zh-TW`、`ja`、`ko`）：
  - 安裝參數：`--lang <code>`（例如 `python3 install.py --lang en`，或傳遞 `-- --lang ja` 給 `install.sh`）
  - 執行期環境變數：`AGY_STATUSLINE_LANG=en`
- **純 ASCII 模式**（適用於不支援 Unicode 符號的舊版終端機或字型）：
  - 安裝參數：`--ascii`（例如 `python3 install.py --ascii`）
  - 執行期環境變數：`AGY_STATUSLINE_ASCII=1`
- **於 `agy` 工作階段內切換開關**：
  - `/statusline off` / `/statusline on`
- **解除安裝**：
  ```bash
  python3 install.py --uninstall   # Windows: python install.py --uninstall
  ```
  或直接在 `agy` 內執行 `/statusline reset`。
- **其他環境變數**：
  - `AGY_STATUSLINE_WARN_PCT=85`：自訂上下文視窗變紅與交接提醒的使用率百分比門檻（預設 `85`）
  - `AGY_STATUSLINE_SHOW_MODEL=1`：於第一行顯示目前模型名稱（`--replace-default` 模式下預設自動啟用）
  - `NO_COLOR=1`：停用 ANSI 色彩輸出

## 本機測試

```bash
python3 -m unittest discover -s tests -v   # Windows: python -m unittest discover -s tests -v
```

## License

[MIT](../LICENSE)
