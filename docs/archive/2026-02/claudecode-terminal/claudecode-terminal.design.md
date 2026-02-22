# ClaudeCode Terminal Design Document

> **Summary**: Telegram 기반 Claude Code 원격 실행 CLI 앱의 상세 설계
>
> **Project**: claudecode-terminal
> **Version**: 0.1.0
> **Author**: js
> **Date**: 2026-02-22
> **Status**: Draft
> **Planning Doc**: [claudecode-terminal.plan.md](../../01-plan/features/claudecode-terminal.plan.md)

---

## 1. Overview

### 1.1 Design Goals

- **즉시 사용 가능**: `pip install` 후 3개 명령어로 동작 (`init` → `start`)
- **단일 프로세스**: FastAPI/Docker 없이 python-telegram-bot 단독 실행
- **경량**: 최소 의존성, SQLite 단일 파일 DB
- **확장 가능**: 플러그인/훅 없이도 핵심 로직 커스터마이징 가능한 모듈 구조
- **안전**: 인증 + 블랙리스트 + 타임아웃의 3중 보안 레이어

### 1.2 Design Principles

- **Single Responsibility**: 각 모듈이 하나의 역할만 수행
- **Dependency Injection 지양**: 간결함 우선, 글로벌 설정 싱글턴 사용
- **기존 코드 재활용**: `claude-terminal`의 검증된 패턴을 경량화하여 이식
- **CLI-first**: 모든 설정과 제어를 CLI에서 완결

---

## 2. Architecture

### 2.1 Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  claudecode-terminal (Python Package)                       │
│                                                             │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  CLI Layer (typer)                                     │ │
│  │  ┌──────┬───────┬──────┬────────┬────────┬──────────┐ │ │
│  │  │ init │ start │ stop │ status │ config │ logs     │ │ │
│  │  └──┬───┴───┬───┴──┬───┴────┬───┴────┬───┴──────────┘ │ │
│  └─────┼───────┼──────┼────────┼────────┼────────────────┘ │
│        │       │      │        │        │                   │
│  ┌─────▼───────▼──────▼────────▼────────▼────────────────┐ │
│  │  Bot Core (python-telegram-bot 21.x)                   │ │
│  │                                                        │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │  Security Middleware                              │  │ │
│  │  │  user_id_required → blacklist_check              │  │ │
│  │  └──────────────────────────────────────────────────┘  │ │
│  │                                                        │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐  │ │
│  │  │ Claude      │  │ Shell       │  │ Session      │  │ │
│  │  │ Handlers    │  │ Handlers    │  │ Handlers     │  │ │
│  │  │             │  │             │  │              │  │ │
│  │  │ text_input  │  │ /shell      │  │ /project     │  │ │
│  │  │ /ask        │  │ /exec       │  │ /model       │  │ │
│  │  │ /continue   │  │             │  │ /maxturns    │  │ │
│  │  │             │  │             │  │ /system      │  │ │
│  │  │             │  │             │  │ /settings    │  │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────────────┘  │ │
│  └─────────┼───────────────┼────────────────────────────┘ │
│            │               │                               │
│  ┌─────────▼───────────────▼────────────────────────────┐ │
│  │  Service Layer                                        │ │
│  │                                                       │ │
│  │  ┌──────────────────┐  ┌──────────────────┐          │ │
│  │  │  ClaudeRunner     │  │  ShellRunner      │         │ │
│  │  │                   │  │                   │         │ │
│  │  │  execute()        │  │  execute()        │         │ │
│  │  │  - subprocess     │  │  - subprocess     │         │ │
│  │  │  - timeout 300s   │  │  - blacklist      │         │ │
│  │  │  - output parse   │  │  - timeout 30s    │         │ │
│  │  │  - streaming      │  │  - output limit   │         │ │
│  │  └────────┬─────────┘  └────────┬──────────┘         │ │
│  │           │                      │                    │ │
│  │  ┌────────▼──────────────────────▼──────────────────┐ │ │
│  │  │  Output Formatter                                 │ │ │
│  │  │  - split_message(text, 4096)                      │ │ │
│  │  │  - format_result(stdout, stderr, exit_code)       │ │ │
│  │  │  - send_as_file(text) (large output)              │ │ │
│  │  └──────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────┘ │
│                          │                                  │
│  ┌───────────────────────▼──────────────────────────────┐  │
│  │  Storage Layer                                        │  │
│  │  ┌──────────────────┐  ┌──────────────────┐          │  │
│  │  │  SQLite (aiosqlite)│  │  Config (TOML)   │         │  │
│  │  │  - commands table │  │  - config.toml   │         │  │
│  │  │  - WAL mode       │  │  - .env (secrets)│         │  │
│  │  └──────────────────┘  └──────────────────┘          │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

