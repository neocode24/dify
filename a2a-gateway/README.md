# Dify A2A Gateway

[![Tests](https://img.shields.io/badge/tests-53%20passed-success)](tests/)
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

## 📐 아키텍처 상세 분석

### 전체 흐름: A2A Client → Gateway → Dify

```
┌─────────────────┐
│   A2A Client    │  (외부 클라이언트 - 웹앱, CLI, 다른 Agent 등)
│                 │
│ • contextId 관리│
│ • message.send  │
│ • Task 조회     │
└────────┬────────┘
         │ JSON-RPC 2.0
         │ {"method": "message.send", "params": {"messages": [...], "contextId": "session-123"}}
         ▼
┌─────────────────────────────────────────────────────────┐
│            A2A-Gateway (FastAPI)                        │
│                                                         │
│  ┌──────────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │ Router       │  │ TaskManager │  │ TaskStore    │  │
│  │ (/a2a)       │─▶│             │─▶│ (InMemory)   │  │
│  └──────────────┘  └─────────────┘  └──────────────┘  │
│         │                │                             │
│         │                ▼                             │
│         │      1. contextId로 기존 Task 검색          │
│         │      2. conversation_id 추출 (metadata)     │
│         │      3. 새 Task 생성 (pending)              │
│         │                                              │
│         ▼                                              │
│  ┌──────────────┐                                      │
│  │ Dify Client  │  (httpx + SSE)                       │
│  └──────┬───────┘                                      │
└─────────┼──────────────────────────────────────────────┘
          │ POST /v1/chat-messages
          │ {"query": "...", "conversation_id": "conv-dify-456", "user": "session-123"}
          ▼
┌─────────────────┐
│   Dify API      │  (실제 AI 엔진)
│                 │
│ • 대화 히스토리 │
│ • LLM 실행      │
│ • conversation  │
│   관리          │
└────────┬────────┘
         │ SSE Streaming
         │ {"event": "message", "answer": "안녕하세요!", "conversation_id": "conv-dify-456"}
         ▼
┌─────────────────────────────────────────────────────────┐
│            A2A-Gateway                                  │
│                                                         │
│  TaskManager:                                           │
│    1. SSE 이벤트 수신 및 변환                           │
│    2. Artifact 생성 (텍스트 응답)                       │
│    3. Task 상태 업데이트 (running → completed)          │
│    4. metadata에 conversation_id 저장                   │
│                                                         │
└────────┬────────────────────────────────────────────────┘
         │ SSE (A2A 표준 이벤트)
         │ {"result": {"type": "task_status_update", "taskId": "...", "status": "completed"}}
         │ {"result": {"type": "task_artifact_update", "artifact": {...}}}
         ▼
┌─────────────────┐
│   A2A Client    │
│                 │
│ • Task 완료     │
│ • Artifact 수신 │
└─────────────────┘
```

### Gateway vs Dify 역할 분담

| 책임 영역 | A2A-Gateway | Dify API |
|-----------|-------------|----------|
| **프로토콜** | A2A Protocol (JSON-RPC 2.0) | REST + SSE |
| **세션 ID** | contextId 관리 ✅ | conversation_id 관리 ✅ |
| **Task 관리** | Task 생성/저장/조회/취소 ✅ | ✗ |
| **대화 실행** | ✗ | LLM 실행, 워크플로우 ✅ |
| **대화 히스토리** | Task.history (A2A 형식) ✅ | conversation 저장소 ✅ |
| **SSE 스트리밍** | Gateway → Client ✅ | Dify → Gateway ✅ |
| **Artifact 생성** | SSE 이벤트 → Artifact ✅ | ✗ |
| **표준 준수** | A2A Protocol ✅ | Dify API ✅ |

**핵심 포인트:**
- Gateway는 **프로토콜 변환기** + **Task 관리자** 역할
- Dify는 **실제 AI 엔진** + **대화 저장소** 역할
- contextId ↔ conversation_id 매핑은 Gateway의 핵심 책임

### 1:1 Gateway-Agent 매핑

**아키텍처 원칙: 1 Gateway Instance = 1 Dify Agent**

```
┌─────────────────────────────────────────────────────┐
│              Multi-Agent 환경 (Phase 3 계획)        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐      ┌──────────────┐            │
│  │ A2A Client 1 │      │ A2A Client 2 │            │
│  └──────┬───────┘      └──────┬───────┘            │
│         │                     │                     │
│         │                     │                     │
│         ▼                     ▼                     │
│  ┌─────────────────────────────────────┐            │
│  │   Gateway Instance 1                │            │
│  │   DIFY_API_KEY = app-agent-A        │──────┐    │
│  │   AgentCard: "Customer Support AI"  │      │    │
│  └─────────────────────────────────────┘      │    │
│                                               │    │
│  ┌─────────────────────────────────────┐      │    │
│  │   Gateway Instance 2                │      │    │
│  │   DIFY_API_KEY = app-agent-B        │──────┤    │
│  │   AgentCard: "Sales Assistant AI"   │      │    │
│  └─────────────────────────────────────┘      │    │
│                                               │    │
│  ┌─────────────────────────────────────┐      │    │
│  │   Gateway Instance 3                │      │    │
│  │   DIFY_API_KEY = app-agent-C        │──────┘    │
│  │   AgentCard: "Data Analyst AI"      │           │
│  └─────────────────────────────────────┘           │
│                     │                              │
│                     ▼                              │
│          ┌──────────────────┐                      │
│          │  Dify Backend    │                      │
│          │                  │                      │
│          │  • Agent A       │                      │
│          │  • Agent B       │                      │
│          │  • Agent C       │                      │
│          └──────────────────┘                      │
└─────────────────────────────────────────────────────┘
```

**현재 구현 (Phase 2.1):**
- 각 Gateway는 **하나의 DIFY_API_KEY**로 설정됨
- 하나의 Dify App (Agent)과만 통신
- 여러 Client가 동일 Gateway 공유 가능 (contextId로 구분)

**향후 계획 (Phase 3 - AgentCard):**
- AgentCard 설정으로 Gateway-Agent 매핑 명시
- Multi-agent 라우팅 (클라이언트가 Agent 선택)
- Agent 간 협업 (Agent-to-Agent 통신)

### Task 관리 책임: Gateway = A2A Server

**Gateway의 역할:**

```
A2A Server (Gateway) 책임:
├─ Task Lifecycle 관리
│  ├─ Task 생성 (message.send 호출 시)
│  ├─ 상태 전환 (pending → running → completed/failed/canceled)
│  └─ Task 저장/조회/취소
│
├─ A2A Protocol 표준 준수
│  ├─ JSON-RPC 2.0 요청/응답
│  ├─ TaskStatusUpdateEvent 발행
│  └─ TaskArtifactUpdateEvent 발행
│
├─ Session 매핑
│  ├─ contextId (A2A) → conversation_id (Dify)
│  └─ Task.metadata에 conversation_id 저장
│
└─ SSE 연결 관리
   ├─ Dify SSE 스트림 수신
   ├─ A2A 표준 이벤트로 변환
   └─ Client에게 전달
```

**Gateway가 하지 않는 것:**
- ✗ 실제 AI 응답 생성 (← Dify LLM)
- ✗ 대화 내용 장기 저장 (← Dify conversation)
- ✗ 비즈니스 로직 실행 (← Dify workflow)
- ✗ Multi-agent 라우팅 (← Phase 3 계획)

## 🔄 Conversation 지속성: contextId ↔ conversation_id

### contextId 이해하기 (클라이언트 관리)

**정의:** A2A Protocol 표준의 세션 식별자

**특징:**
- 클라이언트가 생성하고 관리
- 동일한 contextId = 동일한 대화 세션
- A2A 표준 필드 (`params.contextId`)
- 형식: 자유 (예: `session-user-123`, `conv-alice-2024-11-07`)

**예시:**
```javascript
// 사용자 Alice의 첫 번째 대화
const contextId1 = "session-alice-chat1";

// 사용자 Alice의 두 번째 대화 (별도 세션)
const contextId2 = "session-alice-chat2";

// 사용자 Bob의 대화
const contextId3 = "session-bob-chat1";
```

### conversation_id 이해하기 (Gateway 내부 관리)

**정의:** Dify 내부 대화 ID (클라이언트에게 숨김)

**특징:**
- Dify API가 생성 (예: `conv-dify-456`)
- Gateway가 Task.metadata에 저장
- 클라이언트는 **절대 알 필요 없음** (내부 구현)
- Multi-turn 대화 시 재사용하여 히스토리 유지

**흐름:**
```python
# 1차 요청 (contextId: "session-123")
request1 = {
    "method": "message.send",
    "params": {
        "contextId": "session-123",
        "messages": [{"role": "user", "parts": [{"type": "text", "text": "안녕"}]}]
    }
}

# Gateway 내부:
# 1. contextId로 기존 Task 검색 → 없음
# 2. 새 Task 생성 (task-abc)
# 3. Dify API 호출 (conversation_id 없음)
# 4. Dify 응답: conversation_id = "conv-dify-456"
# 5. Task.metadata = {"dify_conversation_id": "conv-dify-456"}

# 2차 요청 (동일한 contextId)
request2 = {
    "method": "message.send",
    "params": {
        "contextId": "session-123",  # 동일!
        "messages": [{"role": "user", "parts": [{"type": "text", "text": "내 이름은?"}]}]
    }
}

# Gateway 내부:
# 1. contextId로 기존 Task 검색 → task-abc 발견
# 2. task-abc.metadata에서 "conv-dify-456" 추출
# 3. Dify API 호출 (conversation_id = "conv-dify-456")
# 4. Dify가 이전 대화 기억하고 응답!
```

### Multi-turn 대화 Step-by-step 예시

**시나리오:** 사용자가 3턴 대화 (이름 → 기억 확인 → 추가 질문)

#### Turn 1: 이름 알려주기

**클라이언트 요청:**
```bash
curl -N -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "msg-1",
    "method": "message.send",
    "params": {
      "contextId": "session-user-alice",
      "messages": [
        {
          "role": "user",
          "parts": [{"type": "text", "text": "제 이름은 김철수입니다"}]
        }
      ],
      "configuration": {"stream": true}
    }
  }'
```

**Gateway 내부 처리:**
```
1. contextId "session-user-alice"로 Task 검색 → 없음
2. Task 생성:
   - id: "task-abc-123"
   - contextId: "session-user-alice"
   - status: "pending"
   - metadata: {}
3. Dify API 호출:
   POST /v1/chat-messages
   {
     "query": "제 이름은 김철수입니다",
     "user": "session-user-alice",
     "response_mode": "streaming"
     // conversation_id 없음 (첫 대화)
   }
4. Dify 응답:
   {
     "answer": "안녕하세요, 김철수님!",
     "conversation_id": "conv-dify-456"  // Dify가 생성
   }
5. Task 업데이트:
   - status: "completed"
   - metadata: {"dify_conversation_id": "conv-dify-456"}
   - artifacts: [Artifact with "안녕하세요, 김철수님!"]
```

**클라이언트 응답 (SSE):**
```
data: {"jsonrpc":"2.0","id":"msg-1","result":{"type":"task_status_update","taskId":"task-abc-123","status":"completed"}}

data: {"jsonrpc":"2.0","id":"msg-1","result":{"type":"task_artifact_update","taskId":"task-abc-123","artifact":{"artifactId":"artifact-1","parts":[{"type":"text","text":"안녕하세요, 김철수님!"}]}}}
```

#### Turn 2: 이름 기억 확인

**클라이언트 요청:**
```bash
curl -N -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "msg-2",
    "method": "message.send",
    "params": {
      "contextId": "session-user-alice",  # 동일한 contextId!
      "messages": [
        {
          "role": "user",
          "parts": [{"type": "text", "text": "제 이름이 뭐였죠?"}]
        }
      ],
      "configuration": {"stream": true}
    }
  }'
```

**Gateway 내부 처리:**
```
1. contextId "session-user-alice"로 Task 검색
   → task-abc-123 발견! (status: completed)
2. task-abc-123.metadata에서 conversation_id 추출
   → "conv-dify-456"
3. 새 Task 생성:
   - id: "task-def-456"
   - contextId: "session-user-alice"
   - status: "pending"
   - metadata: {}
4. Dify API 호출:
   POST /v1/chat-messages
   {
     "query": "제 이름이 뭐였죠?",
     "user": "session-user-alice",
     "conversation_id": "conv-dify-456",  // 이전 대화 ID 전달!
     "response_mode": "streaming"
   }
5. Dify 응답:
   {
     "answer": "김철수님이라고 하셨습니다.",  // 이전 대화 기억!
     "conversation_id": "conv-dify-456"
   }
6. Task 업데이트:
   - status: "completed"
   - metadata: {"dify_conversation_id": "conv-dify-456"}
   - artifacts: [Artifact with "김철수님이라고 하셨습니다."]
```

**클라이언트 응답 (SSE):**
```
data: {"jsonrpc":"2.0","id":"msg-2","result":{"type":"task_status_update","taskId":"task-def-456","status":"completed"}}

data: {"jsonrpc":"2.0","id":"msg-2","result":{"type":"task_artifact_update","taskId":"task-def-456","artifact":{"artifactId":"artifact-2","parts":[{"type":"text","text":"김철수님이라고 하셨습니다."}]}}}
```

#### Turn 3: 추가 질문

**클라이언트 요청:**
```bash
curl -N -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "msg-3",
    "method": "message.send",
    "params": {
      "contextId": "session-user-alice",
      "messages": [
        {
          "role": "user",
          "parts": [{"type": "text", "text": "오늘 날씨는 어때요?"}]
        }
      ],
      "configuration": {"stream": true}
    }
  }'
```

**결과:** 동일한 conversation_id로 대화 계속 진행 ✅

### 대화 지속성 보장 메커니즘

```
┌──────────────────────────────────────────────────────────────┐
│            대화 지속성 보장 플로우                            │
└──────────────────────────────────────────────────────────────┘

Request 1 (contextId: "session-123")
    │
    ▼
┌─────────────────────────────────────┐
│ TaskStore.list(context_id="session- │
│ 123", status=completed, limit=1)    │
│ → 결과 없음 (첫 요청)               │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Task 생성                           │
│ - id: "task-abc"                    │
│ - contextId: "session-123"          │
│ - metadata: {}                      │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Dify API 호출                       │
│ - conversation_id: null             │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Dify 응답                           │
│ - conversation_id: "conv-dify-456"  │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Task 업데이트                       │
│ - metadata: {                       │
│     "dify_conversation_id":         │
│       "conv-dify-456"               │
│   }                                 │
└─────────────────────────────────────┘

─────────────────────────────────────────

Request 2 (contextId: "session-123")  # 동일!
    │
    ▼
┌─────────────────────────────────────┐
│ TaskStore.list(context_id="session- │
│ 123", status=completed, limit=1)    │
│ → task-abc 발견!                    │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ task-abc.metadata에서 추출:         │
│ - "dify_conversation_id":           │
│     "conv-dify-456"                 │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 새 Task 생성 (task-def)             │
│ - contextId: "session-123"          │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Dify API 호출                       │
│ - conversation_id: "conv-dify-456"  │ ← 재사용!
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ Dify가 이전 대화 기억! ✅           │
└─────────────────────────────────────┘
```

**핵심 코드 (services/task_manager.py:201-214):**

```python
# Dify conversation_id 재사용 로직
conversation_id = task.metadata.get("dify_conversation_id")

# 현재 Task에 없으면, 동일 contextId의 최근 완료된 Task에서 가져오기
if not conversation_id and task.contextId:
    recent_tasks = self.task_store.list(
        context_id=task.contextId,
        status=TaskStatus.completed,
        limit=1,
        offset=0
    )
    if recent_tasks and "dify_conversation_id" in recent_tasks[0].metadata:
        conversation_id = recent_tasks[0].metadata["dify_conversation_id"]
        logger.info(f"Reusing conversation_id {conversation_id} from previous Task")
```

## 📋 Task 시스템 심화

### Task 생명주기

```
┌─────────┐
│ pending │  (Task 생성 직후)
└────┬────┘
     │ TaskManager.run_task() 호출
     ▼
┌─────────┐
│ running │  (Dify API 호출 중, SSE 스트리밍 중)
└────┬────┘
     │
     ├─────────────┬──────────────┬─────────────┐
     ▼             ▼              ▼             ▼
┌───────────┐ ┌─────────┐ ┌────────────┐ ┌──────────────┐
│ completed │ │ failed  │ │ canceled   │ │ input-required│
└───────────┘ └─────────┘ └────────────┘ └──────────────┘
   (정상)      (에러)     (사용자취소)   (사용자입력필요)

상태 전환 트리거:
- pending → running: TaskManager.run_task() 시작
- running → completed: Dify 응답 완료, Artifact 생성 성공
- running → failed: Dify API 에러, 네트워크 에러
- running → canceled: tasks/cancel API 호출
- running → input-required: Dify가 사용자 입력 요청 (향후)
```

**각 상태 설명:**

| 상태 | 설명 | Task 필드 |
|------|------|-----------|
| `pending` | Task 생성됨, 아직 실행 전 | `completedAt: null`, `error: null` |
| `running` | Dify API 호출 중, SSE 스트리밍 중 | `completedAt: null`, `error: null` |
| `completed` | 정상 완료, Artifact 생성됨 | `completedAt: datetime`, `artifacts: [...]` |
| `failed` | 실행 중 에러 발생 | `error: "error message"`, `completedAt: null` |
| `canceled` | 사용자가 tasks/cancel 호출 | `completedAt: datetime`, `error: null` |
| `input-required` | 사용자 추가 입력 필요 (Phase 3 계획) | `completedAt: null` |
| `auth-required` | 인증 필요 (Phase 3 계획) | `completedAt: null` |

### Task.kind 필드

**정의:** A2A Protocol 표준의 타입 판별자

**값:** `"task"` (현재)

**목적:**
- 클라이언트가 응답 객체 타입 식별
- 향후 확장: `"agent"`, `"artifact"`, `"event"` 등

**예시:**
```json
{
  "id": "task-abc-123",
  "kind": "task",  // ← 타입 판별자
  "contextId": "session-123",
  "status": "completed",
  ...
}
```

**A2A 표준 문서:**
> The `kind` field is a type discriminator used by clients to determine how to handle the object. For Task objects, the value is always `"task"`.

### Task.metadata 구조

**목적:** Gateway 내부 정보 저장 (클라이언트에게 불투명)

**핵심 필드:**

| 필드 | 타입 | 설명 |
|------|------|------|
| `dify_conversation_id` | string | Dify 대화 ID (대화 지속성 핵심) |
| `model` | string | 사용된 LLM 모델 (예: `gpt-4`) |
| `tokens` | object | 토큰 사용량 `{"prompt": 50, "completion": 100}` |
| `execution_time_ms` | number | 실행 시간 (밀리초) |

**예시:**
```json
{
  "id": "task-abc-123",
  "contextId": "session-123",
  "status": "completed",
  "metadata": {
    "dify_conversation_id": "conv-dify-456",
    "model": "gpt-4",
    "tokens": {
      "prompt": 50,
      "completion": 100,
      "total": 150
    },
    "execution_time_ms": 1234
  },
  ...
}
```

**주의사항:**
- metadata는 **Gateway 내부 구현**
- 클라이언트는 metadata에 의존하면 안 됨 (불안정)
- A2A 표준 필드만 사용 권장 (contextId, taskId, artifacts)

### TaskStore 아키텍처

#### Phase 2 (현재): InMemory

```python
class TaskStore:
    """Thread-safe 인메모리 Task 저장소"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def save(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.id] = task
        return task

    def get(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list(
        self,
        context_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 10,
        offset: int = 0
    ) -> list[Task]:
        # 필터링 및 페이지네이션 로직
        ...
```

**특징:**
- ✅ **속도:** O(1) lookup, 매우 빠름
- ✅ **단순성:** 의존성 없음 (Redis, DB 불필요)
- ✅ **Thread-safe:** Lock 사용
- ✅ **개발 편의:** 즉시 테스트 가능
- ⚠️ **제한 1:** 서버 재시작 시 데이터 소실
- ⚠️ **제한 2:** 메모리 크기 제약 (대규모 Task 저장 불가)
- ⚠️ **제한 3:** 분산 서버 불가 (단일 인스턴스만)

#### Phase 3 (계획): Redis/PostgreSQL

```python
class RedisTaskStore(TaskStore):
    """Redis 기반 영속 Task 저장소"""

    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)

    def save(self, task: Task) -> Task:
        # Redis SET with TTL
        self.redis.setex(
            f"task:{task.id}",
            ttl=86400,  # 24시간
            value=task.model_dump_json()
        )
        return task

    def get(self, task_id: str) -> Optional[Task]:
        data = self.redis.get(f"task:{task_id}")
        return Task.model_validate_json(data) if data else None
```

**계획된 기능:**
- ✅ **영속성:** 서버 재시작 후에도 데이터 유지
- ✅ **TTL:** 오래된 Task 자동 삭제
- ✅ **검색:** 복잡한 쿼리 (status, date range 등)
- ✅ **분산:** 여러 Gateway 인스턴스 공유
- ✅ **대용량:** 수백만 Task 저장 가능

**로드맵:**
- Phase 3.1: Redis TaskStore 구현
- Phase 3.2: PostgreSQL TaskStore 구현
- Phase 3.3: TaskStore 인터페이스 추상화 (전략 패턴)

## 🎁 Artifact 시스템

### Artifact란?

**정의:** Task 실행의 구체적 결과물 (A2A 표준)

**예시:**
- 텍스트 응답 ("안녕하세요!")
- 생성된 코드 (Python 스크립트)
- 이미지 URL (`https://...`)
- 구조화된 데이터 (JSON 객체)

**A2A 표준 문서:**
> An Artifact represents a concrete output produced during task execution. It can contain text, files, or structured data.

### Artifact 생성 및 저장 과정

```
┌─────────────────────────────────────────────────────────────┐
│          Artifact 생성 플로우                                │
└─────────────────────────────────────────────────────────────┘

1. Client → Gateway: message.send
    │
    ▼
2. Gateway → Dify: POST /chat-messages (SSE)
    │
    ▼
3. Dify SSE Events:
    ├─ {"event": "message", "answer": "안녕"}      ← 텍스트 청크
    ├─ {"event": "message", "answer": "하세요"}    ← 텍스트 청크
    └─ {"event": "message_end", "metadata": {...}}
    │
    ▼
4. Gateway: SSE 이벤트 수집 및 병합
    │
    ├─ 텍스트 청크 병합: "안녕" + "하세요" = "안녕하세요"
    │
    ▼
5. Artifact 생성 (TaskManager._create_artifact_from_response)
    │
    ├─ artifactId 생성: "artifact-{uuid}"
    ├─ Parts 생성: [{"type": "text", "text": "안녕하세요"}]
    ├─ metadata 저장: {"event_type": "message", "tokens": {...}}
    │
    ▼
6. Task.artifacts에 추가
    │
    ├─ Task.artifacts.append(artifact)
    ├─ Task.status = "completed"
    ├─ Task.completedAt = datetime.now()
    │
    ▼
7. TaskArtifactUpdateEvent 발행 (SSE → Client)
    │
    └─ {"type": "task_artifact_update", "artifact": {...}}
```

**코드 예시 (services/task_manager.py):**

```python
def _create_artifact_from_response(
    self,
    task_id: str,
    response_text: str,
    metadata: dict[str, Any]
) -> Artifact:
    """Dify 응답으로부터 Artifact 생성"""
    artifact = Artifact(
        artifactId=f"artifact-{uuid.uuid4()}",
        name="Dify Response",
        description=f"Response for task {task_id}",
        parts=[
            TextPart(text=response_text)
        ],
        metadata=metadata,
        createdAt=datetime.now(timezone.utc)
    )
    return artifact
```

### Parts 구조 상세 (Multi-modal 준비)

A2A Protocol은 **Parts 기반** 메시지를 사용하여 다양한 콘텐츠 타입 지원:

#### TextPart (텍스트)

```python
class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str
```

**사용 예시:**
```json
{
  "type": "text",
  "text": "안녕하세요! Dify A2A Gateway입니다."
}
```

#### FilePart (파일)

```python
class FilePart(BaseModel):
    type: Literal["file"] = "file"
    name: str
    mimeType: Optional[str] = None
    uri: Optional[str] = None       # HTTP URL
    bytes: Optional[str] = None     # Base64 인코딩
```

**사용 예시 (URI):**
```json
{
  "type": "file",
  "name": "report.pdf",
  "mimeType": "application/pdf",
  "uri": "https://storage.example.com/reports/123.pdf"
}
```

**사용 예시 (Base64):**
```json
{
  "type": "file",
  "name": "image.png",
  "mimeType": "image/png",
  "bytes": "iVBORw0KGgoAAAANSUhEUgAAAAUA..."
}
```

#### DataPart (구조화된 데이터)

```python
class DataPart(BaseModel):
    type: Literal["data"] = "data"
    data: dict[str, Any]
```

**사용 예시:**
```json
{
  "type": "data",
  "data": {
    "temperature": 22.5,
    "humidity": 60,
    "location": "Seoul",
    "timestamp": "2024-11-07T12:00:00Z"
  }
}
```

### Artifact 사용 예제

#### 예제 1: 텍스트 응답

**Task 객체:**
```json
{
  "id": "task-abc-123",
  "contextId": "session-123",
  "status": "completed",
  "artifacts": [
    {
      "artifactId": "artifact-xyz-789",
      "name": "Dify Response",
      "parts": [
        {
          "type": "text",
          "text": "안녕하세요! 무엇을 도와드릴까요?"
        }
      ],
      "metadata": {
        "event_type": "message",
        "tokens": {"prompt": 10, "completion": 20}
      },
      "createdAt": "2024-11-07T12:00:00Z"
    }
  ]
}
```

#### 예제 2: 코드 생성 (향후)

**Artifact with Code:**
```json
{
  "artifactId": "artifact-code-456",
  "name": "Generated Python Script",
  "parts": [
    {
      "type": "text",
      "text": "다음은 요청하신 Python 스크립트입니다:"
    },
    {
      "type": "file",
      "name": "script.py",
      "mimeType": "text/x-python",
      "bytes": "ZGVmIG1haW4oKToKICAgIHByaW50KCJIZWxsbyIp"
    }
  ],
  "metadata": {
    "language": "python",
    "lines": 10
  }
}
```

#### 예제 3: 이미지 생성 (Phase 4 계획)

**Artifact with Image:**
```json
{
  "artifactId": "artifact-img-789",
  "name": "Generated Diagram",
  "parts": [
    {
      "type": "text",
      "text": "요청하신 시스템 아키텍처 다이어그램입니다:"
    },
    {
      "type": "file",
      "name": "architecture.png",
      "mimeType": "image/png",
      "uri": "https://storage.dify.ai/images/abc123.png"
    }
  ],
  "metadata": {
    "width": 1024,
    "height": 768,
    "format": "png"
  }
}
```

## 🚀 AgentCard (향후 기능) - Phase 3 계획

### 개념

**AgentCard:** A2A Gateway Instance의 메타데이터 및 설정 객체

**정의:**
- 하나의 Gateway Instance = 하나의 AgentCard
- AgentCard는 Dify Agent의 "대리인" 역할
- 클라이언트가 AgentCard를 통해 Agent 정보 조회

**A2A Protocol 문서 (예상):**
> An AgentCard describes the capabilities, configuration, and metadata of an A2A-compliant agent endpoint.

### 1:1 매핑 아키텍처

```
┌──────────────────────────────────────────────────────────┐
│            Multi-Agent 환경 구성도                       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Client A                                                │
│    │                                                     │
│    └─▶ GET /agentcard                                   │
│           [                                              │
│             {"id": "card-support", "name": "Support AI"} │
│             {"id": "card-sales", "name": "Sales AI"}     │
│           ]                                              │
│        │                                                 │
│        └─▶ 선택: "card-support"                         │
│            message.send to http://gateway1:8080/a2a     │
│                                                          │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────┐            │
│  │  Gateway Instance 1 (port 8080)         │            │
│  │  ┌─────────────────────────────────┐    │            │
│  │  │ AgentCard                       │    │            │
│  │  │ - id: "card-support"            │    │            │
│  │  │ - name: "Customer Support AI"   │    │            │
│  │  │ - description: "24/7 support"   │    │            │
│  │  │ - dify_api_key: app-agent-A     │    │            │
│  │  │ - capabilities: ["chat", "FAQ"] │    │            │
│  │  └─────────────────────────────────┘    │            │
│  │         │                                │            │
│  │         └─▶ Dify Agent A                │            │
│  └─────────────────────────────────────────┘            │
│                                                          │
│  ┌─────────────────────────────────────────┐            │
│  │  Gateway Instance 2 (port 8081)         │            │
│  │  ┌─────────────────────────────────┐    │            │
│  │  │ AgentCard                       │    │            │
│  │  │ - id: "card-sales"              │    │            │
│  │  │ - name: "Sales Assistant AI"    │    │            │
│  │  │ - description: "Product expert" │    │            │
│  │  │ - dify_api_key: app-agent-B     │    │            │
│  │  │ - capabilities: ["chat", "reco"]│    │            │
│  │  └─────────────────────────────────┘    │            │
│  │         │                                │            │
│  │         └─▶ Dify Agent B                │            │
│  └─────────────────────────────────────────┘            │
│                                                          │
│  ┌─────────────────────────────────────────┐            │
│  │  Gateway Instance 3 (port 8082)         │            │
│  │  ┌─────────────────────────────────┐    │            │
│  │  │ AgentCard                       │    │            │
│  │  │ - id: "card-analyst"            │    │            │
│  │  │ - name: "Data Analyst AI"       │    │            │
│  │  │ - description: "SQL & analytics"│    │            │
│  │  │ - dify_api_key: app-agent-C     │    │            │
│  │  │ - capabilities: ["sql", "viz"]  │    │            │
│  │  └─────────────────────────────────┘    │            │
│  │         │                                │            │
│  │         └─▶ Dify Agent C                │            │
│  └─────────────────────────────────────────┘            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 예상 API 엔드포인트 (Phase 3)

#### GET /agentcard

**설명:** 현재 Gateway의 AgentCard 조회

**요청:**
```bash
curl http://localhost:8080/agentcard
```

**응답:**
```json
{
  "id": "agentcard-support-ai",
  "name": "Customer Support AI",
  "description": "24/7 customer support with FAQ and ticket creation",
  "version": "1.0.0",
  "capabilities": [
    {
      "name": "chat",
      "description": "Real-time conversation"
    },
    {
      "name": "faq",
      "description": "Frequently asked questions"
    },
    {
      "name": "ticket",
      "description": "Create support tickets"
    }
  ],
  "metadata": {
    "language": "ko",
    "timezone": "Asia/Seoul",
    "max_tokens": 4096
  },
  "endpoints": {
    "message_send": "http://localhost:8080/a2a",
    "tasks_get": "http://localhost:8080/tasks/get",
    "tasks_list": "http://localhost:8080/tasks/list",
    "tasks_cancel": "http://localhost:8080/tasks/cancel"
  }
}
```

#### POST /agentcard/create (관리 API)

**설명:** 새 AgentCard 생성 (Multi-agent 환경)

**요청:**
```json
{
  "name": "Sales Assistant AI",
  "description": "Product recommendations and sales support",
  "dify_api_key": "app-sales-agent-xyz",
  "dify_api_url": "https://api.dify.ai",
  "capabilities": ["chat", "recommend", "quote"]
}
```

#### PUT /agentcard/{id}

**설명:** AgentCard 업데이트

#### DELETE /agentcard/{id}

**설명:** AgentCard 삭제

### 설정 구조 (agentcard.json)

```json
{
  "id": "agentcard-support-ai",
  "name": "Customer Support AI",
  "description": "24/7 customer support agent",
  "version": "1.0.0",

  "dify": {
    "api_key": "app-support-agent-abc",
    "api_url": "https://api.dify.ai",
    "agent_id": "agent-123"
  },

  "capabilities": [
    {
      "name": "chat",
      "description": "Real-time conversation",
      "enabled": true
    },
    {
      "name": "faq",
      "description": "FAQ search",
      "enabled": true,
      "config": {
        "knowledge_base": "kb-faq-001"
      }
    },
    {
      "name": "ticket",
      "description": "Create support tickets",
      "enabled": true,
      "config": {
        "jira_integration": true
      }
    }
  ],

  "metadata": {
    "language": "ko",
    "timezone": "Asia/Seoul",
    "owner": "support-team@example.com",
    "tags": ["support", "customer-service"]
  },

  "limits": {
    "max_tokens": 4096,
    "rate_limit": {
      "requests_per_minute": 60,
      "concurrent_tasks": 10
    }
  }
}
```

### Phase 3 로드맵

#### Phase 3.1: AgentCard 기본 기능
- [ ] AgentCard 데이터 모델 정의
- [ ] GET /agentcard 엔드포인트 구현
- [ ] agentcard.json 설정 파일 로드
- [ ] 환경변수 기반 AgentCard 생성

#### Phase 3.2: Multi-Agent 라우팅
- [ ] Agent 디렉토리 서비스 (여러 AgentCard 조회)
- [ ] 클라이언트가 Agent 선택 (agentId 파라미터)
- [ ] Gateway 간 라우팅 (Proxy 패턴)

#### Phase 3.3: Agent 간 협업
- [ ] Agent-to-Agent 통신 (A2A Protocol 사용)
- [ ] Delegation: Agent A가 Agent B에게 작업 위임
- [ ] Orchestration: Coordinator Agent가 여러 Agent 조율

#### Phase 3.4: Agent 권한 및 보안
- [ ] API Key 기반 인증
- [ ] Role-based Access Control (RBAC)
- [ ] Rate Limiting (Agent별, Client별)
- [ ] Audit Logging (모든 요청 기록)

**예상 완료 시기:** 2025 Q1-Q2

## 📊 Phase 2.1 주요 개선사항

### A2A 표준 준수 비교

| 항목 | Phase 2 (v0.3.0) | Phase 2.1 (v0.4.0) | A2A 표준 |
|------|------------------|-------------------|----------|
| **message.send 메시지 형식** | `{"role": "user", "content": "..."}` | `{"role": "user", "parts": [{"type": "text", "text": "..."}]}` | Parts 기반 ✅ |
| **Task.kind 필드** | 없음 ❌ | `"task"` ✅ | 필수 ✅ |
| **SSE 이벤트** | `content_delta`, `message_end` (커스텀) | `task_status_update`, `task_artifact_update` (표준) | 표준 ✅ |
| **FilePart 지원** | 미구현 | 모델 정의 완료 (Dify 연동 대기) | 준비됨 ⚠️ |
| **DataPart 지원** | 미구현 | 모델 정의 완료 | 준비됨 ⚠️ |
| **Task API** | ✅ | ✅ | ✅ |
| **contextId 지원** | ✅ | ✅ (확장 필드) | ✅ |

**표준 준수율:**
- v0.3.0: ~75%
- v0.4.0: ~95% (FilePart/DataPart은 Dify Vision API 연동 대기)

### 주요 개선 항목

#### 1. Parts 기반 Message

**Before (v0.3.0):**
```json
{
  "messages": [
    {"role": "user", "content": "안녕하세요"}
  ]
}
```

**After (v0.4.0):**
```json
{
  "messages": [
    {
      "role": "user",
      "parts": [
        {"type": "text", "text": "안녕하세요"}
      ]
    }
  ]
}
```

**이유:** Multi-modal 지원 기반 마련 (텍스트 + 이미지 + 파일 혼합)

#### 2. Task.kind 필드 추가

**Before (v0.3.0):**
```json
{
  "id": "task-abc",
  "status": "completed"
}
```

**After (v0.4.0):**
```json
{
  "id": "task-abc",
  "kind": "task",
  "status": "completed"
}
```

**이유:** A2A 표준 타입 판별자

#### 3. SSE 이벤트 표준화

**Before (v0.3.0):**
```json
{"type": "content_delta", "delta": "안녕", "taskId": "..."}
{"type": "message_end", "taskId": "..."}
```

**After (v0.4.0):**
```json
{"type": "task_status_update", "taskId": "...", "status": "completed"}
{"type": "task_artifact_update", "taskId": "...", "artifact": {...}}
```

**이유:** A2A Protocol 표준 이벤트 사용

### Migration Checklist (v0.3.0 → v0.4.0)

**클라이언트 업그레이드 단계:**

- [ ] **메시지 형식 변경**
  ```diff
  - {"role": "user", "content": "Hello"}
  + {"role": "user", "parts": [{"type": "text", "text": "Hello"}]}
  ```

- [ ] **SSE 이벤트 핸들러 수정**
  ```diff
  - if (event.type === "content_delta") { ... }
  - if (event.type === "message_end") { ... }
  + if (event.type === "task_status_update") { ... }
  + if (event.type === "task_artifact_update") { ... }
  ```

- [ ] **Task 응답 파싱 업데이트**
  ```diff
  - const task = response.result;
  + const task = response.result;
  + console.assert(task.kind === "task");
  ```

- [ ] **Artifact 구조 확인**
  ```javascript
  // Artifact.parts 배열 순회
  for (const part of artifact.parts) {
    if (part.type === "text") {
      console.log(part.text);
    }
  }
  ```

- [ ] **configuration 파라미터 변경**
  ```diff
  - "params": {"stream": true, "contextId": "..."}
  + "params": {"configuration": {"stream": true}, "contextId": "..."}
  ```

**서버 측 변경 없음:** Gateway는 하위 호환성 유지 (Phase 1 테스트 제외)

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
  "version": "0.4.0"
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
        {
          "role": "user",
          "parts": [{"type": "text", "text": "안녕하세요"}]
        }
      ],
      "contextId": "session-123",
      "configuration": {"stream": true}
    }
  }'
```

**SSE 스트리밍 응답:**
```
data: {"jsonrpc":"2.0","id":"msg-1","result":{"type":"task_status_update","taskId":"task-abc-123","status":"completed","contextId":"session-123"}}

data: {"jsonrpc":"2.0","id":"msg-1","result":{"type":"task_artifact_update","taskId":"task-abc-123","artifact":{"artifactId":"artifact-xyz","parts":[{"type":"text","text":"안녕하세요!"}]},"contextId":"session-123"}}
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
      "messages": [
        {
          "role": "user",
          "parts": [{"type": "text", "text": "제 이름은 김철수입니다"}]
        }
      ],
      "contextId": "session-123",
      "configuration": {"stream": true}
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
      "messages": [
        {
          "role": "user",
          "parts": [{"type": "text", "text": "제 이름이 뭐였죠?"}]
        }
      ],
      "contextId": "session-123",
      "configuration": {"stream": true}
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
    "kind": "task",
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
        "kind": "task",
        ...
      },
      {
        "id": "task-def-456",
        "contextId": "session-123",
        "status": "completed",
        "kind": "task",
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
    "kind": "task",
    ...
  }
}
```

## 프로젝트 구조

```
a2a-gateway/
├── main.py                      # FastAPI 애플리케이션 (v0.4.0)
├── config.py                    # 환경변수 기반 설정
├── models/
│   ├── a2a.py                  # A2A Protocol 모델 (Task, Artifact, Parts, Events)
│   └── dify.py                 # Dify API 모델
├── services/
│   ├── task_store.py           # InMemory Task 저장소 (Thread-safe)
│   ├── task_manager.py         # Task 생명주기 관리 (conversation_id 재사용)
│   ├── dify_client.py          # Dify API HTTP 클라이언트
│   └── translator.py           # A2A ↔ Dify 변환 (레거시)
├── routers/
│   ├── chat.py                 # /a2a 엔드포인트 (Task 기반, A2A 이벤트)
│   └── tasks.py                # /tasks/* 엔드포인트
├── tests/
│   ├── unit/                   # 단위 테스트 (23개)
│   │   ├── test_models.py
│   │   ├── test_task_store.py
│   │   ├── test_task_manager.py
│   │   └── test_translator.py
│   └── integration/            # 통합 테스트 (11개)
│       ├── test_task_api.py    # Task API E2E
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
# 전체 테스트 실행 (53개: 23 unit + 11 integration + 19 E2E)
pytest tests/ -v

# 단위 테스트만 실행 (23개 - Dify API 불필요)
pytest tests/unit/ -v

# Task API 통합 테스트 (11개 - Dify API 불필요, Mock 사용)
pytest tests/integration/test_task_api.py -v

# E2E 테스트 (19개 - 실제 Dify API 필요)
pytest tests/integration/test_e2e.py -v

# 커버리지 포함 테스트
pytest tests/ --cov=. --cov-report=html
```

**테스트 구성 (총 53개):**
- **Unit Tests (23)**: 모델, Task Store, Task Manager, 변환기
  - test_models.py: A2A 모델 검증
  - test_task_store.py: Task 저장소 CRUD
  - test_task_manager.py: Task 생명주기
  - test_translator.py: 프로토콜 변환 (레거시)
- **Integration Tests (11)**: Task API E2E (Dify Mock)
  - Task 기반 message.send: 3개
  - tasks/get API: 2개
  - tasks/list API: 3개
  - tasks/cancel API: 3개
- **E2E Tests (19)**: 전체 흐름 (실제 Dify API 필요)

### 코드 품질

```bash
# 코드 포맷팅
ruff format .

# Linting
ruff check .

# 자동 수정
ruff check --fix .
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

### Phase 2: Task API ✅
- Task 기반 아키텍처
- InMemory Task Store
- tasks/get, tasks/list, tasks/cancel
- Context 완벽 지속성

### Phase 2.1: A2A 표준 준수 ✅ (Current)
- Parts 기반 Message
- Task.kind 필드
- TaskStatusUpdateEvent, TaskArtifactUpdateEvent
- A2A Protocol ~95% 준수

### Phase 3: AgentCard & 확장성 (계획 - 2025 Q1-Q2)
- AgentCard 메타데이터 및 설정
- Redis/DB 기반 Task Store (영속화)
- Task 만료 정책 (TTL)
- Multi-Agent 라우팅
- Agent 간 협업 (Agent-to-Agent)
- WebSocket 지원

### Phase 4: Multi-modal (계획 - 2025 Q2-Q3)
- File upload (FilePart)
- Image/Audio 처리
- Binary data (DataPart)
- Dify Vision API 연동
- Real-time collaboration

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

### 4. Parts 형식 에러

**증상:** `message.send` 요청 시 400 에러

**원인:** v0.4.0에서 Parts 기반 메시지 필수

**해결:**
```diff
# 잘못된 형식 (v0.3.0)
- {"role": "user", "content": "Hello"}

# 올바른 형식 (v0.4.0)
+ {"role": "user", "parts": [{"type": "text", "text": "Hello"}]}
```

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

### 응답 형식 변경 (v0.2.0 → v0.3.0 → v0.4.0)

```diff
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
-   "type": "content_delta",  # v0.3.0
+   "type": "task_status_update",  # v0.4.0
-   "delta": "Hello!",
+   "status": "completed",
-   "conversation_id": "conv-123"  # v0.2.0
+   "contextId": "session-123",   # v0.3.0+
+   "taskId": "task-abc-123"      # v0.3.0+
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
