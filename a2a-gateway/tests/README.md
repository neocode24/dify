# A2A Gateway 테스트

## 테스트 구조

```
tests/
├── conftest.py              # pytest fixtures
├── run_tests.sh             # 테스트 실행 스크립트
├── unit/                    # 단위 테스트 (Mock, 빠름)
│   ├── test_translator.py   # 프로토콜 변환 로직
│   └── test_models.py       # Pydantic 모델 검증
└── integration/             # 통합 테스트 (Docker 필요)
    └── test_e2e.py          # E2E 시나리오
```

## 테스트 유형

### 1. 단위 테스트 (Unit Tests)
- **목적**: 프로토콜 변환 로직 검증
- **특징**: Mock 사용, 빠른 실행, 외부 의존성 없음
- **마커**: `@pytest.mark.unit`

### 2. 통합 테스트 (Integration Tests)
- **목적**: A2A Gateway 전체 동작 확인
- **특징**: 실제 HTTP 요청, Health check
- **마커**: `@pytest.mark.integration`
- **요구사항**: A2A Gateway 실행 중

### 3. E2E 테스트 (End-to-End Tests)
- **목적**: Dify API까지 포함한 전체 흐름 검증
- **특징**: 실제 Dify와 통신
- **마커**: `@pytest.mark.e2e`
- **요구사항**: Docker Compose 전체 스택 실행

---

## 실행 방법

### 빠른 실행 (권장)

```bash
cd a2a-gateway/tests
./run_tests.sh
```

### 단위 테스트만

```bash
cd a2a-gateway
pytest tests/unit/ -v -m unit
```

### 통합 테스트만 (Docker 필요)

```bash
# 1. Docker Compose 실행
cd docker
docker compose up -d a2a-gateway

# 2. 테스트 실행
cd ../a2a-gateway
export A2A_GATEWAY_URL=http://localhost:8080
pytest tests/integration/ -v -m integration
```

### E2E 테스트

```bash
# Docker Compose 전체 스택 실행 후
cd a2a-gateway
pytest tests/integration/ -v -m e2e
```

### 전체 테스트

```bash
pytest tests/ -v
```

---

## 테스트 시나리오

### ✅ 단위 테스트

1. **A2A → Dify 변환**
   - 단일 메시지 변환
   - conversation_id 전달
   - 여러 메시지 중 마지막 user 메시지 추출

2. **Dify → A2A 변환**
   - message 이벤트 (스트리밍 청크)
   - message_end 이벤트 (완료)
   - error 이벤트 (에러 처리)
   - agent_thought 이벤트 무시

3. **모델 검증**
   - A2A 프로토콜 모델 (유효성 검사)
   - Dify API 모델 (기본값 확인)

### ✅ 통합 테스트

1. **Health Check**: Gateway 정상 동작 확인
2. **기본 대화**: 단일 메시지 → 응답
3. **스트리밍 응답**: 여러 청크 순차 전달
4. **대화 이어가기**: conversation_id 유지
5. **에러 처리**: 잘못된 요청 형식
6. **JSON-RPC 형식**: 프로토콜 준수
7. **순차 요청**: 여러 요청 처리

---

## 환경 설정

### 환경변수

```bash
# Gateway URL (기본값: http://localhost:8080)
export A2A_GATEWAY_URL=http://localhost:8080

# Dify API Key (E2E 테스트용, 선택)
export DIFY_API_KEY=app-xxx
```

### 의존성 설치

```bash
cd a2a-gateway
uv pip install -e ".[dev]"
```

---

## CI/CD 통합

### GitHub Actions 예시

```yaml
name: Test A2A Gateway

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install uv
          cd a2a-gateway
          uv pip install -e ".[dev]"

      - name: Run unit tests
        run: |
          cd a2a-gateway
          pytest tests/unit/ -v -m unit

      - name: Start Docker services
        run: |
          cd docker
          docker compose up -d

      - name: Run integration tests
        run: |
          cd a2a-gateway
          pytest tests/integration/ -v -m integration
```

---

## 문제 해결

### 1. `A2A_GATEWAY_URL` 연결 실패

```bash
# Gateway가 실행 중인지 확인
curl http://localhost:8080/health

# Docker 로그 확인
cd docker
docker compose logs a2a-gateway
```

### 2. E2E 테스트 실패

```bash
# Dify API 실행 확인
docker compose ps api

# API Key 확인
docker compose exec a2a-gateway printenv DIFY_API_KEY
```

### 3. pytest 버전 충돌

```bash
# 가상환경 재생성
cd a2a-gateway
rm -rf .venv
uv venv
uv pip install -e ".[dev]"
```

---

## 코드 커버리지

```bash
# 커버리지 측정
pytest tests/ --cov=. --cov-report=html

# 결과 확인
open htmlcov/index.html
```

---

## 베스트 프랙티스

1. **단위 테스트 먼저**: 빠른 피드백으로 버그 조기 발견
2. **Mock 활용**: 외부 의존성 격리
3. **명확한 Assertion**: 무엇을 검증하는지 명시
4. **독립성 유지**: 각 테스트는 독립적으로 실행 가능
5. **실패 메시지**: 실패 시 원인 파악이 쉽도록 메시지 작성

---

## 추가 정보

- **pytest 문서**: https://docs.pytest.org/
- **httpx 문서**: https://www.python-httpx.org/
- **A2A Protocol**: https://a2a.anthropic.com/