```
[Telegram User]
      │
      ▼ (message)
[python-telegram-bot Polling]
      │
      ▼
[Security: user_id_required]──── 미인가 → (silent drop + log)
      │ 인가
      ▼
[Handler Router]
      │
      ├── /ask, 일반 텍스트 ──→ [ClaudeRunner.execute()]
      │                              │
      │                              ├── subprocess: claude -p "prompt" --output-format text
      │                              ├── wait_for(timeout=300s)
      │                              └── save_history()
      │
      ├── /shell, /exec ──────→ [ShellRunner.execute()]
      │                              │
      │                              ├── blacklist_check()
      │                              ├── subprocess_shell(command)
      │                              ├── wait_for(timeout=30s)
      │                              └── save_history()
      │
      └── /project, /model, ... → [Session State Update]
                                       │
                                       └── context.user_data[key] = value
      │
      ▼
[Output Formatter]
      │
      ├── len ≤ 4096 → reply_text(message)
      ├── len > 4096 → split_message() → 여러 reply_text()
      └── len > 50000 → send_document(file)
      │
      ▼
[Telegram User]
```

### 2.3 Dependencies

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| CLI (typer) | Config | 설정 읽기/쓰기 |
| CLI (typer) | Bot Core | start/stop 제어 |
| Bot Handlers | ClaudeRunner | Claude Code 실행 |
| Bot Handlers | ShellRunner | 셸 명령 실행 |
| Bot Handlers | Security | 인증 검사 |
| ClaudeRunner | Config | 타임아웃, 프로젝트 경로 |
| ClaudeRunner | Database | 이력 저장 |
| ShellRunner | Blacklist | 위험 명령 차단 |
| ShellRunner | Config | 타임아웃, 출력 제한 |
| ShellRunner | Database | 이력 저장 |

---

## 3. Data Model

### 3.1 Configuration (TOML)

```toml
# ~/.claudecode-terminal/config.toml

[bot]
token = ""                          # Telegram Bot Token (init에서 설정)
allowed_users = []                  # Telegram User ID 목록

[claude]
default_project = "~/projects"      # 기본 프로젝트 디렉토리
default_model = "sonnet"            # opus / sonnet / haiku
timeout = 300                       # 초
max_output = 4096                   # 최대 출력 문자 수

[shell]
timeout = 30                        # 초
enabled = true                      # 셸 명령 허용 여부

[storage]
db_path = "~/.claudecode-terminal/history.db"

[logging]
level = "WARNING"                   # DEBUG / INFO / WARNING / ERROR
file = "~/.claudecode-terminal/bot.log"
```

### 3.2 Database Schema

```sql
-- 명령어 실행 이력
CREATE TABLE IF NOT EXISTS commands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    command TEXT NOT NULL,
    stdout TEXT DEFAULT '',
    stderr TEXT DEFAULT '',
    exit_code INTEGER,
    execution_time_ms INTEGER,
    source TEXT DEFAULT 'telegram'
        CHECK(source IN ('telegram', 'claude')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_commands_created_at
    ON commands(created_at);
```

### 3.3 Session State (In-Memory)

```python
# telegram context.user_data에 저장 (프로세스 메모리)
@dataclass
class UserSession:
    project: str = ""           # 현재 프로젝트 경로
    model: str = ""             # 선택된 모델 (opus/sonnet/haiku)
    max_turns: int = 0          # 최대 턴 수 (0 = 제한 없음)
    system_prompt: str = ""     # 시스템 프롬프트
```

---

## 4. Module Specifications

### 4.1 `cli.py` - CLI Entry Point

