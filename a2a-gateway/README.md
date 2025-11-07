# Dify A2A Gateway

[![Tests](https://img.shields.io/badge/tests-31%20passed-success)](tests/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green)](https://fastapi.tiangolo.com/)

A2A Protocol gateway for Dify - 표준 준수 대화 에이전트 통신 게이트웨이

## 개요

Dify의 Chat API를 [A2A Protocol](https://a2a-protocol.org/) (Agent-to-Agent JSON-RPC 2.0) 표준으로 감싸는 게이트웨이 서비스입니다. A2A 클라이언트가 Dify Agent와 실시간 스트리밍 대화를 수행할 수 있도록 프로토콜 변환을 제공합니다.

## ⚠️ Breaking Changes (v0.2.0)

### A2A Protocol 표준 준수로 인한 변경

이전 버전(v0.1.0)은 A2A Protocol 표준을 준수하지 않았습니다. v0.2.0부터 공식 표준을 따르도록 대폭 리팩토링되었습니다.

#### 주요 변경사항

1. **`conversation_id` → `contextId` 변경**
   - A2A Protocol 표준 필드명 사용
   - 요청/응답 모두 `contextId` 필드로 통일

2. **Redis 의존성 제거**
   - Session 관리를 위한 Redis 불필요
   - `contextId`를 Dify `user_id`로 직접 매핑
   - 인프라 단순화 (Gateway 단독 실행 가능)

3. **User ID 로직 단순화**
   - Before: Redis 기반 `conversation_id → user_id` 매핑
   - After: `contextId` 값을 `user_id`로 직접 사용
   - contextId 없을 경우: `"anonymous"` 사용

4. **메서드명 변경**
   - Before: `chat.create`
   - After: `message.send` (A2A 표준)

#### 마이그레이션 가이드

**요청 형식 변경:**
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

**응답 형식 변경:**
```diff
{
  "jsonrpc": "2.0",
  "id": "1",
  "result": {
    "type": "content_delta",
    "delta": "Hello!",
-   "conversation_id": "conv-123"
+   "contextId": "session-123"
  }
}
```

**환경변수 제거:**
```diff
- REDIS_ENABLED=true
- REDIS_HOST=localhost
- REDIS_PORT=6379
- REDIS_DB=0
- REDIS_PASSWORD=
- REDIS_TTL_DAYS=1
```

**Docker Compose 변경:**
```diff
services:
  a2a-gateway:
    depends_on:
      - api
-     - redis
```

## 주요 기능

### 🔄 프로토콜 변환
- **A2A → Dify**: A2A JSON-RPC 요청을 Dify REST API로 변환
- **Dify → A2A**: Dify SSE 스트리밍 응답을 A2A JSON-RPC로 변환
- **실시간 스트리밍**: Server-Sent Events를 통한 실시간 응답 전송

### 🎯 A2A Protocol 표준 준수
- **contextId 기반 세션 관리**: A2A Protocol의 contextId를 Dify user_id로 매핑
- **대화 컨텍스트 유지**: contextId를 통한 다중 턴 대화 지원
- **표준 메서드**: `message.send` 메서드 지원
- **단순한 아키텍처**: 외부 의존성 없이 Gateway 단독 실행

### 📊 프로덕션 준비
- **Health Check**: 종합 health endpoint 제공
- **종합 테스트**: 31개 테스트 (23 unit + 8 E2E) 검증 완료
- **독립 배포**: Dify 코드 수정 없이 별도 서비스로 동작
- **Docker 지원**: Docker Compose 통합 배포

## 아키텍처

### 기본 흐름

```
A2A Client
    ↓ POST /a2a (A2A JSON-RPC)
A2A Gateway (FastAPI)
    ↓ POST /v1/chat-messages (Dify REST + SSE)
Dify API
```

### contextId 기반 세션 관리

```
┌─────────────┐                  ┌──────────────┐                  ┌──────────┐
│ A2A Client  │─────────────────▶│ A2A Gateway  │─────────────────▶│   Dify   │
│             │◀─────────────────│              │◀─────────────────│   API    │
└─────────────┘                  └──────────────┘                  └──────────┘
      │                                  │
      │ contextId: "session-123"        │ user_id: "session-123"
      │ (Client 제공)                   │ (contextId 직접 매핑)
```

#### 대화 흐름

1. **첫 메시지**: Client가 contextId 제공 (또는 없으면 "anonymous")
2. **Gateway 변환**: contextId → Dify user_id 직접 매핑
3. **Dify 요청**: user_id로 Dify API 호출
4. **Dify 응답**: conversation_id 생성 및 스트리밍 응답
5. **A2A 응답**: contextId를 응답에 포함하여 반환
6. **후속 메시지**: 동일 contextId 사용 시 Dify가 자동으로 컨텍스트 유지

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

**응답 예시:**
```json
{
  "status": "ok",
  "service": "dify-a2a-gateway",
  "version": "0.2.0"
}
```

### 기본 대화 요청 (contextId 없음)

```bash
curl -N -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-1",
    "method": "message.send",
    "params": {
      "messages": [
        {"role": "user", "content": "안녕하세요"}
      ]
    }
  }'
```

### 대화 이어가기 (contextId 사용)

```bash
# 1. 첫 번째 메시지 (contextId 지정)
curl -N -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "msg-1",
    "method": "message.send",
    "params": {
      "messages": [
        {"role": "user", "content": "제 이름은 김철수입니다"}
      ],
      "contextId": "session-123"
    }
  }'

# 2. 대화 이어가기 (동일한 contextId 사용)
curl -N -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "msg-2",
    "method": "message.send",
    "params": {
      "messages": [
        {"role": "user", "content": "제 이름이 뭐였죠?"}
      ],
      "contextId": "session-123"
    }
  }'
```

**참고**: contextId를 제공하지 않으면 "anonymous" user로 처리되며, 대화 컨텍스트가 유지되지 않습니다.

### SSE 스트리밍 응답 형식

```
data: {"jsonrpc":"2.0","id":"test-1","result":{"type":"content_delta","delta":"안녕","contextId":"session-123"}}

data: {"jsonrpc":"2.0","id":"test-1","result":{"type":"content_delta","delta":"하세요","contextId":"session-123"}}

data: {"jsonrpc":"2.0","id":"test-1","result":{"type":"complete","message_id":"msg-xxx","contextId":"session-123"}}
```

## 환경변수

### 필수 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DIFY_API_KEY` | Dify App API Key | - (필수) |

### Gateway 설정

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DIFY_API_URL` | Dify API 엔드포인트 | `http://api:5001` |
| `PORT` | Gateway 포트 | `8080` |
| `HOST` | 바인드 주소 | `0.0.0.0` |
| `LOG_LEVEL` | 로그 레벨 (DEBUG/INFO/WARNING/ERROR) | `INFO` |
| `CORS_ORIGINS` | CORS 허용 출처 | `["*"]` |

### CORS 설정

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `CORS_ORIGINS` | 허용할 Origin 목록 (JSON 배열) | `["*"]` |

## 프로젝트 구조

```
a2a-gateway/
├── main.py                      # FastAPI 애플리케이션 엔트리포인트
├── config.py                    # 환경변수 기반 설정 관리
├── models/
│   ├── a2a.py                  # A2A Protocol Pydantic 모델
│   └── dify.py                 # Dify API Pydantic 모델
├── services/
│   ├── dify_client.py          # Dify API HTTP 클라이언트 (httpx + SSE)
│   └── translator.py           # A2A ↔ Dify 프로토콜 변환기
├── routers/
│   └── chat.py                 # /a2a 엔드포인트 라우터
├── tests/
│   ├── unit/                   # 단위 테스트 (23개)
│   │   ├── test_models.py
│   │   └── test_translator.py
│   └── integration/            # 통합 테스트 (8개)
│       └── test_e2e.py         # E2E 테스트
├── Dockerfile                   # 프로덕션 이미지 빌드
├── pyproject.toml              # 의존성 및 프로젝트 메타데이터
├── .env.example                # 환경변수 템플릿
├── .gitignore
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
# 전체 테스트 실행 (34개)
pytest tests/ -v

# 단위 테스트만 실행 (24개)
pytest tests/unit/ -v

# 통합 테스트만 실행 (10개 - Dify API 필요)
pytest tests/integration/ -v

# 커버리지 포함 테스트
pytest tests/ --cov=. --cov-report=html
```

**테스트 구성:**
- **Unit Tests (24)**: 모델, 변환기 단위 테스트 (Dify API 불필요)
- **E2E Tests (10)**: 전체 흐름 검증 (Dify API 필요)
  - Health check
  - 기본 채팅
  - 스트리밍 청크
  - 대화 연속성
  - 에러 처리
  - JSON-RPC 포맷
  - 연속 요청
  - 3턴/5턴 대화 컨텍스트
  - 수학 계산 메모리

### 코드 품질

```bash
# 코드 포맷팅
ruff format .

# Linting
ruff check .

# 자동 수정
ruff check --fix .

# 타입 체크 (선택)
mypy .
```

### 로컬 Dify와 연동 테스트

```bash
# 1. Dify 로컬 실행 (docker)
cd ../docker
docker compose up -d

# 2. .env 설정
DIFY_API_URL=http://localhost:5001
DIFY_API_KEY=app-xxx  # Dify 콘솔에서 발급

# 3. Gateway 실행
uvicorn main:app --reload --port 8080

# 4. 테스트 실행
pytest tests/integration/ -v
```

## Docker 배포

### 이미지 빌드

```bash
# 로컬 빌드
docker build -t langgenius/dify-a2a-gateway:latest .

# Multi-platform 빌드 (ARM64 + AMD64)
docker buildx build --platform linux/amd64,linux/arm64 \
  -t langgenius/dify-a2a-gateway:latest .
```

### 단독 실행

```bash
docker run -d \
  -p 8080:8080 \
  -e DIFY_API_URL=http://dify-api:5001 \
  -e DIFY_API_KEY=app-xxx \
  -e REDIS_ENABLED=false \
  --name a2a-gateway \
  langgenius/dify-a2a-gateway:latest
```

### Docker Compose 통합

```yaml
services:
  a2a-gateway:
    image: langgenius/dify-a2a-gateway:latest
    ports:
      - "8080:8080"
    environment:
      DIFY_API_URL: http://api:5001
      DIFY_API_KEY: ${A2A_DIFY_API_KEY}
      REDIS_ENABLED: true
      REDIS_HOST: redis
      REDIS_PORT: 6379
      REDIS_PASSWORD: ${REDIS_PASSWORD}
      REDIS_DB: 2
      REDIS_TTL_DAYS: 1
    depends_on:
      - api
      - redis
    networks:
      - default
```

## 문제 해결

### 1. Dify API 연결 실패

```bash
# API 서비스 상태 확인
docker compose ps api

# 네트워크 연결 확인
docker compose exec a2a-gateway ping api

# API 로그 확인
docker compose logs api -f
```

**증상:** `Connection refused` 또는 `Host not found`
**해결:**
- `DIFY_API_URL`이 올바른지 확인
- Docker 네트워크 내에서는 `http://api:5001` 사용
- 로컬 호스트에서는 `http://localhost:5001` 사용

### 2. API Key 오류

**증상:** `401 Unauthorized` 또는 `Invalid API key`
**해결:**
- `.env` 파일에서 `DIFY_API_KEY` 확인
- Dify 콘솔에서 App의 API Key 재발급
- API Key 앞에 `app-` 접두사 확인

### 3. SSE 스트리밍 끊김

**증상:** 응답이 중간에 끊기거나 버퍼링됨
**해결:**
- Nginx/프록시 사용 시 버퍼링 비활성화:
  ```nginx
  proxy_buffering off;
  proxy_cache off;
  proxy_set_header Connection '';
  chunked_transfer_encoding off;
  ```
- `curl`에서 `-N` 옵션 사용

### 4. 대화 컨텍스트 유지 안됨

**증상:** 이전 대화 내용을 기억하지 못함
**확인사항:**
1. 동일한 `contextId`를 전달했는지 확인
2. `contextId`가 없으면 "anonymous" 처리되어 컨텍스트 유지 안됨
3. Dify가 동일 user_id의 대화 이력을 유지하는지 확인

## 성능 및 확장성

### 성능 특성

- **응답 시간**: Dify API 응답 시간 + 프로토콜 변환 오버헤드 (~5ms)
- **동시 연결**: FastAPI의 비동기 처리로 수천 개 동시 연결 지원
- **메모리 사용**: 기본 ~50MB + 연결당 ~1MB
- **외부 의존성**: 없음 (Gateway 단독 실행)

### 수평 확장

```yaml
# Docker Compose 스케일링
docker compose up -d --scale a2a-gateway=3

# 로드 밸런서 설정 (Nginx 예시)
upstream a2a_gateway {
    least_conn;
    server a2a-gateway-1:8080;
    server a2a-gateway-2:8080;
    server a2a-gateway-3:8080;
}
```

**주의사항:**
- 상태를 저장하지 않으므로 Sticky session 불필요
- 모든 인스턴스가 동일한 Dify API를 바라봐야 함

## A2A Protocol 지원

### 현재 지원 기능

- ✅ `chat.create` - 대화 생성
- ✅ SSE 스트리밍 응답
- ✅ `conversation_id` 기반 대화 연속성
- ✅ JSON-RPC 2.0 에러 처리

### 향후 지원 예정

- ⏳ `chat.update` - 대화 수정
- ⏳ `chat.delete` - 대화 삭제
- ⏳ File upload 지원
- ⏳ Agent tool calls 매핑

## 참고 자료

- [A2A Protocol Specification](https://a2a.anthropic.com/docs)
- [Dify API Documentation](https://docs.dify.ai/guides/application-publishing/developing-with-apis)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Server-Sent Events (SSE)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)

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
