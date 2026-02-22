# ClaudeCode Terminal Planning Document

> **Summary**: Telegram을 통해 원격 컴퓨터에서 Claude Code CLI를 실행하고 제어하는 오픈소스 CLI 앱
>
> **Project**: claudecode-terminal
> **Version**: 0.1.0
> **Author**: js
> **Date**: 2026-02-22
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

원격지 컴퓨터에 설치된 Claude Code를 Telegram 메신저를 통해 어디서든 실행하고 결과를 확인할 수 있는 CLI 도구. 기존 `claude-terminal` 프로젝트의 Claude Code 실행 기능을 독립적인 배포 가능한 패키지로 분리하여, 누구나 `npm install -g` 또는 `pip install`로 설치하고 자신의 컴퓨터에서 사용할 수 있도록 한다.

### 1.2 Background

- 기존 `claude-terminal`은 Docker 기반의 개인용 올인원 서비스로, 웹 터미널/대시보드/Tesla 연동 등 다양한 기능이 결합되어 있어 다른 사용자가 설치하기 어려움
- Claude Code CLI는 로컬에서만 실행 가능하지만, 개발자들은 이동 중에도 원격 서버의 Claude Code를 활용하고 싶은 니즈가 존재
- Telegram은 모바일/데스크톱 어디서든 접근 가능하여 원격 제어 인터페이스로 적합
- 설치와 설정이 간단한 CLI 도구로 만들어 오픈소스 커뮤니티에 공유

### 1.3 Related Documents

- 참조 프로젝트: `/Users/js/Docker/claude-terminal` (기존 개인용 서비스)
- 참조 소스: `claude-terminal/backend/app/api/services/claude_code.py` (Claude Code 실행 로직)
- 참조 소스: `claude-terminal/backend/app/bot/handlers.py` (Telegram 핸들러 패턴)

---

## 2. Scope

### 2.1 In Scope

- [x] Telegram Bot을 통한 Claude Code 원격 실행
- [x] 프로젝트 디렉토리 전환 (`/project <path>`)
- [x] 모델 선택 (`/model opus|sonnet|haiku`)
- [x] 대화 계속하기 (`/continue`)
- [x] 시스템 프롬프트 설정 (`/system <prompt>`)
- [x] 명령어 실행 이력 조회 (`/history`)
- [x] 셸 명령어 직접 실행 (`/shell <cmd>`)
- [x] 간단한 설치 (npm install -g 또는 pip install)
- [x] 대화형 초기 설정 마법사 (`claudecode-terminal init`)
- [x] 다중 사용자 인증 (Telegram User ID 기반)
- [x] 세션/대화 컨텍스트 관리
- [x] 긴 응답 자동 분할 (Telegram 4096자 제한 처리)

### 2.2 Out of Scope

- 웹 터미널 UI (xterm.js) - 별도 프로젝트로 분리
- 시스템 대시보드 (CPU/메모리 모니터링) - 별도 프로젝트로 분리
- Tesla API 연동
- Docker 기반 배포 (선택적 제공만)
- 파일 업로드/다운로드 (v2에서 검토)
- 멀티 봇 인스턴스 관리

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | `claudecode-terminal init` 명령으로 대화형 설정 (Bot Token, User ID, 프로젝트 경로) | High | Pending |
| FR-02 | `claudecode-terminal start` 명령으로 봇 데몬 시작 | High | Pending |
| FR-03 | `claudecode-terminal stop` 명령으로 봇 데몬 종료 | High | Pending |
| FR-04 | `claudecode-terminal status` 명령으로 실행 상태 확인 | Medium | Pending |
| FR-05 | Telegram `/ask <prompt>` 명령으로 Claude Code 실행 | High | Pending |
| FR-06 | Telegram `/project <path>` 명령으로 프로젝트 디렉토리 전환 | High | Pending |
| FR-07 | Telegram `/model <name>` 명령으로 모델 선택 | High | Pending |
| FR-08 | Telegram `/continue` 명령으로 이전 대화 이어가기 | Medium | Pending |
| FR-09 | Telegram `/system <prompt>` 명령으로 시스템 프롬프트 설정 | Medium | Pending |
| FR-10 | Telegram `/shell <cmd>` 명령으로 셸 명령 직접 실행 | High | Pending |
| FR-11 | Telegram `/history` 명령으로 최근 실행 이력 조회 | Medium | Pending |
| FR-12 | Telegram `/settings` 명령으로 현재 설정 확인 | Low | Pending |
| FR-13 | Telegram `/maxturns <n>` 명령으로 최대 턴 수 설정 | Medium | Pending |
| FR-14 | 위험 명령어 블랙리스트 필터링 (`rm -rf /`, `mkfs` 등) | High | Pending |
| FR-15 | 명령 실행 타임아웃 (기본 300초, 설정 가능) | High | Pending |
| FR-16 | 긴 출력 자동 분할 및 파일 전송 (4096자 초과 시) | High | Pending |
| FR-17 | 일반 텍스트 입력 시 Claude Code로 자동 전달 (기본 모드) | High | Pending |
| FR-18 | 실행 이력 로컬 SQLite 저장 | Medium | Pending |
| FR-19 | `claudecode-terminal config` 명령으로 설정 변경 | Medium | Pending |
| FR-20 | `claudecode-terminal logs` 명령으로 로그 확인 | Low | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Performance | Claude Code 실행 응답 시작까지 2초 이내 | Timestamp 비교 |
| Performance | 동시 명령 큐잉 (1명 사용자 기준 직렬 실행) | 동시 요청 테스트 |
| Security | Telegram User ID 화이트리스트 인증 | 미인가 사용자 테스트 |
| Security | 위험 명령어 패턴 매칭 차단 | 블랙리스트 테스트 |
| Reliability | 봇 프로세스 크래시 시 자동 재시작 (systemd/pm2) | 프로세스 킬 테스트 |
| Usability | 초기 설정 5분 이내 완료 | 신규 사용자 테스트 |
| Compatibility | Python 3.10+ 지원 | CI 매트릭스 |
| Compatibility | macOS, Linux 지원 | 크로스플랫폼 테스트 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] 모든 FR-01 ~ FR-20 기능 요구사항 구현
- [ ] `pip install claudecode-terminal`로 설치 가능
- [ ] `claudecode-terminal init` → `claudecode-terminal start`로 5분 이내 사용 시작
- [ ] README.md에 설치/사용 가이드 완성
- [ ] PyPI 패키지 배포 완료

