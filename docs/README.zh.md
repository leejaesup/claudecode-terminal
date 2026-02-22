# ClaudeCode Terminal

> 通过Telegram远程控制Claude Code。

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Tests](https://img.shields.io/badge/tests-50%20passed-brightgreen.svg)](#docker集成测试)

[English](../README.md) | [한국어](README.ko.md) | [日本語](README.ja.md) | **[中文](README.zh.md)**

---

## 架构

### 系统整体架构图

```mermaid
graph TB
    subgraph User["用户"]
        TG["Telegram应用"]
    end

    subgraph Server["本地机器"]
        subgraph CCT["claudecode-terminal"]
            CLI["CLI<br/>(Typer)"]
            BOT["Telegram Bot<br/>(python-telegram-bot)"]
            SEC["安全<br/>(认证 + 黑名单)"]
            CLAUDE["Claude Runner<br/>(subprocess)"]
            SHELL["Shell Runner<br/>(asyncio)"]
            DB["SQLite<br/>(aiosqlite)"]
            CONFIG["配置<br/>(TOML)"]
            FMT["格式化器<br/>(Telegram输出)"]
        end

        CCLI["Claude Code CLI<br/>(Node.js)"]
        OS["OS Shell<br/>(bash/zsh)"]
    end

    TG <-->|"Telegram Bot API<br/>(polling)"| BOT
    BOT --> SEC
    SEC -->|"认证通过"| CLAUDE
    SEC -->|"认证通过"| SHELL
    CLAUDE -->|"subprocess exec"| CCLI
    SHELL -->|"subprocess shell"| OS
    CLAUDE --> DB
    SHELL --> DB
    CLAUDE --> FMT
    SHELL --> FMT
    FMT --> BOT
    CLI --> CONFIG
    BOT --> CONFIG
    CLI -->|"启动/停止"| BOT

    style CCT fill:#1a1a2e,stroke:#e94560,color:#fff
    style User fill:#0f3460,stroke:#e94560,color:#fff
    style Server fill:#16213e,stroke:#0f3460,color:#fff
```

### 模块结构

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
        APP["app.py<br/>应用设置"]
        HANDLERS["handlers.py<br/>12个命令处理器"]
        SECURITY["security.py<br/>用户认证"]
    end

    subgraph services["services/"]
        BLACKLIST["blacklist.py<br/>7个正则模式"]
        CLAUDE_SVC["claude.py<br/>ClaudeRunner"]
        SHELL_SVC["shell.py<br/>ShellRunner"]
    end

    subgraph storage["storage/"]
        DATABASE["database.py<br/>aiosqlite"]
        MODELS["models.py<br/>ExecutionResult"]
    end

    subgraph utils["utils/"]
        FORMATTING["formatting.py<br/>分割 / 格式化"]
        SYSTEM["system.py<br/>CLI验证"]
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

### 请求流程

```mermaid
sequenceDiagram
    actor User as Telegram用户
    participant Bot as Telegram Bot
    participant Sec as 安全
    participant BL as 黑名单
    participant Claude as ClaudeRunner
    participant Shell as ShellRunner
    participant CLI as Claude Code CLI
    participant OS as OS Shell
    participant DB as SQLite
    participant Fmt as 格式化器

    User->>Bot: /ask "解释这段代码"
    Bot->>Sec: 验证user_id
    alt 未授权用户
        Sec-->>Bot: 静默丢弃
    end
    Sec->>Claude: execute(prompt, project)
    Claude->>CLI: subprocess exec
    CLI-->>Claude: stdout/stderr
    Claude->>DB: save_command()
    Claude-->>Fmt: ExecutionResult
    Fmt-->>Bot: 格式化消息
    Bot-->>User: Claude响应

    User->>Bot: /shell "git status"
    Bot->>Sec: 验证user_id
    Sec->>Shell: execute(command)
    Shell->>BL: check(command)
    alt 被阻止
        BL-->>Shell: (true, 原因)
        Shell-->>Fmt: 阻止结果
        Fmt-->>Bot: "阻止: 原因"
        Bot-->>User: 阻止消息
    end
    BL-->>Shell: (false, "")
    Shell->>OS: subprocess shell
    OS-->>Shell: stdout/stderr
    Shell->>DB: save_command()
    Shell-->>Fmt: ExecutionResult
    Fmt-->>Bot: 格式化消息
    Bot-->>User: 命令输出
```

### 数据模型

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
        text bot_token "必填"
        list allowed_users "用户ID列表"
        text default_project "~/projects"
        text default_model "sonnet"
        int claude_timeout "300秒"
        int shell_timeout "30秒"
        int max_output "4096"
        text db_path "~/.claudecode-terminal/history.db"
        text log_level "WARNING"
    }