```python
# typer CLI 앱
app = typer.Typer(name="claudecode-terminal")

@app.command()
def init():
    """대화형 초기 설정 마법사"""
    # 1. Claude Code CLI 설치 확인 (claude --version)
    # 2. Telegram Bot Token 입력 (BotFather 안내 포함)
    # 3. Telegram User ID 입력 (여러 개 가능, 콤마 구분)
    # 4. 기본 프로젝트 디렉토리 입력 (기본값: ~/projects)
    # 5. 기본 모델 선택 (opus/sonnet/haiku, 기본값: sonnet)
    # 6. ~/.claudecode-terminal/ 디렉토리 생성
    # 7. config.toml 저장 (파일 권한 600)
    # 8. .env 생성 (BOT_TOKEN만 별도 저장)

@app.command()
def start(daemon: bool = False):
    """봇 시작"""
    # 1. config.toml 존재 확인 (없으면 init 안내)
    # 2. Claude Code CLI 설치 확인
    # 3. 이미 실행 중인지 PID 파일 확인
    # 4. daemon=True → fork & PID 파일 기록
    # 5. daemon=False → foreground 실행
    # 6. asyncio.run(run_bot())

@app.command()
def stop():
    """봇 종료"""
    # 1. PID 파일 읽기
    # 2. SIGTERM 전송
    # 3. 5초 대기, 미종료 시 SIGKILL
    # 4. PID 파일 삭제

@app.command()
def status():
    """실행 상태 확인"""
    # 1. PID 파일 확인
    # 2. 프로세스 존재 확인
    # 3. 상태 출력 (running/stopped, PID, uptime)

@app.command()
def config(key: str = None, value: str = None):
    """설정 확인/변경"""
    # key=None → 전체 설정 출력
    # key+value → 해당 키 업데이트

@app.command()
def logs(lines: int = 50, follow: bool = False):
    """로그 확인"""
    # tail -n {lines} [-f] bot.log
```

### 4.2 `config.py` - Configuration Manager

```python
from pathlib import Path
import tomllib  # Python 3.11+
import tomli_w  # TOML writing

CONFIG_DIR = Path.home() / ".claudecode-terminal"
CONFIG_FILE = CONFIG_DIR / "config.toml"
PID_FILE = CONFIG_DIR / "bot.pid"
LOG_FILE = CONFIG_DIR / "bot.log"
ENV_FILE = CONFIG_DIR / ".env"

MODEL_ALIASES: dict[str, str] = {
    "opus": "claude-opus-4-6",
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
}

@dataclass
class BotConfig:
    token: str = ""
    allowed_users: list[int] = field(default_factory=list)

@dataclass
class ClaudeConfig:
    default_project: str = "~/projects"
    default_model: str = "sonnet"
    timeout: int = 300
    max_output: int = 4096

@dataclass
class ShellConfig:
    timeout: int = 30
    enabled: bool = True

@dataclass
class StorageConfig:
    db_path: str = "~/.claudecode-terminal/history.db"

@dataclass
class LoggingConfig:
    level: str = "WARNING"
    file: str = "~/.claudecode-terminal/bot.log"

@dataclass
class AppConfig:
    bot: BotConfig
    claude: ClaudeConfig
    shell: ShellConfig
    storage: StorageConfig
    logging: LoggingConfig

def load_config() -> AppConfig:
    """config.toml에서 설정 로드, 환경변수 오버라이드 지원"""

def save_config(config: AppConfig) -> None:
    """config.toml에 설정 저장"""

def ensure_config_dir() -> None:
    """~/.claudecode-terminal/ 디렉토리 생성 및 권한 설정"""
```

### 4.3 `bot/app.py` - Bot Application

```python
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters
)

async def run_bot(config: AppConfig) -> None:
    """봇 메인 루프"""
    # 1. Application 생성
    app = Application.builder().token(config.bot.token).build()

    # 2. 핸들러 등록
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("ask", ask_handler))
    app.add_handler(CommandHandler("shell", shell_handler))
    app.add_handler(CommandHandler("exec", exec_handler))
    app.add_handler(CommandHandler("project", project_handler))
    app.add_handler(CommandHandler("model", model_handler))
    app.add_handler(CommandHandler("maxturns", maxturns_handler))
    app.add_handler(CommandHandler("system", system_handler))
    app.add_handler(CommandHandler("continue", continue_handler))
    app.add_handler(CommandHandler("history", history_handler))
    app.add_handler(CommandHandler("settings", settings_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # 3. DB 초기화
    await init_db(config.storage.db_path)

    # 4. Bot 명령어 목록 설정
    await app.bot.set_my_commands([...])

    # 5. Polling 시작
    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    # 6. SIGTERM/SIGINT 대기
    stop_event = asyncio.Event()
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)
    await stop_event.wait()

    # 7. Graceful shutdown
    await app.updater.stop()
    await app.stop()
    await app.shutdown()
    await close_db()
```

### 4.4 `bot/handlers.py` - Telegram Command Handlers