### 4.2 Quality Criteria

- [ ] pytest 기반 테스트 커버리지 80% 이상
- [ ] ruff + mypy 타입 체크 통과
- [ ] GitHub Actions CI/CD 파이프라인 구축
- [ ] 주요 명령어에 대한 E2E 테스트

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Claude Code CLI가 설치되지 않은 환경 | High | Medium | 시작 시 `claude --version` 체크, 미설치 시 안내 메시지 |
| Telegram Bot Token 유출 | High | Low | `.env` 파일 권한 600, `.gitignore` 포함, 문서에 보안 가이드 |
| 긴 Claude Code 실행 시 Telegram 타임아웃 | Medium | High | 스트리밍 방식 출력 (중간 결과 주기적 전송), "실행 중..." 상태 메시지 |
| 셸 명령어 악용 (인가 사용자라도) | High | Low | 블랙리스트 + 명령 실행 확인 옵션 제공 |
| 다양한 OS 환경의 호환성 문제 | Medium | Medium | Python 표준 라이브러리 최대 활용, OS별 CI 테스트 |
| Claude Code API 변경/비호환 | Medium | Low | Claude Code CLI 버전 체크, 호환성 매트릭스 관리 |

---

## 6. Architecture Considerations

### 6.1 Project Level Selection

| Level | Characteristics | Recommended For | Selected |
|-------|-----------------|-----------------|:--------:|
| **Starter** | Simple structure (`components/`, `lib/`, `types/`) | Static sites, portfolios, landing pages | ☐ |
| **Dynamic** | Feature-based modules, BaaS integration | Web apps with backend, SaaS MVPs | ☒ |
| **Enterprise** | Strict layer separation, DI, microservices | High-traffic systems, complex architectures | ☐ |

### 6.2 Key Architectural Decisions

| Decision | Options | Selected | Rationale |
|----------|---------|----------|-----------|
| Language | Python / Node.js / Go | **Python** | Claude Code CLI가 Node.js지만, python-telegram-bot 생태계가 성숙하고 기존 프로젝트와 일관성 유지 |
| Package Type | pip (PyPI) / npm / standalone binary | **pip (PyPI)** | Python 에코시스템, 쉬운 배포와 설치 |
| Telegram SDK | python-telegram-bot / aiogram / telethon | **python-telegram-bot 21.x** | 기존 프로젝트에서 검증됨, async 지원, 활발한 커뮤니티 |
| DB | SQLite / JSON file / None | **SQLite** | 명령 이력 저장, 경량, 서버 불필요 |
| Config | .env / YAML / TOML | **TOML + .env** | pyproject.toml과 일관, .env로 시크릿 분리 |
| Process Mgmt | systemd / pm2 / 내장 데몬 | **내장 데몬 + systemd 템플릿** | 범용성, 선택적 systemd 지원 |
| CLI Framework | click / typer / argparse | **typer** | type hints 기반, 자동 --help 생성, 모던 Python |

