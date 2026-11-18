# agy-statusline

[English](../README.md) | [简体中文](README.zh-CN.md) | [繁體中文](README.zh-TW.md) | 日本語 | [한국어](README.ko.md)

Google Antigravity CLI（`agy`）向けの軽量・ゼロ依存なローカル下部ステータスライン（`statusLine`）HUD スクリプトです。

- **サードパーティ依存ゼロ**：Python 3 標準ライブラリのみで動作し、`npm` や `jq` のインストールは不要です。
- **ネットワーク通信ゼロ & 認証情報アクセスゼロ**：`agy` が標準入力（`stdin`）経由でネイティブに渡すテレメトリ JSON とローカルの `.git` ステータスのみを解析します。1 回あたりの更新は約 30〜90ms（`agy` の 300ms スロットル間隔より十分に高速）で、常駐バックグラウンドデーモンもありません。
- **クロスプラットフォーム & 多言語対応（i18n）**：macOS・Linux・Windows でシームレスに動作します。OS の言語設定を自動検出し（`en`、`zh-CN`、`zh-TW`、`ja`、`ko` に対応、その他のロケールは英語にフォールバック）、レガシーなターミナルフォント向けに純粋な ASCII モード（`--ascii`）もサポートしています。
- **標準ステータスバーを保持**：デフォルトで `stack_with_default: true` が有効になっており、`agy` 標準のステータスバーの下にコンパクトな 2 行を追加表示します：
  1. **カレントディレクトリ**（スマートなパス省略表示）│ **Git ブランチ & ステータス**（`*` 変更あり、`?` 未追跡、`↑/↓` 先行・遅れ）│ **コンテキストウィンドウの進捗バー**（85% に達すると赤色に変化し、ハンドオフを推奨）
  2. **リアルタイムクォータ状況**：`Gemini 5h / 週 / Argon 週` および `Claude/GPT 5h / 週` の残量（%）、ミニ進捗バー、リセットまでのカウントダウン（狭いターミナル幅では折り返しを防ぐためミニバーを自動で非表示）

## プレビュー

```text
~/Projects/agy-statusline │ ⎇ main* │ コンテキスト [██░░░░░░░░] 18% (193k/1M)
クォータ  Gemini 5h [████░] 87%(2h11m) · 週 [████░] 74%(4d3h) │ Claude/GPT 週 [█████] 92%(3d19h)
```

## クイックインストール

インストーラーは既存の `~/.gemini/antigravity-cli/settings.json` を自動的に `.bak` へバックアップした上で、`statusLine` フィールドのみをマージします。既存のモデル設定、権限、信頼済みワークスペースの設定はそのまま維持されます。インストール後は `agy` を再起動するか、セッション内で `/statusline on` を実行してください。

### macOS / Linux

```bash
curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash
```

### Windows PowerShell

```powershell
irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1 | iex
```

### リポジトリをクローンしてローカルインストール

```bash
git clone https://github.com/kkrr6840/agy-statusline.git
cd agy-statusline
python3 install.py   # Windows: python install.py
```

## オプション・言語設定・アンインストール

- **標準ステータスバーを置き換える**（`--replace-default`：標準バーと重ねず単一バーモードで表示し、1 行目に現在のモデル名を自動表示）：
  - macOS / Linux：
    ```bash
    curl -fsSL https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.sh | bash -s -- --replace-default
    ```
  - Windows PowerShell：
    ```powershell
    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/kkrr6840/agy-statusline/main/install.ps1))) --replace-default
    ```
- **表示言語の指定**（デフォルトは自動検出。対応言語：`en`、`zh-CN`、`zh-TW`、`ja`、`ko`）：
  - インストーラー引数：`--lang ja` / `--lang ko` / `--lang en`（例：`python3 install.py --lang ja`）
  - 環境変数：`AGY_STATUSLINE_LANG=ja`（または `ko`、`en` など）
- **ASCII 専用モード**（Unicode 記号に対応していないターミナル向け）：
  - インストーラー引数 `--ascii`（例：`python3 install.py --ascii`）、または環境変数 `AGY_STATUSLINE_ASCII=1`
- **`agy` セッション内での表示切り替え**：
  - `/statusline off` / `/statusline on`
- **アンインストール**：
  ```bash
  python3 install.py --uninstall   # Windows: python install.py --uninstall
  ```
  （または `agy` セッション内で `/statusline reset` を実行）
- **その他の環境変数**：
  - `AGY_STATUSLINE_WARN_PCT=85`：コンテキスト使用率が赤色警告に変わる閾値（%）をカスタマイズ（デフォルト：`85`）
  - `AGY_STATUSLINE_SHOW_MODEL=1`：1 行目に現在のモデル名を追加表示（`--replace-default` モードではデフォルトで有効）
  - `NO_COLOR=1`：ANSI カラー出力を無効化

## ローカルテスト

```bash
python3 -m unittest discover -s tests -v   # Windows: python -m unittest discover -s tests -v
```

## ライセンス

MIT