```python
# 기존 claude-terminal의 handlers.py를 경량화
# 변경점:
# - MODE_NORMAL/MODE_CLAUDE 이중 모드 → Claude 기본 모드 (단일)
# - /exec → /shell (일관성)
# - 파일 명령어 (/cat, /write 등) 제외 → /shell로 통합
# - 웹 터미널 (/terminal) 제외
# - stats (/stats) 제외

# --- 핵심 핸들러 ---

@user_id_required
async def start_handler(update, context):
    """봇 시작 인사 + 간단 가이드"""

@user_id_required
async def help_handler(update, context):
    """명령어 도움말"""

@user_id_required
async def text_handler(update, context):
    """일반 텍스트 → Claude Code로 전달 (기본 모드)"""
    project = get_project(context)
    if not project:
        await update.message.reply_text(
            "프로젝트가 설정되지 않았습니다.\n/project <경로>로 먼저 설정하세요."
        )
        return
    await execute_claude_and_reply(update, context, text, project)

@user_id_required
async def ask_handler(update, context):
    """/ask <prompt> → Claude Code 실행"""

@user_id_required
async def shell_handler(update, context):
    """/shell <cmd> → 셸 명령 실행"""

@user_id_required
async def project_handler(update, context):
    """/project [path] → 프로젝트 전환/확인"""
    # 경로 유효성 검사: os.path.isdir() 체크
    # 절대/상대 경로 모두 지원: expanduser + resolve

@user_id_required
async def model_handler(update, context):
    """/model [name] → 모델 변경/확인"""

@user_id_required
async def maxturns_handler(update, context):
    """/maxturns [n] → 최대 턴 수 설정"""

@user_id_required
async def system_handler(update, context):
    """/system [prompt|clear] → 시스템 프롬프트 설정"""

@user_id_required
async def continue_handler(update, context):
    """/continue [prompt] → 이전 대화 이어가기"""

@user_id_required
async def history_handler(update, context):
    """/history → 최근 10개 명령 이력"""

@user_id_required
async def settings_handler(update, context):
    """/settings → 현재 세션 설정 확인"""
```

### 4.5 `bot/security.py` - Authentication & Blacklist

```python
# 기존 claude-terminal의 security.py + blacklist.py 통합

def is_allowed_user(user_id: int, config: AppConfig) -> bool:
    """User ID 화이트리스트 확인"""
    if not config.bot.allowed_users:
        return True  # 빈 리스트 = 모두 허용 (개인 사용 시)
    return user_id in config.bot.allowed_users

def user_id_required(func):
    """인증 데코레이터"""
    @functools.wraps(func)
    async def wrapper(update, context):
        user = update.effective_user
        if user is None:
            return
        if not is_allowed_user(user.id, _config):
            logger.warning("Unauthorized: user_id=%d", user.id)
            return  # silent drop
        return await func(update, context)
    return wrapper

# --- Blacklist ---

BLACKLIST_PATTERNS: list[tuple[str, str]] = [
    (r":\(\)\s*\{\s*:\|:\s*&\s*\}", "Fork bomb detected"),
    (r"\brm\s+(-[rfRF]+\s+)?/\s*$", "Dangerous rm on root"),
    (r"\bmkfs\b", "Filesystem format blocked"),
    (r"\bdd\s+if=", "Raw disk write blocked"),
    (r"^(shutdown|reboot|halt|poweroff)\b", "System control blocked"),
    (r"^(vi|vim|nano|less|more|top|htop|ssh|python3?|node|bash|zsh)\b",
     "Interactive command - use web terminal"),
]

class BlacklistChecker:
    def __init__(self):
        self._patterns = [
            (re.compile(p, re.IGNORECASE), r) for p, r in BLACKLIST_PATTERNS
        ]

    def check(self, command: str) -> tuple[bool, str]:
        for compiled, reason in self._patterns:
            if compiled.search(command):
                return True, reason
        return False, ""
```

### 4.6 `services/claude.py` - Claude Code Executor