### 6.3 Architecture Overview

```
claudecode-terminal (Python CLI Package)
┌─────────────────────────────────────────────────┐
│  CLI Layer (typer)                               │
│  ┌───────────────────────────────────────────┐   │
│  │ init │ start │ stop │ status │ config │ logs│  │
│  └───────────────────────────────────────────┘   │
│                       │                          │
│  Bot Layer (python-telegram-bot)                 │
│  ┌───────────────────────────────────────────┐   │
│  │ /ask  │ /shell │ /project │ /model │ ...  │   │
│  │       │        │          │        │      │   │
│  │ Security: User ID whitelist + Blacklist   │   │
│  └───────────────────────────────────────────┘   │
│                       │                          │
│  Service Layer                                   │
│  ┌──────────────┐  ┌──────────────┐             │
│  │ ClaudeRunner  │  │ ShellRunner  │             │
│  │ - execute()   │  │ - execute()  │             │
│  │ - continue()  │  │ - blacklist  │             │
│  │ - streaming   │  │ - timeout    │             │
│  └──────────────┘  └──────────────┘             │
│                       │                          │
│  Storage Layer                                   │
│  ┌──────────────┐  ┌──────────────┐             │
│  │ SQLite DB     │  │ Config TOML  │             │
│  │ - history     │  │ - settings   │             │
│  │ - sessions    │  │ - secrets    │             │
│  └──────────────┘  └──────────────┘             │
└─────────────────────────────────────────────────┘
```

### 6.4 Project Structure

```
claudecode-terminal/
├── pyproject.toml              # 패키지 설정, 의존성, CLI 엔트리포인트
├── README.md                   # 설치/사용 가이드 (영문)
├── LICENSE                     # MIT License
├── .env.example                # 환경변수 템플릿
├── .gitignore
├── src/
│   └── claudecode_terminal/
│       ├── __init__.py         # 버전 정보
│       ├── __main__.py         # python -m claudecode_terminal
│       ├── cli.py              # typer CLI 엔트리포인트
│       ├── config.py           # 설정 관리 (TOML + env)
│       ├── daemon.py           # 프로세스 데몬화
│       ├── bot/
│       │   ├── __init__.py
│       │   ├── app.py          # Bot Application 생성/시작
│       │   ├── handlers.py     # Telegram 명령어 핸들러
│       │   └── security.py     # 인증 + 블랙리스트
│       ├── services/
│       │   ├── __init__.py
│       │   ├── claude.py       # Claude Code CLI 실행
│       │   ├── shell.py        # 셸 명령어 실행
│       │   └── streaming.py    # 긴 출력 스트리밍 처리
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── database.py     # SQLite 관리
│       │   └── models.py       # 데이터 모델
│       └── utils/
│           ├── __init__.py
│           ├── formatting.py   # 메시지 포맷팅/분할
│           └── system.py       # 시스템 체크 유틸리티
├── tests/
│   ├── conftest.py
│   ├── test_cli.py
│   ├── test_handlers.py
│   ├── test_claude.py
│   ├── test_shell.py
│   └── test_security.py
├── docs/
│   ├── 01-plan/
│   │   └── features/
│   └── 02-design/
│       └── features/
└── docker/                     # 선택적 Docker 지원
    ├── Dockerfile
    └── docker-compose.yml
```

---

## 7. Convention Prerequisites

### 7.1 Existing Project Conventions

- [ ] `CLAUDE.md` has coding conventions section
- [ ] `docs/01-plan/conventions.md` exists
- [ ] ESLint configuration
- [ ] Prettier configuration
- [ ] TypeScript configuration

### 7.2 Conventions to Define

| Category | Current State | To Define | Priority |
|----------|---------------|-----------|:--------:|
| **Naming** | Missing | snake_case (Python), kebab-case (CLI commands) | High |
| **Folder structure** | Missing | src/claudecode_terminal/ 모듈 구조 | High |
| **Import order** | Missing | stdlib → third-party → local (isort) | Medium |
| **Environment variables** | Missing | CLAUDECODE_* 접두사 통일 | Medium |
| **Error handling** | Missing | 사용자 친화적 에러 메시지 + 로그 분리 | Medium |
| **Logging** | Missing | structlog JSON 포맷, 레벨별 파일 분리 | Medium |

### 7.3 Environment Variables