```

### 安全层

```mermaid
graph TB
    REQ["接收消息"] --> L1
    L1["第1层: 用户认证<br/>allowed_users白名单"] -->|通过| L2
    L1 -->|失败| DROP["静默丢弃"]
    L2["第2层: 命令黑名单<br/>7个正则模式"] -->|通过| L3
    L2 -->|失败| BLOCK["阻止响应"]
    L3["第3层: 超时<br/>shell: 30秒 / claude: 300秒"] -->|通过| L4
    L3 -->|超时| KILL["终止进程"]
    L4["第4层: 输出限制<br/>最大4096字符"] --> EXEC["执行并存储"]

    style L1 fill:#d63031,stroke:#fff,color:#fff
    style L2 fill:#e17055,stroke:#fff,color:#fff
    style L3 fill:#fdcb6e,stroke:#000,color:#000
    style L4 fill:#00b894,stroke:#fff,color:#fff
```

---

## 概述

ClaudeCode Terminal是一个通过Telegram远程控制[Claude Code](https://docs.anthropic.com/en/docs/claude-code)的个人CLI工具。可以在任何地方通过Telegram机器人发送提示词、执行Shell命令、管理项目。

## 主要功能

- **Claude Code集成** - 通过Telegram向Claude Code发送提示词并接收结果
- **远程Shell** - 通过Telegram在本地机器上执行Shell命令
- **安全性** - 用户ID白名单、危险命令黑名单、执行超时
- **守护进程模式** - 在后台运行机器人
- **命令历史** - 所有执行记录保存到SQLite
- **多模型** - 在Opus、Sonnet、Haiku模型之间切换

## 前提条件

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`npm i -g @anthropic-ai/claude-code`)
- Telegram Bot令牌 (在[@BotFather](https://t.me/BotFather)创建)

## 安装

```bash
pip install claudecode-terminal
```

## 快速开始

```bash
# 交互式设置向导
claudecode-terminal init

# 启动机器人（前台）
claudecode-terminal start

# 后台运行
claudecode-terminal start --daemon

# 检查状态
claudecode-terminal status

# 停止机器人
claudecode-terminal stop
```

## Telegram命令

| 命令 | 说明 |
|------|------|
| `/ask <提示词>` | 向Claude Code提问 |
| `/shell <命令>` | 执行Shell命令 |
| `/project <路径>` | 切换项目目录 |
| `/model <名称>` | 更改模型 (opus/sonnet/haiku) |
| `/continue [消息]` | 继续上一次对话 |
| `/system <提示词>` | 设置系统提示词 |
| `/maxturns <数字>` | 设置最大对话轮数 |
| `/history` | 查看最近命令历史 |
| `/settings` | 查看当前设置 |

直接输入文本即可发送给Claude Code。

## CLI命令

```bash
claudecode-terminal init      # 交互式设置向导
claudecode-terminal start     # 启动机器人（前台）
claudecode-terminal start -d  # 后台运行
claudecode-terminal stop      # 停止机器人
claudecode-terminal status    # 检查运行状态
claudecode-terminal config    # 查看/修改配置
claudecode-terminal logs      # 查看机器人日志
claudecode-terminal version   # 显示版本信息
```

快捷命令: 可以使用`cct`代替`claudecode-terminal`。

## 配置

配置文件位置: `~/.claudecode-terminal/config.toml`

环境变量优先于配置文件:

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `CLAUDECODE_BOT_TOKEN` | Telegram Bot令牌 | (必填) |
| `CLAUDECODE_ALLOWED_USERS` | 逗号分隔的用户ID | (允许所有) |
| `CLAUDECODE_DEFAULT_PROJECT` | 默认项目目录 | `~/projects` |
| `CLAUDECODE_DEFAULT_MODEL` | 默认Claude模型 | `sonnet` |
| `CLAUDECODE_TIMEOUT` | Claude超时（秒） | `300` |
| `CLAUDECODE_SHELL_TIMEOUT` | Shell超时（秒） | `30` |
| `CLAUDECODE_MAX_OUTPUT` | 最大输出字符数 | `4096` |

## 安全性

- **用户认证**: 仅允许白名单中的Telegram用户ID
- **命令黑名单**: 阻止危险命令 (rm -rf /、fork bomb、mkfs、dd、shutdown、交互式命令)
- **超时**: 所有命令都有可配置的执行时间限制
- **输出限制**: 限制输出长度以防止内存问题
- **配置文件权限**: 以`600`权限保存

## Docker集成测试

```bash
docker compose -f docker-compose.test.yml build
docker compose -f docker-compose.test.yml run --rm test
```

## 许可证

MIT
