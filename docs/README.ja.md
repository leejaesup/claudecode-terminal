# ClaudeCode Terminal

> Telegramを通じてClaude Codeをリモート制御します。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Tests](https://img.shields.io/badge/tests-50%20passed-brightgreen.svg)](#docker統合テスト)

[English](../README.md) | [한국어](README.ko.md) | **[日本語](README.ja.md)** | [中文](README.zh.md)

---

## アーキテクチャ

### システム全体構成図

```mermaid
graph TB
    subgraph User["ユーザー"]
        TG["Telegramアプリ"]
    end

    subgraph Server["ローカルマシン"]
        subgraph CCT["claudecode-terminal"]
            CLI["CLI<br/>(Typer)"]
            BOT["Telegram Bot<br/>(python-telegram-bot)"]
            SEC["セキュリティ<br/>(認証 + ブラックリスト)"]
            CLAUDE["Claude Runner<br/>(subprocess)"]
            SHELL["Shell Runner<br/>(asyncio)"]
            DB["SQLite<br/>(aiosqlite)"]
            CONFIG["設定<br/>(TOML)"]
            FMT["フォーマッタ<br/>(Telegram出力)"]
        end

        CCLI["Claude Code CLI<br/>(Node.js)"]
        OS["OS Shell<br/>(bash/zsh)"]
    end

    TG <-->|"Telegram Bot API<br/>(polling)"| BOT
    BOT --> SEC
    SEC -->|"認証通過"| CLAUDE
    SEC -->|"認証通過"| SHELL
    CLAUDE -->|"subprocess exec"| CCLI
    SHELL -->|"subprocess shell"| OS
    CLAUDE --> DB
    SHELL --> DB
    CLAUDE --> FMT
    SHELL --> FMT
    FMT --> BOT
    CLI --> CONFIG
    BOT --> CONFIG
    CLI -->|"起動/停止"| BOT

    style CCT fill:#1a1a2e,stroke:#e94560,color:#fff
    style User fill:#0f3460,stroke:#e94560,color:#fff
    style Server fill:#16213e,stroke:#0f3460,color:#fff
```

### モジュール構造

```mermaid
graph LR
    subgraph cli["cli.py"]
        INIT["init"]
        START["start"]
        STOP["stop"]
        STATUS["status"]
        CFG_CMD["config"]
        LOGS["logs"]
        VER["version"]
    end

    subgraph bot["bot/"]
        APP["app.py<br/>アプリ設定"]
        HANDLERS["handlers.py<br/>12コマンドハンドラ"]
        SECURITY["security.py<br/>ユーザー認証"]
    end

    subgraph services["services/"]
        BLACKLIST["blacklist.py<br/>7正規表現パターン"]
        CLAUDE_SVC["claude.py<br/>ClaudeRunner"]
        SHELL_SVC["shell.py<br/>ShellRunner"]
    end

    subgraph storage["storage/"]
        DATABASE["database.py<br/>aiosqlite"]
        MODELS["models.py<br/>ExecutionResult"]
    end

    subgraph utils["utils/"]
        FORMATTING["formatting.py<br/>分割 / フォーマット"]
        SYSTEM["system.py<br/>CLI検証"]
    end

    START --> APP
    APP --> HANDLERS
    HANDLERS --> SECURITY
    SECURITY --> BLACKLIST
    HANDLERS --> CLAUDE_SVC
    HANDLERS --> SHELL_SVC
    CLAUDE_SVC --> DATABASE
    SHELL_SVC --> DATABASE
    SHELL_SVC --> BLACKLIST
    HANDLERS --> FORMATTING
    CLAUDE_SVC --> MODELS
    SHELL_SVC --> MODELS

    style cli fill:#2d3436,stroke:#00b894,color:#fff
    style bot fill:#2d3436,stroke:#0984e3,color:#fff
    style services fill:#2d3436,stroke:#e17055,color:#fff
    style storage fill:#2d3436,stroke:#fdcb6e,color:#fff
    style utils fill:#2d3436,stroke:#a29bfe,color:#fff
```

### リクエストフロー

```mermaid
sequenceDiagram
    actor User as Telegramユーザー
    participant Bot as Telegram Bot
    participant Sec as セキュリティ
    participant BL as ブラックリスト
    participant Claude as ClaudeRunner
    participant Shell as ShellRunner
    participant CLI as Claude Code CLI
    participant OS as OS Shell
    participant DB as SQLite
    participant Fmt as フォーマッタ

    User->>Bot: /ask "このコードを説明して"
    Bot->>Sec: user_id確認
    alt 未認証ユーザー
        Sec-->>Bot: 無視
    end
    Sec->>Claude: execute(prompt, project)
    Claude->>CLI: subprocess exec
    CLI-->>Claude: stdout/stderr
    Claude->>DB: save_command()
    Claude-->>Fmt: ExecutionResult
    Fmt-->>Bot: フォーマット済みメッセージ
    Bot-->>User: Claude応答

    User->>Bot: /shell "git status"
    Bot->>Sec: user_id確認
    Sec->>Shell: execute(command)
    Shell->>BL: check(command)
    alt ブロック
        BL-->>Shell: (true, 理由)
        Shell-->>Fmt: ブロック結果
        Fmt-->>Bot: "ブロック: 理由"
        Bot-->>User: ブロックメッセージ
    end
    BL-->>Shell: (false, "")
    Shell->>OS: subprocess shell
    OS-->>Shell: stdout/stderr
    Shell->>DB: save_command()
    Shell-->>Fmt: ExecutionResult
    Fmt-->>Bot: フォーマット済みメッセージ
    Bot-->>User: コマンド出力
```

### データモデル

```mermaid
erDiagram
    COMMANDS {
        int id PK "AUTOINCREMENT"
        text user_id "NOT NULL"
        text command "NOT NULL"
        text stdout "DEFAULT ''"
        text stderr "DEFAULT ''"
        int exit_code
        int execution_time_ms
        text source "CHECK(telegram|claude)"
        timestamp created_at "DEFAULT CURRENT_TIMESTAMP"
    }

    CONFIG {
        text bot_token "必須"
        list allowed_users "ユーザーID一覧"
        text default_project "~/projects"
        text default_model "sonnet"
        int claude_timeout "300秒"
        int shell_timeout "30秒"
        int max_output "4096"
        text db_path "~/.claudecode-terminal/history.db"
        text log_level "WARNING"
    }
```

### セキュリティ層

```mermaid
graph TB
    REQ["受信メッセージ"] --> L1
    L1["第1層: ユーザー認証<br/>allowed_usersホワイトリスト"] -->|通過| L2
    L1 -->|失敗| DROP["無視"]
    L2["第2層: コマンドブラックリスト<br/>7正規表現パターン"] -->|通過| L3
    L2 -->|失敗| BLOCK["ブロック応答"]
    L3["第3層: タイムアウト<br/>shell: 30秒 / claude: 300秒"] -->|通過| L4
    L3 -->|タイムアウト| KILL["プロセス終了"]
    L4["第4層: 出力制限<br/>最大4096文字"] --> EXEC["実行・保存"]

    style L1 fill:#d63031,stroke:#fff,color:#fff
    style L2 fill:#e17055,stroke:#fff,color:#fff
    style L3 fill:#fdcb6e,stroke:#000,color:#000
    style L4 fill:#00b894,stroke:#fff,color:#fff
```

---

## 概要

ClaudeCode Terminalは、Telegramを通じて[Claude Code](https://docs.anthropic.com/en/docs/claude-code)をリモート制御する個人用CLIツールです。どこからでもTelegramボットでプロンプト送信、シェルコマンド実行、プロジェクト管理が可能です。

## 主な機能

- **Claude Code連携** - TelegramからClaude Codeにプロンプトを送信し結果を受信
- **リモートシェル** - Telegramでローカルマシンのシェルコマンドを実行
- **セキュリティ** - ユーザーIDホワイトリスト、危険コマンドブラックリスト、実行タイムアウト
- **デーモンモード** - バックグラウンドでボットを実行
- **コマンド履歴** - すべての実行記録をSQLiteに保存
- **マルチモデル** - Opus、Sonnet、Haikuモデルの切り替え

## 前提条件

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`npm i -g @anthropic-ai/claude-code`)
- Telegram Botトークン ([@BotFather](https://t.me/BotFather)で作成)

## インストール

```bash
pip install claudecode-terminal
```

## クイックスタート

```bash
# 対話型セットアップウィザード
claudecode-terminal init

# ボット起動（フォアグラウンド）
claudecode-terminal start

# バックグラウンド実行
claudecode-terminal start --daemon

# ステータス確認
claudecode-terminal status

# ボット停止
claudecode-terminal stop
```

## Telegramコマンド

| コマンド | 説明 |
|----------|------|
| `/ask <プロンプト>` | Claude Codeに質問 |
| `/shell <コマンド>` | シェルコマンドを実行 |
| `/project <パス>` | プロジェクトディレクトリを切替 |
| `/model <名前>` | モデル変更 (opus/sonnet/haiku) |
| `/continue [メッセージ]` | 前回の会話を続行 |
| `/system <プロンプト>` | システムプロンプトを設定 |
| `/maxturns <数>` | 最大会話ターン数を設定 |
| `/history` | 最近のコマンド履歴を表示 |
| `/settings` | 現在の設定を表示 |

テキストを入力すると、Claude Codeに直接送信されます。

## CLIコマンド

```bash
claudecode-terminal init      # 対話型セットアップウィザード
claudecode-terminal start     # ボット起動（フォアグラウンド）
claudecode-terminal start -d  # バックグラウンド実行
claudecode-terminal stop      # ボット停止
claudecode-terminal status    # 実行状態確認
claudecode-terminal config    # 設定の表示/変更
claudecode-terminal logs      # ボットログを表示
claudecode-terminal version   # バージョン情報
```

短縮コマンド: `claudecode-terminal`の代わりに`cct`が使用可能。

## 設定

設定ファイル: `~/.claudecode-terminal/config.toml`

環境変数は設定ファイルの値より優先されます:

| 環境変数 | 説明 | デフォルト |
|----------|------|-----------|
| `CLAUDECODE_BOT_TOKEN` | Telegram Botトークン | (必須) |
| `CLAUDECODE_ALLOWED_USERS` | カンマ区切りユーザーID | (全員許可) |
| `CLAUDECODE_DEFAULT_PROJECT` | デフォルトプロジェクトディレクトリ | `~/projects` |
| `CLAUDECODE_DEFAULT_MODEL` | デフォルトClaudeモデル | `sonnet` |
| `CLAUDECODE_TIMEOUT` | Claudeタイムアウト（秒） | `300` |
| `CLAUDECODE_SHELL_TIMEOUT` | シェルタイムアウト（秒） | `30` |
| `CLAUDECODE_MAX_OUTPUT` | 最大出力文字数 | `4096` |

## セキュリティ

- **ユーザー認証**: ホワイトリストに登録されたTelegramユーザーIDのみ許可
- **コマンドブラックリスト**: 危険なコマンドをブロック (rm -rf /、フォークボム、mkfs、dd、shutdown、対話型コマンド)
- **タイムアウト**: すべてのコマンドに実行時間制限を適用
- **出力制限**: メモリ問題を防ぐための出力長制限
- **設定ファイル権限**: `600`権限で保存

## Docker統合テスト

```bash
docker compose -f docker-compose.test.yml build
docker compose -f docker-compose.test.yml run --rm test
```

## ライセンス

MIT