```python
# 기존 claude_code.py의 경량화 버전
# 변경점:
# - runuser 제거 (로컬 사용자로 직접 실행)
# - 프로젝트 경로를 절대경로로 resolve
# - 스트리밍 상태 메시지 추가

class ClaudeRunner:
    def __init__(self, config: AppConfig):
        self.config = config

    async def execute(
        self,
        prompt: str,
        project_path: str,
        user_id: str,
        model: str = "",
        max_turns: int = 0,
        system_prompt: str = "",
        continue_conversation: bool = False,
    ) -> ExecutionResult:
        """Claude Code CLI 실행"""
        resolved_path = Path(project_path).expanduser().resolve()
        if not resolved_path.is_dir():
            return ExecutionResult(
                stdout="", stderr=f"Project not found: {resolved_path}",
                exit_code=-1, execution_time_ms=0,
            )

        # 명령어 구성
        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "text",
            "--dangerously-skip-permissions",
        ]

        if model:
            resolved_model = MODEL_ALIASES.get(model, model)
            cmd.extend(["--model", resolved_model])

        if max_turns > 0:
            cmd.extend(["--max-turns", str(max_turns)])

        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])

        if continue_conversation:
            cmd.append("--continue")

        # 실행
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(resolved_path),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.claude.timeout,
            )
            exit_code = proc.returncode or 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            stdout_bytes = b""
            stderr_bytes = f"Timeout ({self.config.claude.timeout}s)".encode()
            exit_code = -1
        except FileNotFoundError:
            return ExecutionResult(
                stdout="",
                stderr="Claude Code CLI not found. Install: npm i -g @anthropic-ai/claude-code",
                exit_code=-1, execution_time_ms=0,
            )

        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        # 이력 저장
        await self._save_history(
            user_id, f"[claude] {prompt}",
            stdout[:self.config.claude.max_output],
            stderr[:self.config.claude.max_output],
            exit_code, elapsed_ms,
        )

        return ExecutionResult(
            stdout=stdout, stderr=stderr,
            exit_code=exit_code, execution_time_ms=elapsed_ms,
        )

# Key differences from claude-terminal:
# 1. create_subprocess_exec (not shell) → 셸 인젝션 방지
# 2. runuser 제거 → 로컬 사용자로 직접 실행
# 3. Path.expanduser().resolve() → 사용자 홈 경로 지원
# 4. FileNotFoundError 처리 → claude CLI 미설치 감지
```

### 4.7 `services/shell.py` - Shell Executor

```python
class ShellRunner:
    def __init__(self, config: AppConfig, blacklist: BlacklistChecker):
        self.config = config
        self.blacklist = blacklist

    async def execute(
        self,
        command: str,
        user_id: str,
        cwd: str | None = None,
    ) -> ExecutionResult:
        """셸 명령 실행"""
        # 1. 블랙리스트 체크
        blocked, reason = self.blacklist.check(command)
        if blocked:
            return ExecutionResult(
                stdout="", stderr=f"Blocked: {reason}",
                exit_code=-1, execution_time_ms=0, blocked=True,
            )

        # 2. 작업 디렉토리 결정
        work_dir = cwd or self.config.claude.default_project
        work_dir = str(Path(work_dir).expanduser().resolve())

        # 3. 실행
        start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.config.shell.timeout,
            )
            exit_code = proc.returncode or 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            stdout_bytes = b""
            stderr_bytes = f"Timeout ({self.config.shell.timeout}s)".encode()
            exit_code = -1

        elapsed_ms = int((time.monotonic() - start) * 1000)
        stdout = stdout_bytes.decode("utf-8", errors="replace")[:self.config.claude.max_output]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:self.config.claude.max_output]

        await self._save_history(user_id, command, stdout, stderr, exit_code, elapsed_ms)

        return ExecutionResult(
            stdout=stdout, stderr=stderr,
            exit_code=exit_code, execution_time_ms=elapsed_ms,
        )
```

### 4.8 `storage/database.py` - Database Manager

```python
# 기존 claude-terminal의 database.py 간소화
# 변경점:
# - 단일 테이블 (commands만)
# - system_stats, sessions, tesla_tokens 등 제거
# - context manager 패턴 추가

import aiosqlite
from pathlib import Path

_db: aiosqlite.Connection | None = None

async def init_db(db_path: str) -> None:
    """DB 초기화 및 테이블 생성"""
    global _db
    resolved = Path(db_path).expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)

    _db = await aiosqlite.connect(str(resolved))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode = WAL")

    await _db.execute("""
        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            command TEXT NOT NULL,
            stdout TEXT DEFAULT '',
            stderr TEXT DEFAULT '',
            exit_code INTEGER,
            execution_time_ms INTEGER,
            source TEXT DEFAULT 'telegram',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    await _db.execute(
        "CREATE INDEX IF NOT EXISTS idx_commands_created_at ON commands(created_at)"
    )
    await _db.commit()

async def get_db() -> aiosqlite.Connection:
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db

async def close_db() -> None:
    global _db
    if _db is not None:
        await _db.close()
        _db = None
```

### 4.9 `storage/models.py` - Data Models

```python
from dataclasses import dataclass, field

@dataclass
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: int = 0
    blocked: bool = False
    reason: str = ""

@dataclass
class CommandRecord:
    id: int = 0
    user_id: str = ""
    command: str = ""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time_ms: int = 0
    source: str = "telegram"
    created_at: str = ""
```

