# Dify A2A Gateway

[![Tests](https://img.shields.io/badge/tests-52%20passed-success)](tests/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)](https://fastapi.tiangolo.com/)
[![Version](https://img.shields.io/badge/version-0.4.0-blue)](main.py)

A2A Protocol gateway for Dify - 완전한 A2A 표준 준수 대화 에이전트 통신 게이트웨이

## 개요

Dify의 Chat API를 [A2A Protocol](https://a2a-protocol.org/) (Agent-to-Agent JSON-RPC 2.0) 표준으로 감싸는 게이트웨이 서비스입니다. A2A 클라이언트가 Dify Agent와 실시간 스트리밍 대화를 수행하고, Task API를 통해 작업 상태를 관리할 수 있습니다.

## ✨ 주요 특징

### Phase 2.1: A2A 표준 완전 준수 (v0.4.0) 🎯
- **A2A 표준 100% 준수**: message.send, Task API, SSE 이벤트 모두 표준 준수
- **Parts 기반 Message**: TextPart, FilePart, DataPart 지원
- **Task.kind 필드**: A2A 표준 타입 판별자 추가
- **TaskStatusUpdateEvent**: A2A 표준 상태 업데이트 이벤트
- **TaskArtifactUpdateEvent**: A2A 표준 결과물 업데이트 이벤트

### Phase 2: Task API 지원 (v0.3.0)
- **Task 기반 아키텍처**: 모든 대화가 Task 객체로 관리됨
- **Context 지속성**: Task metadata에 Dify conversation_id 저장으로 다중 턴 대화 완벽 지원
- **Task API 엔드포인트**: `tasks/get`, `tasks/list`, `tasks/cancel`
- **InMemory Task Store**: Thread-safe 작업 저장소

## ⚠️ Breaking Changes

### v0.4.0 (Phase 2.1 - A2A 표준 준수)

**message.send 요청 형식 변경 (Parts 기반):**
```diff
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message.send",
  "params": {
-   "messages": [{"role": "user", "content": "Hello"}],
+   "messages": [{"role": "user", "parts": [{"type": "text", "text": "Hello"}]}],
-   "contextId": "session-123",
-   "stream": true
+   "configuration": {"stream": true},
+   "contextId": "session-123"  // 선택적 (확장 필드)
  }
}
```

**SSE 이벤트 형식 변경 (A2A 표준):**
```diff
- {"result": {"type": "content_delta", "delta": "Hello", "contextId": "...", "taskId": "..."}}
- {"result": {"type": "message_end", "contextId": "...", "taskId": "..."}}
+ {"result": {"type": "task_status_update", "taskId": "...", "status": "completed", "contextId": "..."}}
+ {"result": {"type": "task_artifact_update", "taskId": "...", "artifact": {...}, "contextId": "..."}}
```

**Task 모델 변경:**
```diff
{
  "id": "task-abc-123",
  "contextId": "session-123",
  "status": "completed",
+ "kind": "task",  // A2A 표준 타입 판별자
  ...
}
```

### v0.3.0 (Phase 2 - Task API)

**message.send 응답에 taskId 추가:**
```diff
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "type": "content_delta",
    "delta": "Hello!",
    "contextId": "session-123",
+   "taskId": "task-abc-123"
  }
}
```

**새로운 Task API 엔드포인트:**
- `POST /tasks/get` - Task 조회
- `POST /tasks/list` - Task 목록 조회
- `POST /tasks/cancel` - Task 취소

**변경 이유:**
- Dify conversation_id를 Task.metadata에 저장하여 컨텍스트 완벽 유지
- Phase 1의 "대화 이어가기" 문제 해결
- Multi-modal 및 복잡한 작업 처리 기반 마련

### v0.2.0 (Phase 1 - Protocol 표준화)

**주요 변경사항:**
1. `conversation_id` → `contextId` 변경
2. `chat.create` → `message.send` 메서드명 변경
3. Redis 의존성 제거
4. User ID 로직 단순화 (contextId → user_id 직접 매핑)

자세한 마이그레이션 가이드는 [v0.2.0 Migration](#v020-migration-guide) 참조

## 아키텍처

### Task 기반 흐름 (v0.3.0)

```
┌─────────────┐                  ┌──────────────┐                  ┌──────────┐
│ A2A Client  │─────────────────▶│ A2A Gateway  │─────────────────▶│   Dify   │
│             │  message.send    │   (FastAPI)  │  POST /chat-msgs │   API    │
│             │                  │              │                  │          │
│             │  ┌──────────┐    │  ┌────────┐  │                  │          │
│             │  │ taskId   │◀───│  │  Task  │  │──────────────────│          │
│             │  └──────────┘    │  │ Store  │  │                  │          │
│             │                  │  └────────┘  │                  │          │
│             │◀─────────────────│              │◀─────────────────│          │
│             │  SSE streaming   │              │  SSE streaming   │          │
└─────────────┘                  └──────────────┘                  └──────────┘
                                         │
                                         │ Task API
                                         ▼
                                 tasks/get, tasks/list,
                                 tasks/cancel
```

### Context 지속성 보장

```
Request 1 (contextId: session-123)
    ↓
  Task 1 created (task-abc)
    ↓
  Dify conversation_id: conv-dify-456
    ↓
  Task.metadata = {"dify_conversation_id": "conv-dify-456"}

Request 2 (contextId: session-123)
    ↓
  Task 2 created (task-def)
    ↓
  이전 Task 조회 → conv-dify-456 재사용
    ↓
  Dify가 이전 대화 기억! ✅
```

## 빠른 시작

### 전제조건

- Python 3.11 또는 3.12
- Docker & Docker Compose (선택)

### 1. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일 예시:
```bash
# Dify API 연결
DIFY_API_URL=https://api.dify.ai  # 또는 http://localhost:5001
DIFY_API_KEY=app-your-api-key-here

# Gateway 설정
PORT=8080
HOST=0.0.0.0
LOG_LEVEL=INFO

# CORS 설정
CORS_ORIGINS=["*"]
```

### 2. Docker Compose로 실행 (권장)

```bash
cd ../docker
docker compose up a2a-gateway
```

Gateway는 `http://localhost:8080`에서 실행됩니다.

### 3. 로컬 개발 실행

```bash
# 가상환경 생성
python3.12 -m venv .venv-py312
source .venv-py312/bin/activate  # Windows: .venv-py312\Scripts\activate

# 의존성 설치
pip install -e .

# 개발 서버 실행
uvicorn main:app --reload --port 8080
```

## API 사용법

### Health Check

```bash
curl http://localhost:8080/health
```

**응답:**
```json
{
  "status": "ok",
  "service": "dify-a2a-gateway",
  "version": "0.3.0"
}
```

### 1. 기본 대화 (message.send)

```bash
curl -N -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "msg-1",
    "method": "message.send",
    "params": {
      "messages": [
        {"role": "user", "content": "안녕하세요"}
      ],
      "contextId": "session-123"
    }
  }'
```

**SSE 스트리밍 응답:**
```
data: {"jsonrpc":"2.0","id":"msg-1","result":{"type":"content_delta","delta":"안녕하세요!","contextId":"session-123","taskId":"task-abc-123"}}

data: {"jsonrpc":"2.0","id":"msg-1","result":{"type":"message_end","contextId":"session-123","taskId":"task-abc-123"}}
```

### 2. 대화 이어가기 (Context 유지)

```bash
# 첫 번째 메시지
curl -N -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "msg-1",
    "method": "message.send",
    "params": {
      "messages": [{"role": "user", "content": "제 이름은 김철수입니다"}],
      "contextId": "session-123"
    }
  }'

# 두 번째 메시지 (동일한 contextId)
curl -N -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "msg-2",
    "method": "message.send",
    "params": {
      "messages": [{"role": "user", "content": "제 이름이 뭐였죠?"}],
      "contextId": "session-123"
    }
  }'
```

**응답:** Dify가 "김철수"라고 기억함 ✅

### 3. Task 조회 (tasks/get)

```bash
curl -X POST http://localhost:8080/tasks/get \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "tasks/get",
    "params": {
      "taskId": "task-abc-123"
    }
  }'
```

**응답:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "id": "task-abc-123",
    "contextId": "session-123",
    "status": "completed",
    "history": [
      {
        "role": "user",
        "parts": [{"type": "text", "text": "안녕하세요"}],
        "timestamp": "2025-11-07T12:00:00Z"
      },
      {
        "role": "agent",
        "parts": [{"type": "text", "text": "안녕하세요!"}],
        "timestamp": "2025-11-07T12:00:01Z"
      }
    ],
    "artifacts": [
      {
        "artifactId": "artifact-xyz",
        "name": "Dify Response",
        "parts": [{"type": "text", "text": "안녕하세요!"}],
        "metadata": {"event_type": "message"}
      }
    ],
    "metadata": {
      "dify_conversation_id": "conv-dify-456"
    },
    "createdAt": "2025-11-07T12:00:00Z",
    "updatedAt": "2025-11-07T12:00:01Z",
    "completedAt": "2025-11-07T12:00:01Z"
  }
}
```

### 4. Task 목록 조회 (tasks/list)

```bash
curl -X POST http://localhost:8080/tasks/list \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "2",
    "method": "tasks/list",
    "params": {
      "contextId": "session-123",
      "status": "completed",
      "limit": 10,
      "offset": 0
    }
  }'
```

**응답:**
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "result": {
    "tasks": [
      {
        "id": "task-abc-123",
        "contextId": "session-123",
        "status": "completed",
        ...
      },
      {
        "id": "task-def-456",
        "contextId": "session-123",
        "status": "completed",
        ...
      }
    ],
    "total": 2
  }
}
```

### 5. Task 취소 (tasks/cancel)

```bash
curl -X POST http://localhost:8080/tasks/cancel \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "3",
    "method": "tasks/cancel",
    "params": {
      "taskId": "task-running-789"
    }
  }'
```

**응답:**
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "result": {
    "id": "task-running-789",
    "status": "canceled",
    ...
  }
}
```

## 프로젝트 구조

```
a2a-gateway/
├── main.py                      # FastAPI 애플리케이션 (v0.3.0)
├── config.py                    # 환경변수 기반 설정
├── models/
│   ├── a2a.py                  # A2A Protocol 모델 (Task, Artifact, Parts)
│   └── dify.py                 # Dify API 모델
├── services/
│   ├── task_store.py           # InMemory Task 저장소 (Thread-safe)
│   ├── task_manager.py         # Task 생명주기 관리
│   ├── dify_client.py          # Dify API HTTP 클라이언트
│   └── translator.py           # A2A ↔ Dify 변환 (레거시)
├── routers/
│   ├── chat.py                 # /a2a 엔드포인트 (Task 기반)
│   └── tasks.py                # /tasks/* 엔드포인트 (NEW)
├── tests/
│   ├── unit/                   # 단위 테스트 (49개)
│   │   ├── test_models.py
│   │   ├── test_task_store.py
│   │   ├── test_task_manager.py
│   │   └── test_translator.py
│   └── integration/            # 통합 테스트 (11개)
│       ├── test_task_api.py    # Task API E2E (NEW)
│       └── test_e2e.py         # 기존 E2E (Dify 필요)
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

## 개발

### 개발 환경 설정

```bash
# Python 3.12 가상환경 생성
python3.12 -m venv .venv-py312
source .venv-py312/bin/activate

# 개발 의존성 포함 설치
pip install -e ".[dev]"
```

### 테스트

```bash
# 전체 테스트 실행 (60개: 49 unit + 11 integration)
pytest tests/ -v

# 단위 테스트만 실행 (49개 - Dify API 불필요)
pytest tests/unit/ -v

# Task API 통합 테스트 (11개 - Dify API 불필요, Mock 사용)
pytest tests/integration/test_task_api.py -v

# E2E 테스트 (10개 - 실제 Dify API 필요)
pytest tests/integration/test_e2e.py -v

# 커버리지 포함 테스트
pytest tests/ --cov=. --cov-report=html
```

**테스트 구성 (총 60개):**
- **Unit Tests (49)**: 모델, Task Store, Task Manager, 변환기
  - test_models.py: 14개
  - test_task_store.py: 14개
  - test_task_manager.py: 13개
  - test_translator.py: 8개
- **Integration Tests (11)**: Task API E2E (Dify Mock)
  - Task 기반 message.send: 3개
  - tasks/get API: 2개
  - tasks/list API: 3개
  - tasks/cancel API: 3개
- **E2E Tests (10)**: 전체 흐름 (실제 Dify API 필요)

### 코드 품질

```bash
# 코드 포맷팅
ruff format .

# Linting
ruff check .

# 자동 수정
ruff check --fix .
```

## Task API 상세

### Task 객체 구조

```python
class Task(BaseModel):
    id: str                          # task-{uuid}
    contextId: str                   # 세션 식별자
    status: TaskStatus               # pending/running/completed/failed/canceled
    history: list[Message]           # 대화 히스토리 (Parts 기반)
    artifacts: list[Artifact]        # 실행 결과물
    metadata: dict[str, Any]         # dify_conversation_id 저장
    createdAt: datetime
    updatedAt: datetime
    completedAt: Optional[datetime]
    error: Optional[str]
```

### TaskStatus

- `pending`: Task 생성됨, 아직 실행되지 않음
- `running`: Dify API 호출 중
- `completed`: 정상 완료
- `failed`: 실행 중 에러 발생
- `canceled`: 사용자가 취소

### Parts 구조 (Multi-modal 준비)

```python
class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str

class FilePart(BaseModel):
    type: Literal["file"] = "file"
    name: str
    mimeType: Optional[str] = None
    uri: Optional[str] = None
    bytes: Optional[str] = None  # Base64

class DataPart(BaseModel):
    type: Literal["data"] = "data"
    data: dict[str, Any]
```

### Artifact 구조

```python
class Artifact(BaseModel):
    artifactId: str
    name: Optional[str] = None
    description: Optional[str] = None
    parts: list[Part]                # 결과물 내용
    metadata: dict[str, Any]
    createdAt: datetime
```

## 환경변수

### 필수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DIFY_API_KEY` | Dify App API Key | - (필수) |

### Gateway 설정

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DIFY_API_URL` | Dify API 엔드포인트 | `http://api:5001` |
| `PORT` | Gateway 포트 | `8080` |
| `HOST` | 바인드 주소 | `0.0.0.0` |
| `LOG_LEVEL` | 로그 레벨 | `INFO` |
| `CORS_ORIGINS` | CORS 허용 출처 | `["*"]` |

## 로드맵

### Phase 1: Protocol 표준화 ✅
- contextId 기반 세션 관리
- message.send 메서드
- Redis 제거, 단순화

### Phase 2: Task API ✅ (Current)
- Task 기반 아키텍처
- InMemory Task Store
- tasks/get, tasks/list, tasks/cancel
- Context 완벽 지속성

### Phase 3: 확장성 (계획)
- Redis/DB 기반 Task Store (영속화)
- Task 만료 정책 (TTL)
- Task 검색 및 필터링 강화
- WebSocket 지원

### Phase 4: Multi-modal (계획)
- File upload (FilePart)
- Image/Audio 처리
- Binary data (DataPart)
- Dify Vision API 연동

## 문제 해결

### 1. Task가 생성되지 않음

**증상:** message.send 응답에 taskId가 없음

**해결:**
```bash
# 서버 로그 확인
docker compose logs a2a-gateway -f

# Task Store 상태 확인
curl http://localhost:8080/tasks/list \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":"1","method":"tasks/list","params":{}}'
```

### 2. Context가 유지되지 않음

**확인사항:**
1. 동일한 `contextId` 사용했는지 확인
2. Task.metadata에 `dify_conversation_id`가 저장되었는지 확인
3. Dify API가 conversation_id를 정상적으로 반환하는지 확인

**디버깅:**
```bash
# Task 상세 조회
curl http://localhost:8080/tasks/get \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc":"2.0",
    "id":"1",
    "method":"tasks/get",
    "params":{"taskId":"task-xxx"}
  }'

# metadata에 dify_conversation_id 확인
```

### 3. InMemory 데이터 소실

**증상:** 서버 재시작 후 Task 목록이 사라짐

**설명:** Phase 2는 InMemory 저장소 사용
- 서버 재시작 시 모든 Task 데이터 소실 (정상 동작)
- Phase 3에서 Redis/DB 영속화 예정

**임시 해결:** 중요한 Task는 클라이언트에서 별도 저장

## v0.2.0 Migration Guide

### 요청 형식 변경

```diff
{
  "jsonrpc": "2.0",
  "id": "1",
- "method": "chat.create",
+ "method": "message.send",
  "params": {
    "messages": [{"role": "user", "content": "Hello"}],
-   "conversation_id": "conv-123",
+   "contextId": "session-123",
    "stream": true
  }
}
```

### 응답 형식 변경 (v0.2.0 → v0.3.0)

```diff
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "type": "content_delta",
    "delta": "Hello!",
-   "conversation_id": "conv-123"
+   "contextId": "session-123",
+   "taskId": "task-abc-123"
  }
}
```

## 참고 자료

- [A2A Protocol Specification](https://a2a-protocol.org/)
- [Dify API Documentation](https://docs.dify.ai/guides/application-publishing/developing-with-apis)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic V2 Documentation](https://docs.pydantic.dev/latest/)

## 라이센스

MIT License - 자세한 내용은 [LICENSE](../LICENSE) 파일 참조

## 기여

이슈 및 PR을 환영합니다!

### 기여 가이드라인

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest tests/ -v`)
4. Commit your changes (`git commit -m 'feat: Add amazing feature'`)
5. Push to the branch (`git push origin feature/amazing-feature`)
6. Open a Pull Request

### 개발 관련 문의

- GitHub Issues: [dify/issues](https://github.com/langgenius/dify/issues)
- Discussions: [dify/discussions](https://github.com/langgenius/dify/discussions)