| Variable | Purpose | Required | Default |
|----------|---------|:--------:|---------|
| `CLAUDECODE_BOT_TOKEN` | Telegram Bot API 토큰 | Yes | - |
| `CLAUDECODE_ALLOWED_USERS` | 허용된 Telegram User ID (콤마 구분) | Yes | - |
| `CLAUDECODE_DEFAULT_PROJECT` | 기본 프로젝트 디렉토리 | No | `~/projects` |
| `CLAUDECODE_DEFAULT_MODEL` | 기본 Claude 모델 | No | `sonnet` |
| `CLAUDECODE_TIMEOUT` | Claude Code 실행 타임아웃 (초) | No | `300` |
| `CLAUDECODE_SHELL_TIMEOUT` | 셸 명령 타임아웃 (초) | No | `30` |
| `CLAUDECODE_MAX_OUTPUT` | 최대 출력 길이 (자) | No | `4096` |
| `CLAUDECODE_DB_PATH` | SQLite DB 경로 | No | `~/.claudecode-terminal/history.db` |
| `CLAUDECODE_LOG_LEVEL` | 로그 레벨 | No | `WARNING` |

---

## 8. User Experience Flow

### 8.1 설치 및 초기 설정

```bash
# 1. 설치
pip install claudecode-terminal

# 2. 초기 설정 (대화형 마법사)
claudecode-terminal init
# → Telegram Bot Token 입력 (BotFather에서 생성)
# → 허용할 Telegram User ID 입력
# → 기본 프로젝트 디렉토리 설정
# → 기본 모델 선택
# → 설정 파일 생성: ~/.claudecode-terminal/config.toml

# 3. 봇 시작
claudecode-terminal start
# → "Bot started! Send /help to your bot on Telegram"

# 4. (선택) 백그라운드 데몬으로 실행
claudecode-terminal start --daemon
```

### 8.2 Telegram 사용 흐름

```
User: /help
Bot:  ClaudeCode Terminal v0.1.0
      ─────────────────────────
      /ask <prompt>    - Claude Code에 질문
      /shell <cmd>     - 셸 명령어 실행
      /project <path>  - 프로젝트 전환
      /model <name>    - 모델 변경 (opus/sonnet/haiku)
      /continue        - 이전 대화 이어가기
      /system <prompt> - 시스템 프롬프트 설정
      /maxturns <n>    - 최대 턴 수 설정
      /history         - 최근 실행 이력
      /settings        - 현재 설정 확인
      /help            - 도움말

User: /project ~/my-app
Bot:  Project switched to: ~/my-app

User: login 기능을 만들어줘
Bot:  🔄 Claude Code 실행 중...
      ────────────────────────
      (Claude Code 실행 결과가 여기에 표시됨)
      ...
      ✅ 완료 (12.3초)

User: /shell git status
Bot:  On branch main
      Changes not staged for commit:
        modified: src/auth/login.ts
      ...
```

---

## 9. 기존 프로젝트와의 차이점

| 항목 | claude-terminal (기존) | claudecode-terminal (신규) |
|------|----------------------|--------------------------|
| **배포 형태** | Docker Compose 서비스 | pip 패키지 (CLI) |
| **설치 대상** | 개인 서버 | 누구나 로컬 PC |
| **주요 기능** | 웹터미널 + 대시보드 + Claude + Tesla | Claude Code 원격 실행에 집중 |
| **웹 UI** | React 프론트엔드 | 없음 (Telegram만) |
| **시스템 모니터링** | CPU/메모리/디스크/네트워크 | 없음 |
| **인증** | JWT + API Key + User ID | Telegram User ID만 |
| **설정** | .env + pydantic-settings | TOML + .env (시크릿만) |
| **프로세스 관리** | Docker 컨테이너 | 내장 데몬 / systemd |

---

## 10. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Claude Code CLI 미설치 환경 | High | Medium | 시작 시 버전 체크, 설치 안내 제공 |
| Bot Token 유출 | High | Low | config.toml 권한 600, .gitignore, 문서화 |
| 긴 실행 시간 (Telegram 응답 지연) | Medium | High | 중간 상태 메시지, 스트리밍 출력 |
| PyPI 패키지명 충돌 | Low | Medium | 사전 확인 후 예약 |
| 크로스 플랫폼 호환성 (Windows) | Medium | Medium | v1은 macOS/Linux만, v2에서 Windows |

---

## 11. Next Steps

1. [ ] Design 문서 작성 (`claudecode-terminal.design.md`)
2. [ ] `pyproject.toml` 구성 및 프로젝트 스캐폴딩
3. [ ] 핵심 모듈 구현 (config → bot → claude service → cli)
4. [ ] PyPI 배포 테스트
5. [ ] README.md 작성 (영문, 한국어 동시)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-02-22 | Initial draft | js |