### 4.10 `utils/formatting.py` - Message Formatting

```python
MAX_TELEGRAM_LENGTH = 4096
FILE_THRESHOLD = 50000  # 이 이상이면 파일로 전송

def split_message(text: str, max_len: int = MAX_TELEGRAM_LENGTH) -> list[str]:
    """긴 메시지를 Telegram 제한에 맞게 분할"""
    # 기존 claude-terminal의 _split_message() 재사용
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, max_len)
        if split_at == -1:
            split_at = max_len
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks

def format_claude_result(result: ExecutionResult, project: str) -> str:
    """Claude Code 실행 결과 포맷팅"""
    output = result.stdout or result.stderr or "(no output)"
    elapsed = format_duration(result.execution_time_ms)
    return f"Claude | {project} | {elapsed}\n\n{output}"

def format_shell_result(result: ExecutionResult, command: str) -> str:
    """셸 명령 실행 결과 포맷팅"""
    output = result.stdout or result.stderr or "(no output)"
    icon = "OK" if result.exit_code == 0 else f"ERR({result.exit_code})"
    return f"$ {command}\n[{icon}]\n\n{output}"

def format_duration(ms: int) -> str:
    if ms < 1000:
        return f"{ms}ms"
    elif ms < 60000:
        return f"{ms / 1000:.1f}s"
    else:
        return f"{ms // 60000}m {(ms % 60000) // 1000}s"

async def send_long_message(update, text: str) -> None:
    """길이에 따라 분할 전송 또는 파일 전송"""
    if len(text) <= MAX_TELEGRAM_LENGTH:
        await update.message.reply_text(text)
    elif len(text) <= FILE_THRESHOLD:
        for chunk in split_message(text):
            await update.message.reply_text(chunk)
    else:
        # 파일로 전송
        import io
        file = io.BytesIO(text.encode("utf-8"))
        file.name = "output.txt"
        await update.message.reply_document(file)
```

### 4.11 `utils/system.py` - System Checks

```python
import shutil
import subprocess

def check_claude_cli() -> tuple[bool, str]:
    """Claude Code CLI 설치 확인"""
    claude_path = shutil.which("claude")
    if not claude_path:
        return False, "Claude Code CLI not found"
    try:
        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True, text=True, timeout=5,
        )
        return True, result.stdout.strip()
    except Exception as e:
        return False, str(e)

def check_project_dir(path: str) -> tuple[bool, str]:
    """프로젝트 디렉토리 유효성 확인"""
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        return False, f"Directory not found: {resolved}"
    if not resolved.is_dir():
        return False, f"Not a directory: {resolved}"
    return True, str(resolved)
```

### 4.12 `daemon.py` - Process Daemonization

```python
import os
import signal
from pathlib import Path

def write_pid(pid_file: Path) -> None:
    pid_file.write_text(str(os.getpid()))

def read_pid(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)  # 프로세스 존재 확인
        return pid
    except (ValueError, OSError):
        pid_file.unlink(missing_ok=True)
        return None

def stop_daemon(pid_file: Path) -> bool:
    pid = read_pid(pid_file)
    if pid is None:
        return False
    os.kill(pid, signal.SIGTERM)
    # 최대 5초 대기
    for _ in range(50):
        try:
            os.kill(pid, 0)
            time.sleep(0.1)
        except OSError:
            pid_file.unlink(missing_ok=True)
            return True
    # 강제 종료
    os.kill(pid, signal.SIGKILL)
    pid_file.unlink(missing_ok=True)
    return True

def daemonize() -> None:
    """Unix 더블 포크 데몬화"""
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)
    # stdin/stdout/stderr 리다이렉트
    sys.stdin = open(os.devnull, 'r')
    sys.stdout = open(os.devnull, 'w')
    sys.stderr = open(os.devnull, 'w')
```

---

## 5. Telegram Bot Commands

### 5.1 Command List

| Command | Arguments | Description | Handler |
|---------|-----------|-------------|---------|
| `/start` | - | 시작 인사 + 간단 가이드 | `start_handler` |
| `/help` | - | 전체 명령어 도움말 | `help_handler` |
| `/ask` | `<prompt>` | Claude Code 실행 | `ask_handler` |
| `/shell` | `<cmd>` | 셸 명령 실행 | `shell_handler` |
| `/project` | `[path]` | 프로젝트 전환/확인 | `project_handler` |
| `/model` | `[name]` | 모델 변경/확인 | `model_handler` |
| `/maxturns` | `[n]` | 최대 턴 수 설정 | `maxturns_handler` |
| `/system` | `[prompt\|clear]` | 시스템 프롬프트 설정 | `system_handler` |
| `/continue` | `[prompt]` | 이전 대화 이어가기 | `continue_handler` |
| `/history` | - | 최근 10개 실행 이력 | `history_handler` |
| `/settings` | - | 현재 세션 설정 확인 | `settings_handler` |
| (텍스트) | - | Claude Code로 자동 전달 | `text_handler` |

