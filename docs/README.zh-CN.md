# agy-statusline

[English](../README.md) | 简体中文 | [繁體中文](README.zh-TW.md) | [日本語](README.ja.md) | [한국어](README.ko.md)

为 Google Antigravity CLI（`agy`）编写的轻量级、零依赖本地底部状态栏（`statusLine` HUD）。

- **零第三方依赖**：纯 Python 3 标准库实现，无需安装 `npm` 或 `jq`。
- **零网络请求 & 零凭据读取**：直接解析 `agy` 原生通过 `stdin` 推送的状态遥测 JSON 与本地 `.git` 状态（单次刷新约 30～90ms，远低于 `agy` 的 300ms 节流间隔，无常驻后台守护进程）。
- **跨平台 & 多语言（i18n）**：在 macOS、Linux 与 Windows 上开箱即用。默认自动识别系统语言（支持 `en`、`zh-CN`、`zh-TW`、`ja`、`ko`，其余地区自动回退至英文），并提供纯 ASCII 模式（`--ascii`）兼容老旧终端。
- **清爽叠加在默认底栏下方**：默认开启 `stack_with_default: true`，在 `agy` 原生状态栏下方紧凑追加两行：
  1. **当前目录**（智能路径折叠，兼容多盘符与 Unicode 中文路径）│ **Git 分支与同步状态**（`*` 已修改、`?` 未跟踪、`↑/↓` 领先/落后）│ **上下文窗口进度条**（达到 85% 自动变红并提示交接预警）
  2. **实时配额概览**：`Gemini 5h / 周 / Argon 周` 与 `Claude/GPT 5h / 周` 剩余百分比、迷你进度条及重置倒计时（窄分屏终端下自动收起进度条防止折行）

## 预览

```text
~/Projects/agy-statusline │ ⎇ main* │ 上下文 [██░░░░░░░░] 18% (193k/1M)
配额  Gemini 5h [████░] 87%(2h11m) · 周 [████░] 74%(4d3h) │ Claude/GPT 周 [█████] 92%(3d19h)
```

## 快速安装

安装器会自动将已有的 `~/.gemini/antigravity-cli/settings.json` 备份为 `.bak`，仅合并写入 `statusLine` 字段，原有的模型、权限和信任工作区配置完整保留。安装完成后重启 `agy` 或在当前会话内执行 `/statusline on` 即可生效。

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1 | iex
```

### 克隆仓库本地安装

```bash
git clone https://github.com/kkrr6840/agy-statusline.git
cd agy-statusline
python3 install.py   # Windows: python install.py
```

## 可选参数、语言指定与卸载

- **替换官方默认状态栏**（`--replace-default`，不叠加单栏显示，并自动在首行展示当前模型名）：
  - macOS / Linux：
    ```bash
    curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash -s -- --replace-default
    ```
  - Windows PowerShell：
    ```powershell
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1))) --replace-default
    ```
- **固定显示语言**（默认根据系统语言自动检测；支持代码：`en`、`zh-CN`、`zh-TW`、`ja`、`ko`）：
  - 安装参数：`--lang <code>`（例如 `python3 install.py --lang en`，或向 `install.sh` 传入 `-- --lang ja`）
  - 运行时环境变量：`AGY_STATUSLINE_LANG=en`
- **纯 ASCII 模式**（适用于不支持 Unicode 符号的旧终端或字体）：
  - 安装参数：`--ascii`（例如 `python3 install.py --ascii`）
  - 运行时环境变量：`AGY_STATUSLINE_ASCII=1`
- **在 `agy` 会话内临时开关**：
  - `/statusline off` / `/statusline on`
- **彻底卸载**：
  ```bash
  python3 install.py --uninstall   # Windows: python install.py --uninstall
  ```
  或在 `agy` 会话内直接执行 `/statusline reset`。
- **其他环境变量**：
  - `AGY_STATUSLINE_WARN_PCT=85`：自定义上下文变红及交接预警阈值百分比（默认 `85`）
  - `AGY_STATUSLINE_SHOW_MODEL=1`：在第一行显示当前模型名（`--replace-default` 模式下默认自动开启）
  - `NO_COLOR=1`：禁用 ANSI 颜色输出

## 本地测试

```bash
python3 -m unittest discover -s tests -v   # Windows: python -m unittest discover -s tests -v
```

## License

[MIT](../LICENSE)
