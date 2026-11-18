# agy-statusline

English | [简体中文](docs/README.zh-CN.md) | [繁體中文](docs/README.zh-TW.md) | [日本語](docs/README.ja.md) | [한국어](docs/README.ko.md)

A lightweight, zero-dependency local `statusLine` HUD for Google Antigravity CLI (`agy`).

- **Zero third-party dependencies**: Pure Python 3 standard library — no `npm` or `jq` required.
- **Zero network requests & zero credential access**: Reads telemetry JSON streamed natively by `agy` over `stdin` plus local `.git` status (~30–90ms per refresh, well under `agy`'s 300ms throttle, with no background daemon).
- **Cross-platform & Multi-language (i18n)**: Works out of the box on macOS, Linux, and Windows. Automatically detects system language (`en`, `zh-CN`, `zh-TW`, `ja`, `ko`, falling back to English for all other regions) and supports pure ASCII mode (`--ascii`) for legacy terminals.
- **Stacks cleanly below default bar**: Enables `stack_with_default: true` by default, adding two compact lines underneath `agy`'s built-in status bar:
  1. **Current directory** (smart path folding, multi-drive & Unicode-aware) │ **Git branch & status** (`*` modified, `?` untracked, `↑/↓` ahead/behind) │ **Context window progress bar** (turns red at 85% with a handoff alert)
  2. **Live quota overview**: `Gemini 5h / weekly / Argon weekly` & `Claude/GPT 5h / weekly` remaining %, mini progress bars, and reset countdowns (auto-hides bars on narrow split-pane terminals to prevent line wrapping)

## Preview

```text
~/Projects/agy-statusline │ ⎇ main* │ Context [██░░░░░░░░] 18% (193k/1M)
Quota  Gemini 5h [████░] 87%(2h11m) · wk [████░] 74%(4d3h) │ Claude/GPT wk [█████] 92%(3d19h)
```

## Quick Install

The installer automatically backs up `~/.gemini/antigravity-cli/settings.json` to `.bak` and merges only the `statusLine` field, keeping your existing model, permissions, and trusted workspaces intact. Restart `agy` or run `/statusline on` inside an active session.

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1 | iex
```

### Clone & Local Install

```bash
git clone https://github.com/kkrr6840/agy-statusline.git
cd agy-statusline
python3 install.py   # Windows: python install.py
```

## Options, Language Override & Uninstall

- **Replace built-in status line** (`--replace-default` — single status bar mode with active model name automatically shown on line 1):
  - macOS / Linux:
    ```bash
    curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash -s -- --replace-default
    ```
  - Windows PowerShell:
    ```powershell
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1))) --replace-default
    ```
- **Pin display language** (auto-detected from OS locale by default; supported codes: `en`, `zh-CN`, `zh-TW`, `ja`, `ko`):
  - Installer flag: `--lang <code>` (e.g. `python3 install.py --lang en`, or pass `-- --lang ja` to `install.sh`)
  - Runtime environment variable: `AGY_STATUSLINE_LANG=en`
- **ASCII-only mode** (for legacy terminals or fonts without Unicode symbols):
  - Installer flag: `--ascii` (e.g. `python3 install.py --ascii`)
  - Runtime environment variable: `AGY_STATUSLINE_ASCII=1`
- **Toggle inside `agy`**:
  - `/statusline off` / `/statusline on`
- **Uninstall**:
  ```bash
  python3 install.py --uninstall   # Windows: python install.py --uninstall
  ```
  Or run `/statusline reset` directly inside `agy`.
- **Other environment variables**:
  - `AGY_STATUSLINE_WARN_PCT=85`: Custom context usage percentage threshold for the red warning & handoff alert (default: `85`)
  - `AGY_STATUSLINE_SHOW_MODEL=1`: Show the active model name on line 1 (enabled automatically with `--replace-default`)
  - `NO_COLOR=1`: Disable ANSI color output

## Local Tests

```bash
python3 -m unittest discover -s tests -v   # Windows: python -m unittest discover -s tests -v
```

## License

[MIT](LICENSE)