### 5.2 Message Format Examples

```
# /help 응답
ClaudeCode Terminal v0.1.0
─────────────────────────
Commands:
  /ask <prompt>    - Ask Claude Code
  /shell <cmd>     - Execute shell command
  /project <path>  - Switch project directory
  /model <name>    - Change model (opus/sonnet/haiku)
  /continue        - Continue previous conversation
  /system <prompt> - Set system prompt
  /maxturns <n>    - Set max turns
  /history         - Recent command history
  /settings        - Current settings
  /help            - This help message

Tip: Just type any text to send it directly to Claude Code.

# Claude Code 실행 결과
Claude | my-project | 12.3s

Here's the login component I created:
...

# /shell 결과
$ git status
[OK]

On branch main
Changes not staged for commit:
  modified: src/auth/login.ts

# /settings 결과
Current Settings
─────────────────
Project: ~/my-app
Model: sonnet (claude-sonnet-4-6)
Max turns: unlimited
System prompt: (none)
```

---

## 6. Error Handling

### 6.1 Error Categories

| Category | Trigger | User Message | Log Level |
|----------|---------|-------------|-----------|
| Auth | 미인가 사용자 | (응답 없음, silent drop) | WARNING |
| Blacklist | 위험 명령어 | "Blocked: {reason}" | WARNING |
| Timeout | 실행 시간 초과 | "Timeout ({n}s)" | WARNING |
| NotFound | Claude CLI 미설치 | "Claude Code not found. Install: ..." | ERROR |
| NotFound | 프로젝트 경로 없음 | "Project not found: {path}" | INFO |
| Runtime | 프로세스 실행 실패 | "Execution failed: {error}" | ERROR |
| Config | config.toml 없음 | "Run `claudecode-terminal init` first" | INFO |
| Config | 잘못된 설정값 | "Invalid config: {detail}" | ERROR |
| Network | Telegram API 오류 | (자동 재시도, 로그만) | ERROR |

### 6.2 Error Response Pattern

```python
# 모든 핸들러에서 일관된 에러 응답
async def safe_reply(update, text: str) -> None:
    try:
        await send_long_message(update, text)
    except Exception:
        logger.exception("Failed to send message")
```

---

## 7. Security Considerations

- [x] Telegram User ID 화이트리스트 인증 (빈 리스트 = 전체 허용 옵션)
- [x] 위험 명령어 정규식 블랙리스트 (fork bomb, rm -rf /, mkfs 등)
- [x] 명령 실행 타임아웃 (Claude: 300s, Shell: 30s)
- [x] 출력 길이 제한 (기본 4096자)
- [x] config.toml 파일 권한 600 (소유자만 읽기/쓰기)
- [x] Bot Token을 .env에 분리 저장
- [x] 미인가 접근 시 응답 없이 로그만 기록 (silent drop)
- [x] `create_subprocess_exec` 사용 (shell injection 방지, Claude 실행)
- [ ] Rate limiting (v2에서 검토)

---

## 8. Test Plan

### 8.1 Test Scope

| Type | Target | Tool |
|------|--------|------|
| Unit Test | config, security, blacklist, formatting | pytest |
| Unit Test | ClaudeRunner, ShellRunner (mock subprocess) | pytest + asyncio |
| Integration Test | Bot handlers (mock telegram) | pytest + python-telegram-bot test utils |
| E2E Test | init → start → Telegram 명령 | manual / pytest-docker |

### 8.2 Key Test Cases

```python
# test_security.py
def test_allowed_user_with_valid_id()
def test_allowed_user_with_invalid_id()
def test_allowed_user_empty_list_allows_all()

# test_blacklist.py
def test_fork_bomb_blocked()
def test_rm_rf_root_blocked()
def test_safe_command_allowed()
def test_interactive_command_blocked()

# test_claude.py
async def test_execute_success()
async def test_execute_timeout()
async def test_execute_cli_not_found()
async def test_execute_project_not_found()
async def test_model_alias_resolution()

# test_shell.py
async def test_execute_success()
async def test_execute_blacklisted()
async def test_execute_timeout()

# test_formatting.py
def test_split_message_short()
def test_split_message_long()
def test_split_message_no_newline()
def test_format_duration_ms()
def test_format_duration_seconds()
def test_format_duration_minutes()

# test_config.py
def test_load_config_default()
def test_load_config_from_file()
def test_save_and_reload_config()
def test_model_aliases()

# test_cli.py
def test_init_creates_config_dir()
def test_start_without_config_shows_error()
def test_status_when_stopped()
```

---

## 9. Package Configuration

### 9.1 pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "claudecode-terminal"
version = "0.1.0"
description = "Control Claude Code remotely via Telegram"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [{ name = "js" }]
keywords = ["claude", "telegram", "remote", "cli", "ai"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Environment :: Console",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Tools",
]

dependencies = [
    "python-telegram-bot>=21.0,<22.0",
    "aiosqlite>=0.20.0",
    "typer>=0.12.0",
    "tomli-w>=1.0.0",
    "rich>=13.0.0",           # CLI 출력 꾸미기
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "ruff>=0.5.0",
    "mypy>=1.10",
]

[project.scripts]
claudecode-terminal = "claudecode_terminal.cli:app"
cct = "claudecode_terminal.cli:app"   # 단축 명령

[project.urls]
Homepage = "https://github.com/user/claudecode-terminal"
Repository = "https://github.com/user/claudecode-terminal"

[tool.hatch.build.targets.wheel]
packages = ["src/claudecode_terminal"]

[tool.ruff]
target-version = "py310"
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B"]

[tool.mypy]
python_version = "3.10"
strict = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 9.2 Dependencies Summary

| Package | Version | Purpose | Size Impact |
|---------|---------|---------|-------------|
| python-telegram-bot | 21.x | Telegram Bot API | ~2MB |
| aiosqlite | 0.20+ | Async SQLite | ~50KB |
| typer | 0.12+ | CLI framework | ~200KB |
| tomli-w | 1.0+ | TOML write | ~20KB |
| rich | 13.0+ | CLI output formatting | ~1MB |
| **Total** | | | **~3.3MB** |

---

## 10. Implementation Order

### Phase 1: Foundation (Core)
1. [x] `pyproject.toml` + project scaffolding
2. [ ] `config.py` - 설정 관리 (TOML 읽기/쓰기)
3. [ ] `storage/database.py` - SQLite 초기화
4. [ ] `storage/models.py` - 데이터 모델

### Phase 2: Security
5. [ ] `bot/security.py` - 인증 데코레이터 + 블랙리스트

### Phase 3: Services
6. [ ] `services/claude.py` - Claude Code 실행
7. [ ] `services/shell.py` - 셸 명령 실행
8. [ ] `utils/formatting.py` - 메시지 포맷팅

### Phase 4: Bot
9. [ ] `bot/handlers.py` - Telegram 핸들러
10. [ ] `bot/app.py` - Bot Application

### Phase 5: CLI
11. [ ] `cli.py` - init/start/stop/status/config/logs
12. [ ] `daemon.py` - 프로세스 데몬화
13. [ ] `utils/system.py` - 시스템 체크

### Phase 6: Polish
14. [ ] `__init__.py` + `__main__.py` - 패키지 엔트리포인트
15. [ ] Tests
16. [ ] README.md

---

## 11. File Mapping (기존 → 신규)

| 기존 (claude-terminal) | 신규 (claudecode-terminal) | 변경 사항 |
|------------------------|--------------------------|----------|
| `backend/app/config.py` | `src/.../config.py` | pydantic-settings → dataclass + TOML |
| `backend/app/database.py` | `src/.../storage/database.py` | 7개 테이블 → 1개 테이블 |
| `backend/app/bot/security.py` | `src/.../bot/security.py` | 동일 패턴 재사용 |
| `backend/app/api/services/blacklist.py` | `src/.../bot/security.py` | security에 통합 |
| `backend/app/api/services/claude_code.py` | `src/.../services/claude.py` | runuser 제거, exec 방식 |
| `backend/app/api/services/shell.py` | `src/.../services/shell.py` | 거의 동일 |
| `backend/app/bot/handlers.py` | `src/.../bot/handlers.py` | 20+핸들러 → 12핸들러 |
| (없음) | `src/.../cli.py` | 신규: typer CLI |
| (없음) | `src/.../daemon.py` | 신규: 프로세스 관리 |
| `backend/app/main.py` | `src/.../bot/app.py` | FastAPI lifespan → 단독 polling |

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-02-22 | Initial draft | js |
