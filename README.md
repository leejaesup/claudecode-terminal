# ClaudeCode Terminal

> Control Claude Code remotely via Telegram.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-50%20passed-brightgreen.svg)](#docker-integration-test)

**[English](README.md)** | [한국어](docs/README.ko.md) | [日本語](docs/README.ja.md) | [中文](docs/README.zh.md)

---

## Architecture

### System Overview

```mermaid
graph TB
    subgraph User["User"]
        TG["Telegram App"]
    end

    subgraph Server["Local Machine"]
        subgraph CCT["claudecode-terminal"]
            CLI["CLI<br/>(Typer)"]
            BOT["Telegram Bot<br/>(python-telegram-bot)"]
            SEC["Security<br/>(Auth + Blacklist)"]
            CLAUDE["Claude Runner<br/>(subprocess)"]
            SHELL["Shell Runner<br/>(asyncio)"]
            DB["SQLite<br/>(aiosqlite)"]
            CONFIG["Config<br/>(TOML)"]
            FMT["Formatter<br/>(Telegram output)"]
        end

        CCLI["Claude Code CLI<br/>(Node.js)"]
        OS["OS Shell<br/>(bash/zsh)"]
    end

    TG <-->|"Telegram Bot API<br/>(polling)"| BOT
    BOT --> SEC
    SEC -->|"authorized"| CLAUDE
    SEC -->|"authorized"| SHELL
    CLAUDE -->|"subprocess exec"| CCLI
    SHELL -->|"subprocess shell"| OS
    CLAUDE --> DB
    SHELL --> DB
    CLAUDE --> FMT
    SHELL --> FMT
    FMT --> BOT
    CLI --> CONFIG
    BOT --> CONFIG
    CLI -->|"start/stop"| BOT

    style CCT fill:#1a1a2e,stroke:#e94560,color:#fff
    style User fill:#0f3460,stroke:#e94560,color:#fff
    style Server fill:#16213e,stroke:#0f3460,color:#fff
```

### Module Structure

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
        APP["app.py<br/>Application setup"]
        HANDLERS["handlers.py<br/>12 command handlers"]
        SECURITY["security.py<br/>user_id_required"]
    end

    subgraph services["services/"]
        BLACKLIST["blacklist.py<br/>7 regex patterns"]
        CLAUDE_SVC["claude.py<br/>ClaudeRunner"]
        SHELL_SVC["shell.py<br/>ShellRunner"]
    end

    subgraph storage["storage/"]
        DATABASE["database.py<br/>aiosqlite"]
        MODELS["models.py<br/>ExecutionResult"]
    end

    subgraph utils["utils/"]
        FORMATTING["formatting.py<br/>split / format"]
        SYSTEM["system.py<br/>CLI checks"]
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

### Request Flow

```mermaid
sequenceDiagram
    actor User as Telegram User
    participant Bot as Telegram Bot
    participant Sec as Security
    participant BL as Blacklist
    participant Claude as ClaudeRunner
    participant Shell as ShellRunner
    participant CLI as Claude Code CLI
    participant OS as OS Shell
    participant DB as SQLite
    participant Fmt as Formatter

    User->>Bot: /ask "explain this code"
    Bot->>Sec: check user_id
    alt Unauthorized
        Sec-->>Bot: silent drop
    end
    Sec->>Claude: execute(prompt, project)
    Claude->>CLI: subprocess exec
    CLI-->>Claude: stdout/stderr
    Claude->>DB: save_command()
    Claude-->>Fmt: ExecutionResult
    Fmt-->>Bot: formatted message
    Bot-->>User: Claude response

    User->>Bot: /shell "git status"
    Bot->>Sec: check user_id
    Sec->>Shell: execute(command)
    Shell->>BL: check(command)
    alt Blocked
        BL-->>Shell: (true, reason)
        Shell-->>Fmt: blocked result
        Fmt-->>Bot: "Blocked: reason"
        Bot-->>User: blocked message
    end
    BL-->>Shell: (false, "")
    Shell->>OS: subprocess shell
    OS-->>Shell: stdout/stderr
    Shell->>DB: save_command()
    Shell-->>Fmt: ExecutionResult
    Fmt-->>Bot: formatted message
    Bot-->>User: command output
```

### Data Model

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
        text bot_token "required"
        list allowed_users "user IDs"
        text default_project "~/projects"
        text default_model "sonnet"
        int claude_timeout "300s"
        int shell_timeout "30s"
        int max_output "4096"
        text db_path "~/.claudecode-terminal/history.db"
        text log_level "WARNING"
    }
