# agy-statusline

为 Google Antigravity CLI（`agy`）编写的极简本地底部状态栏脚本。

- **零第三方依赖**：仅使用 Python 3 标准库，无需 `npm` / `jq`
- **零网络请求 & 零凭据读取**：直接解析 `agy` 原生通过 `stdin` 推送的状态 JSON 与本地 `.git`，单次耗时约 10～15ms，无常驻后台进程
- **保留原生状态栏**：默认开启 `stack_with_default: true`，在 `agy` 原生底栏下方紧凑追加两行：
  1. **当前目录**（支持中文路径折叠）│ **Git 分支与改动/同步状态**（`*` 已修改、`?` 未跟踪、`↑/↓` 领先落后）│ **上下文窗口进度条**（达到 85% 自动变红提示 `⚠建议交接`）
  2. **实时配额**：`Gemini 5h / 周 / Argon周` 与 `Claude/GPT 5h / 周` 剩余百分比、进度条及重置倒计时（窄终端自动收起迷你进度条防折行）

## 预览

```text
~/Projects/agy-statusline │ ⎇ main* │ 上下文 [██░░░░░░░░] 18% (193k/1M)
配额  Gemini 5h [████░] 87%(2h11m) · 周 [████░] 74%(4d3h) │ Claude/GPT 周 [█████] 92%(3d19h)
```

## 一键安装 / 跨电脑复用

安装器会自动备份已有的 `~/.gemini/antigravity-cli/settings.json`（生成 `.bak`），仅合并写入 `statusLine` 字段，原有模型、权限和信任目录配置原样保留。安装后新开或重启一次 `agy` 即可显示（或在会话内执行 `/statusline enable`）。

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
python3 install.py
```

## 常用操作与可选参数

- **替换官方默认状态栏**（不叠加，单栏显示）：
  ```bash
  curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash -s -- --replace-default
  ```
- **在 `agy` 会话内临时开关**：
  - `/statusline off` / `/statusline on`
- **彻底卸载并恢复原状**：
  ```bash
  python3 install.py --uninstall
  ```
  （或在 `agy` 内直接输入 `/statusline reset`）
- **环境变量微调**：
  - `AGY_STATUSLINE_WARN_PCT=85`：自定义上下文变红预警百分比阈值（默认 `85`）
  - `AGY_STATUSLINE_SHOW_MODEL=1`：在第一行额外显示当前模型名（适合 `--replace-default` 模式）
  - `NO_COLOR=1`：关闭 ANSI 颜色输出

## 本地测试

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT
