# Dify A2A Gateway

A2A Protocol gateway for Dify - 대화 기능 지원

## 개요

Dify의 Chat API를 A2A Protocol로 감싸는 Gateway 서비스입니다. A2A 클라이언트가 Dify Agent와 통신할 수 있도록 프로토콜 변환을 제공합니다.

## 기능

- **A2A → Dify 변환**: A2A JSON-RPC 요청을 Dify REST API로 변환
- **Dify → A2A 변환**: Dify SSE 스트리밍 응답을 A2A JSON-RPC로 변환
- **스트리밍 지원**: Server-Sent Events를 통한 실시간 응답
- **독립 배포**: Dify 코드 수정 없이 별도 서비스로 동작

## 아키텍처

```
A2A Client
    ↓ POST /a2a (A2A JSON-RPC)
A2A Gateway (FastAPI)
    ↓ POST /v1/chat-messages (Dify REST)
Dify API
```

## 빠른 시작

### 1. 환경변수 설정

```bash
cp .env.example .env
# .env 파일에서 DIFY_API_KEY 설정
```

### 2. Docker Compose로 실행

```bash
cd ../docker
docker compose up a2a-gateway
```

### 3. 로컬 개발 실행

```bash
# 의존성 설치
uv pip install -r pyproject.toml

# 개발 서버 실행
uvicorn main:app --reload --port 8080
```

## API 사용법

### Health Check

```bash
curl http://localhost:8080/health
```

### A2A 대화 요청

```bash
curl -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "test-1",
    "method": "chat.create",
    "params": {
      "messages": [
        {"role": "user", "content": "안녕하세요"}
      ],
      "stream": true
    }
  }'
```

### 응답 형식 (SSE)

```
data: {"jsonrpc":"2.0","id":"test-1","result":{"type":"content_delta","delta":"안녕","conversation_id":"..."}}

data: {"jsonrpc":"2.0","id":"test-1","result":{"type":"content_delta","delta":"하세요","conversation_id":"..."}}

data: {"jsonrpc":"2.0","id":"test-1","result":{"type":"complete","message_id":"...","conversation_id":"..."}}
```

## 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `DIFY_API_URL` | Dify API 엔드포인트 | `http://api:5001` |
| `DIFY_API_KEY` | Dify App API Key (필수) | - |
| `PORT` | Gateway 포트 | `8080` |
| `HOST` | 바인드 주소 | `0.0.0.0` |
| `LOG_LEVEL` | 로그 레벨 | `INFO` |
| `CORS_ORIGINS` | CORS 허용 출처 | `["*"]` |

## 프로젝트 구조

```
a2a-gateway/
├── main.py                  # FastAPI 앱
├── config.py                # 설정 관리
├── models/
│   ├── a2a.py              # A2A 프로토콜 모델
│   └── dify.py             # Dify API 모델
├── services/
│   ├── dify_client.py      # Dify API 클라이언트
│   └── translator.py       # 프로토콜 변환기
├── routers/
│   └── chat.py             # Chat 라우터
├── Dockerfile
├── pyproject.toml
└── README.md
```

## 개발

### 테스트

```bash
pytest tests/
```

### 코드 포맷팅

```bash
ruff format .
ruff check .
```

## Docker 배포

### 이미지 빌드

```bash
docker build -t langgenius/dify-a2a-gateway:latest .
```

### 단독 실행

```bash
docker run -d \
  -p 8080:8080 \
  -e DIFY_API_URL=http://dify-api:5001 \
  -e DIFY_API_KEY=app-xxx \
  langgenius/dify-a2a-gateway:latest
```

## 문제 해결

### 1. Dify API 연결 실패

```bash
# api 서비스가 실행 중인지 확인
docker compose ps api

# 네트워크 연결 확인
docker compose exec a2a-gateway ping api
```

### 2. API Key 오류

- `.env` 파일에서 `A2A_DIFY_API_KEY` 확인
- Dify 콘솔에서 App의 API Key 재발급

### 3. SSE 스트리밍 끊김

- Nginx/프록시 버퍼링 설정 확인
- `proxy_buffering off` 설정 필요

## 라이센스

MIT License

## 기여

이슈 및 PR을 환영합니다!