```

### Security Layers

```mermaid
graph TB
    REQ["Incoming Message"] --> L1
    L1["Layer 1: User Authentication<br/>allowed_users whitelist"] -->|pass| L2
    L1 -->|fail| DROP["Silent Drop"]
    L2["Layer 2: Command Blacklist<br/>7 regex patterns"] -->|pass| L3
    L2 -->|fail| BLOCK["Blocked Response"]
    L3["Layer 3: Timeout<br/>shell: 30s / claude: 300s"] -->|pass| L4
    L3 -->|timeout| KILL["Process Kill"]
    L4["Layer 4: Output Limit<br/>max 4096 chars"] --> EXEC["Execute & Store"]

    style L1 fill:#d63031,stroke:#fff,color:#fff
    style L2 fill:#e17055,stroke:#fff,color:#fff
    style L3 fill:#fdcb6e,stroke:#000,color:#000
    style L4 fill:#00b894,stroke:#fff,color:#fff
```

---

## Overview

ClaudeCode Terminal is a personal CLI tool that lets you control [Claude Code](https://docs.anthropic.com/en/docs/claude-code) remotely via Telegram. Send prompts, run shell commands, and manage projects from anywhere through your Telegram bot.

## Features

- **Claude Code Integration** - Send prompts to Claude Code and receive results on Telegram
- **Remote Shell** - Execute shell commands on your local machine via Telegram
- **Security** - User ID whitelist, dangerous command blacklist, execution timeouts
- **Daemon Mode** - Run the bot in the background
- **Command History** - All executions are stored in SQLite
- **Multi-Model** - Switch between Opus, Sonnet, and Haiku models

## Prerequisites

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`npm i -g @anthropic-ai/claude-code`)
- Telegram Bot Token (create at [@BotFather](https://t.me/BotFather))

## Installation

```bash
pip install claudecode-terminal
```

## Quick Start

```bash
# Interactive setup wizard
claudecode-terminal init

# Start bot (foreground)
claudecode-terminal start

# Start in background
claudecode-terminal start --daemon

# Check status
claudecode-terminal status

# Stop bot
claudecode-terminal stop
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/ask <prompt>` | Ask Claude Code a question |
| `/shell <cmd>` | Execute a shell command |
| `/project <path>` | Switch project directory |
| `/model <name>` | Change model (opus/sonnet/haiku) |
| `/continue [msg]` | Continue previous conversation |
| `/system <prompt>` | Set system prompt |
| `/maxturns <n>` | Set max conversation turns |
| `/history` | View recent command history |
| `/settings` | View current settings |

Or just type any message to send it directly to Claude Code.

## CLI Commands

```bash
claudecode-terminal init      # Interactive setup wizard
claudecode-terminal start     # Start the bot (foreground)
claudecode-terminal start -d  # Start in background (daemon)
claudecode-terminal stop      # Stop the bot
claudecode-terminal status    # Check running status
claudecode-terminal config    # View/modify configuration
claudecode-terminal logs      # View bot logs
claudecode-terminal version   # Show version info
```

Short alias: `cct` can be used instead of `claudecode-terminal`.

## Configuration

Configuration is stored in `~/.claudecode-terminal/config.toml`.

Environment variables override config file values:

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDECODE_BOT_TOKEN` | Telegram Bot Token | (required) |
| `CLAUDECODE_ALLOWED_USERS` | Comma-separated user IDs | (all) |
| `CLAUDECODE_DEFAULT_PROJECT` | Default project directory | `~/projects` |
| `CLAUDECODE_DEFAULT_MODEL` | Default Claude model | `sonnet` |
| `CLAUDECODE_TIMEOUT` | Claude timeout (seconds) | `300` |
| `CLAUDECODE_SHELL_TIMEOUT` | Shell timeout (seconds) | `30` |
| `CLAUDECODE_MAX_OUTPUT` | Max output characters | `4096` |

## Security

- **User Authentication**: Only whitelisted Telegram user IDs can use the bot
- **Command Blacklist**: Dangerous commands (rm -rf /, fork bombs, mkfs, dd, shutdown, interactive commands) are blocked
- **Timeouts**: All commands have configurable execution time limits
- **Output Limits**: Output is truncated to prevent memory issues
- **Config Permissions**: Config file is stored with `600` permissions

## Docker Integration Test

```bash
docker compose -f docker-compose.test.yml build
docker compose -f docker-compose.test.yml run --rm test
```

## License

MIT
