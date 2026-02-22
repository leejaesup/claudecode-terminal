# ClaudeCode Terminal

> Telegram을 통해 Claude Code를 원격 제어합니다.

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../LICENSE)
[![Tests](https://img.shields.io/badge/tests-50%20passed-brightgreen.svg)](#docker-통합-테스트)

[English](../README.md) | **[한국어](README.ko.md)** | [日本語](README.ja.md) | [中文](README.zh.md)

---

## 아키텍처

### 시스템 전체 구성도

```mermaid
graph TB
    subgraph User["사용자"]
        TG["Telegram 앱"]
    end

    subgraph Server["로컬 머신"]
        subgraph CCT["claudecode-terminal"]
            CLI["CLI<br/>(Typer)"]
            BOT["Telegram Bot<br/>(python-telegram-bot)"]
            SEC["보안<br/>(인증 + 블랙리스트)"]
            CLAUDE["Claude Runner<br/>(subprocess)"]
            SHELL["Shell Runner<br/>(asyncio)"]
            DB["SQLite<br/>(aiosqlite)"]
            CONFIG["설정<br/>(TOML)"]
            FMT["포맷터<br/>(Telegram 출력)"]
        end

        CCLI["Claude Code CLI<br/>(Node.js)"]
        OS["OS Shell<br/>(bash/zsh)"]
    end

    TG <-->|"Telegram Bot API<br/>(polling)"| BOT
    BOT --> SEC
    SEC -->|"인증 통과"| CLAUDE
    SEC -->|"인증 통과"| SHELL
    CLAUDE -->|"subprocess exec"| CCLI
    SHELL -->|"subprocess shell"| OS
    CLAUDE --> DB
    SHELL --> DB
    CLAUDE --> FMT
    SHELL --> FMT
    FMT --> BOT
    CLI --> CONFIG
    BOT --> CONFIG
    CLI -->|"시작/중지"| BOT

    style CCT fill:#1a1a2e,stroke:#e94560,color:#fff
    style User fill:#0f3460,stroke:#e94560,color:#fff
    style Server fill:#16213e,stroke:#0f3460,color:#fff
```

### 모듈 구조

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
        APP["app.py<br/>앱 설정"]
        HANDLERS["handlers.py<br/>12개 명령 핸들러"]
        SECURITY["security.py<br/>사용자 인증"]
    end

    subgraph services["services/"]
        BLACKLIST["blacklist.py<br/>7개 정규식 패턴"]
        CLAUDE_SVC["claude.py<br/>ClaudeRunner"]
        SHELL_SVC["shell.py<br/>ShellRunner"]
    end

    subgraph storage["storage/"]
        DATABASE["database.py<br/>aiosqlite"]
        MODELS["models.py<br/>ExecutionResult"]
    end

    subgraph utils["utils/"]
        FORMATTING["formatting.py<br/>분할 / 포맷"]
        SYSTEM["system.py<br/>CLI 검증"]
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

### 요청 흐름

```mermaid
sequenceDiagram
    actor User as Telegram 사용자
    participant Bot as Telegram Bot
    participant Sec as 보안
    participant BL as 블랙리스트
    participant Claude as ClaudeRunner
    participant Shell as ShellRunner
    participant CLI as Claude Code CLI
    participant OS as OS Shell
    participant DB as SQLite
    participant Fmt as 포맷터

    User->>Bot: /ask "이 코드 설명해줘"
    Bot->>Sec: user_id 확인
    alt 미인증 사용자
        Sec-->>Bot: 무시
    end
    Sec->>Claude: execute(prompt, project)
    Claude->>CLI: subprocess exec
    CLI-->>Claude: stdout/stderr
    Claude->>DB: save_command()
    Claude-->>Fmt: ExecutionResult
    Fmt-->>Bot: 포맷된 메시지
    Bot-->>User: Claude 응답

    User->>Bot: /shell "git status"
    Bot->>Sec: user_id 확인
    Sec->>Shell: execute(command)
    Shell->>BL: check(command)
    alt 차단됨
        BL-->>Shell: (true, 사유)
        Shell-->>Fmt: 차단 결과
        Fmt-->>Bot: "차단: 사유"
        Bot-->>User: 차단 메시지
    end
    BL-->>Shell: (false, "")
    Shell->>OS: subprocess shell
    OS-->>Shell: stdout/stderr
    Shell->>DB: save_command()
    Shell-->>Fmt: ExecutionResult
    Fmt-->>Bot: 포맷된 메시지
    Bot-->>User: 명령 출력
```

### 데이터 모델

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
        text bot_token "필수"
        list allowed_users "사용자 ID 목록"
        text default_project "~/projects"
        text default_model "sonnet"
        int claude_timeout "300초"
        int shell_timeout "30초"
        int max_output "4096"
        text db_path "~/.claudecode-terminal/history.db"
        text log_level "WARNING"
    }
```

### 보안 계층

```mermaid
graph TB
    REQ["수신 메시지"] --> L1
    L1["1계층: 사용자 인증<br/>allowed_users 화이트리스트"] -->|통과| L2
    L1 -->|실패| DROP["무시"]
    L2["2계층: 명령어 블랙리스트<br/>7개 정규식 패턴"] -->|통과| L3
    L2 -->|실패| BLOCK["차단 응답"]
    L3["3계층: 타임아웃<br/>shell: 30초 / claude: 300초"] -->|통과| L4
    L3 -->|타임아웃| KILL["프로세스 종료"]
    L4["4계층: 출력 제한<br/>최대 4096자"] --> EXEC["실행 및 저장"]

    style L1 fill:#d63031,stroke:#fff,color:#fff
    style L2 fill:#e17055,stroke:#fff,color:#fff
    style L3 fill:#fdcb6e,stroke:#000,color:#000
    style L4 fill:#00b894,stroke:#fff,color:#fff
```

---

## 개요

ClaudeCode Terminal은 Telegram을 통해 [Claude Code](https://docs.anthropic.com/en/docs/claude-code)를 원격으로 제어하는 개인용 CLI 도구입니다. 어디서든 Telegram 봇으로 프롬프트 전송, 쉘 명령 실행, 프로젝트 관리가 가능합니다.

## 주요 기능

- **Claude Code 연동** - Telegram에서 Claude Code에 프롬프트를 보내고 결과를 받음
- **원격 쉘** - Telegram으로 로컬 머신에 쉘 명령어 실행
- **보안** - 사용자 ID 화이트리스트, 위험 명령어 블랙리스트, 실행 타임아웃
- **데몬 모드** - 백그라운드에서 봇 실행
- **명령어 이력** - 모든 실행 기록을 SQLite에 저장
- **멀티 모델** - Opus, Sonnet, Haiku 모델 전환

## 사전 요구사항

- Python 3.10+
- [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`npm i -g @anthropic-ai/claude-code`)
- Telegram Bot 토큰 ([@BotFather](https://t.me/BotFather)에서 생성)

## 설치

```bash
pip install claudecode-terminal
```

## 빠른 시작

```bash
# 대화형 설정 마법사
claudecode-terminal init

# 봇 시작 (포그라운드)
claudecode-terminal start

# 백그라운드 실행
claudecode-terminal start --daemon

# 상태 확인
claudecode-terminal status

# 봇 중지
claudecode-terminal stop
```

## Telegram 명령어

| 명령어 | 설명 |
|--------|------|
| `/ask <프롬프트>` | Claude Code에 질문 |
| `/shell <명령어>` | 쉘 명령어 실행 |
| `/project <경로>` | 프로젝트 디렉토리 전환 |
| `/model <이름>` | 모델 변경 (opus/sonnet/haiku) |
| `/continue [메시지]` | 이전 대화 계속 |
| `/system <프롬프트>` | 시스템 프롬프트 설정 |
| `/maxturns <숫자>` | 최대 대화 턴 설정 |
| `/history` | 최근 명령어 이력 보기 |
| `/settings` | 현재 설정 보기 |

일반 텍스트를 입력하면 Claude Code로 직접 전송됩니다.

## CLI 명령어

```bash
claudecode-terminal init      # 대화형 설정 마법사
claudecode-terminal start     # 봇 시작 (포그라운드)
claudecode-terminal start -d  # 백그라운드 실행
claudecode-terminal stop      # 봇 중지
claudecode-terminal status    # 실행 상태 확인
claudecode-terminal config    # 설정 조회/수정
claudecode-terminal logs      # 봇 로그 보기
claudecode-terminal version   # 버전 정보
```

단축 명령: `claudecode-terminal` 대신 `cct` 사용 가능.

## 설정

설정 파일 위치: `~/.claudecode-terminal/config.toml`

환경변수가 설정 파일 값보다 우선 적용됩니다:

| 환경변수 | 설명 | 기본값 |
|----------|------|--------|
| `CLAUDECODE_BOT_TOKEN` | Telegram Bot 토큰 | (필수) |
| `CLAUDECODE_ALLOWED_USERS` | 쉼표 구분 사용자 ID | (전체 허용) |
| `CLAUDECODE_DEFAULT_PROJECT` | 기본 프로젝트 디렉토리 | `~/projects` |
| `CLAUDECODE_DEFAULT_MODEL` | 기본 Claude 모델 | `sonnet` |
| `CLAUDECODE_TIMEOUT` | Claude 타임아웃 (초) | `300` |
| `CLAUDECODE_SHELL_TIMEOUT` | 쉘 타임아웃 (초) | `30` |
| `CLAUDECODE_MAX_OUTPUT` | 최대 출력 문자수 | `4096` |

## 보안

- **사용자 인증**: 화이트리스트에 등록된 Telegram 사용자 ID만 허용
- **명령어 블랙리스트**: 위험 명령어 차단 (rm -rf /, fork bomb, mkfs, dd, shutdown, 대화형 명령)
- **타임아웃**: 모든 명령어에 실행 시간 제한 적용
- **출력 제한**: 메모리 문제 방지를 위한 출력 길이 제한
- **설정 파일 권한**: `600` 권한으로 저장

## Docker 통합 테스트

```bash
docker compose -f docker-compose.test.yml build
docker compose -f docker-compose.test.yml run --rm test
```

## 라이선스

MIT
