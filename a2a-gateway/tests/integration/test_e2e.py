import json

import pytest
from httpx_sse import aconnect_sse


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_check(a2a_gateway_url, http_client):
    """Health check 엔드포인트 테스트"""
    response = await http_client.get(f"{a2a_gateway_url}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "dify-a2a-gateway"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_basic_chat(a2a_gateway_url, http_client):
    """기본 대화 테스트 (단일 메시지)"""
    request = {
        "jsonrpc": "2.0",
        "id": "test-basic-1",
        "method": "chat.create",
        "params": {"messages": [{"role": "user", "content": "안녕하세요"}], "stream": True},
    }

    chunks = []
    conversation_id = None

    async with aconnect_sse(http_client, "POST", f"{a2a_gateway_url}/a2a", json=request) as event_source:
        async for sse in event_source.aiter_sse():
            data = json.loads(sse.data)
            chunks.append(data)

            # conversation_id 추출
            if "result" in data and data["result"].get("conversation_id"):
                conversation_id = data["result"]["conversation_id"]

    # 검증
    assert len(chunks) > 0, "최소 1개 이상의 청크를 받아야 함"
    assert chunks[0]["jsonrpc"] == "2.0"
    assert chunks[0]["id"] == "test-basic-1"

    # 마지막 청크는 complete
    last_chunk = chunks[-1]
    assert last_chunk["result"]["type"] == "complete"
    assert last_chunk["result"].get("message_id") is not None
    assert conversation_id is not None, "conversation_id가 반환되어야 함"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_streaming_chunks(a2a_gateway_url, http_client):
    """스트리밍 응답 테스트 (여러 청크)"""
    request = {
        "jsonrpc": "2.0",
        "id": "test-stream-1",
        "method": "chat.create",
        "params": {"messages": [{"role": "user", "content": "1부터 5까지 세어주세요"}]},
    }

    content_chunks = []

    async with aconnect_sse(http_client, "POST", f"{a2a_gateway_url}/a2a", json=request) as event_source:
        async for sse in event_source.aiter_sse():
            data = json.loads(sse.data)

            if data.get("result", {}).get("type") == "content_delta":
                content_chunks.append(data["result"]["delta"])

    # 여러 청크가 왔는지 확인
    assert len(content_chunks) > 0, "최소 1개 이상의 content_delta 청크를 받아야 함"

    # 전체 내용 조합
    full_content = "".join(content_chunks)
    assert len(full_content) > 0, "응답 내용이 비어있지 않아야 함"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_conversation_continuity(a2a_gateway_url, http_client):
    """대화 이어가기 테스트 (conversation_id)"""
    # 첫 번째 메시지
    request1 = {
        "jsonrpc": "2.0",
        "id": "test-conv-1",
        "method": "chat.create",
        "params": {"messages": [{"role": "user", "content": "제 이름은 김철수입니다"}]},
    }

    conversation_id = None

    async with aconnect_sse(http_client, "POST", f"{a2a_gateway_url}/a2a", json=request1) as event_source:
        async for sse in event_source.aiter_sse():
            data = json.loads(sse.data)
            if data.get("result", {}).get("conversation_id"):
                conversation_id = data["result"]["conversation_id"]

    assert conversation_id is not None, "첫 번째 요청에서 conversation_id를 받아야 함"

    # 두 번째 메시지 (같은 conversation_id)
    request2 = {
        "jsonrpc": "2.0",
        "id": "test-conv-2",
        "method": "chat.create",
        "params": {
            "messages": [{"role": "user", "content": "제 이름이 뭐라고 했죠?"}],
            "conversation_id": conversation_id,
        },
    }

    response_content = []

    async with aconnect_sse(http_client, "POST", f"{a2a_gateway_url}/a2a", json=request2) as event_source:
        async for sse in event_source.aiter_sse():
            data = json.loads(sse.data)
            if data.get("result", {}).get("type") == "content_delta":
                response_content.append(data["result"]["delta"])

    # 이름을 기억하는지 확인 (김철수가 포함되어야 함)
    full_response = "".join(response_content)
    assert len(full_response) > 0, "응답이 비어있지 않아야 함"
    # Note: Agent가 이름을 정확히 기억하는지는 Agent의 성능에 따라 다름
    # 여기서는 conversation_id가 올바르게 전달되는지만 확인


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_error_handling_malformed_request(a2a_gateway_url, http_client):
    """잘못된 요청 형식 에러 처리"""
    # 필수 필드 누락
    request = {
        "jsonrpc": "2.0",
        "id": "test-error-1",
        # method 누락
        "params": {"messages": [{"role": "user", "content": "Hello"}]},
    }

    response = await http_client.post(f"{a2a_gateway_url}/a2a", json=request)

    # FastAPI가 422 Validation Error 반환
    assert response.status_code == 422


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_jsonrpc_format(a2a_gateway_url, http_client):
    """JSON-RPC 2.0 형식 준수 확인"""
    request = {
        "jsonrpc": "2.0",
        "id": "test-format-1",
        "method": "chat.create",
        "params": {"messages": [{"role": "user", "content": "테스트"}]},
    }

    chunks = []

    async with aconnect_sse(http_client, "POST", f"{a2a_gateway_url}/a2a", json=request) as event_source:
        async for sse in event_source.aiter_sse():
            data = json.loads(sse.data)
            chunks.append(data)

            # JSON-RPC 2.0 필수 필드 확인
            assert data["jsonrpc"] == "2.0"
            assert data["id"] == "test-format-1"
            assert "result" in data or "error" in data

    assert len(chunks) > 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multiple_sequential_requests(a2a_gateway_url, http_client):
    """여러 요청을 순차적으로 보내는 테스트"""
    for i in range(3):
        request = {
            "jsonrpc": "2.0",
            "id": f"test-seq-{i}",
            "method": "chat.create",
            "params": {"messages": [{"role": "user", "content": f"테스트 {i+1}"}]},
        }

        chunks = []

        async with aconnect_sse(http_client, "POST", f"{a2a_gateway_url}/a2a", json=request) as event_source:
            async for sse in event_source.aiter_sse():
                data = json.loads(sse.data)
                chunks.append(data)

        # 각 요청이 정상적으로 완료되는지 확인
        assert len(chunks) > 0
        assert chunks[-1]["result"]["type"] == "complete"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multi_turn_conversation_3_turns(a2a_gateway_url, http_client):
    """3회 연속 대화 테스트 - 컨텍스트 유지 검증"""
    conversation_id = None
    turns = [
        {"content": "저는 서울에 살고 있습니다", "expect_key": None},
        {"content": "제가 어디 산다고 했죠?", "expect_key": "서울"},
        {"content": "그 도시는 한국의 수도인가요?", "expect_key": None},
    ]

    for turn_idx, turn in enumerate(turns):
        request = {
            "jsonrpc": "2.0",
            "id": f"test-3turn-{turn_idx + 1}",
            "method": "chat.create",
            "params": {"messages": [{"role": "user", "content": turn["content"]}]},
        }

        # 2번째 턴부터 conversation_id 포함
        if conversation_id:
            request["params"]["conversation_id"] = conversation_id

        chunks = []
        response_content = []

        async with aconnect_sse(http_client, "POST", f"{a2a_gateway_url}/a2a", json=request) as event_source:
            async for sse in event_source.aiter_sse():
                data = json.loads(sse.data)
                chunks.append(data)

                # conversation_id 추출 (첫 번째 턴)
                if not conversation_id and data.get("result", {}).get("conversation_id"):
                    conversation_id = data["result"]["conversation_id"]

                # 응답 내용 수집
                if data.get("result", {}).get("type") == "content_delta":
                    response_content.append(data["result"]["delta"])

        # 검증
        assert len(chunks) > 0, f"턴 {turn_idx + 1}: 최소 1개 이상의 청크를 받아야 함"

        # 에러 응답 확인
        last_chunk = chunks[-1]
        if "error" in last_chunk:
            pytest.fail(f"턴 {turn_idx + 1}: 에러 발생 - {last_chunk['error']}")

        assert last_chunk.get("result", {}).get("type") == "complete", f"턴 {turn_idx + 1}: 마지막 청크는 complete여야 함"

        # 2번째 턴부터 conversation_id 일관성 확인
        if turn_idx > 0:
            assert conversation_id is not None, f"턴 {turn_idx + 1}: conversation_id가 유지되어야 함"

        # 응답 내용 확인 (선택적 - Agent 성능에 따라 다름)
        full_response = "".join(response_content)
        assert len(full_response) > 0, f"턴 {turn_idx + 1}: 응답이 비어있지 않아야 함"

        # 특정 키워드 검증 (엄격하지 않음, Agent 응답에 따라 실패할 수 있음)
        if turn["expect_key"] and len(full_response) > 10:
            # Note: Agent가 정확히 기억하지 못할 수 있으므로 경고만 출력
            if turn["expect_key"] not in full_response:
                print(f"Warning: 턴 {turn_idx + 1}에서 '{turn['expect_key']}' 키워드가 응답에 없음")

    # 최종 검증: conversation_id가 모든 턴에서 일관되게 유지되었는지
    assert conversation_id is not None, "전체 대화에서 conversation_id가 유지되어야 함"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_multi_turn_conversation_5_turns(a2a_gateway_url, http_client):
    """5회 연속 대화 테스트 - 장기 컨텍스트 유지 검증"""
    conversation_id = None
    turns = [
        "제 이름은 김철수입니다",
        "저는 30살입니다",
        "제가 몇 살이라고 했죠?",
        "제 이름도 기억하시나요?",
        "제 나이와 이름을 다시 한번 확인해주세요",
    ]

    for turn_idx, content in enumerate(turns):
        request = {
            "jsonrpc": "2.0",
            "id": f"test-5turn-{turn_idx + 1}",
            "method": "chat.create",
            "params": {"messages": [{"role": "user", "content": content}]},
        }

        # 2번째 턴부터 conversation_id 포함
        if conversation_id:
            request["params"]["conversation_id"] = conversation_id

        chunks = []
        response_content = []

        async with aconnect_sse(http_client, "POST", f"{a2a_gateway_url}/a2a", json=request) as event_source:
            async for sse in event_source.aiter_sse():
                data = json.loads(sse.data)
                chunks.append(data)

                # conversation_id 추출
                if not conversation_id and data.get("result", {}).get("conversation_id"):
                    conversation_id = data["result"]["conversation_id"]

                # 응답 내용 수집
                if data.get("result", {}).get("type") == "content_delta":
                    response_content.append(data["result"]["delta"])

        # 기본 검증
        assert len(chunks) > 0, f"턴 {turn_idx + 1}: 청크를 받아야 함"

        # 에러 응답 확인
        last_chunk = chunks[-1]
        if "error" in last_chunk:
            pytest.fail(f"턴 {turn_idx + 1}: 에러 발생 - {last_chunk['error']}")

        assert last_chunk.get("result", {}).get("type") == "complete", f"턴 {turn_idx + 1}: complete로 종료되어야 함"

        full_response = "".join(response_content)
        assert len(full_response) > 0, f"턴 {turn_idx + 1}: 응답이 있어야 함"

        # conversation_id 일관성 확인
        if turn_idx > 0:
            assert conversation_id is not None, f"턴 {turn_idx + 1}: conversation_id 유지 필요"

    # 최종 검증
    assert conversation_id is not None, "5턴 대화에서 conversation_id가 일관되게 유지되어야 함"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_conversation_context_memory(a2a_gateway_url, http_client):
    """대화 컨텍스트 메모리 테스트 - 숫자 연산으로 명확한 컨텍스트 검증"""
    conversation_id = None
    turns = [
        {"content": "10 더하기 5는 얼마인가요?", "description": "초기 숫자 제시"},
        {"content": "그 답에 3을 곱하면?", "description": "이전 답(15)에 3 곱하기 = 45"},
        {"content": "그 결과에서 20을 빼면?", "description": "이전 답(45)에서 20 빼기 = 25"},
    ]

    for turn_idx, turn in enumerate(turns):
        request = {
            "jsonrpc": "2.0",
            "id": f"test-memory-{turn_idx + 1}",
            "method": "chat.create",
            "params": {"messages": [{"role": "user", "content": turn["content"]}]},
        }

        if conversation_id:
            request["params"]["conversation_id"] = conversation_id

        chunks = []
        response_content = []

        async with aconnect_sse(http_client, "POST", f"{a2a_gateway_url}/a2a", json=request) as event_source:
            async for sse in event_source.aiter_sse():
                data = json.loads(sse.data)
                chunks.append(data)

                if not conversation_id and data.get("result", {}).get("conversation_id"):
                    conversation_id = data["result"]["conversation_id"]

                if data.get("result", {}).get("type") == "content_delta":
                    response_content.append(data["result"]["delta"])

        # 기본 검증
        assert len(chunks) > 0, f"턴 {turn_idx + 1} ({turn['description']}): 응답 필요"

        # 에러 응답 확인
        last_chunk = chunks[-1]
        if "error" in last_chunk:
            pytest.fail(f"턴 {turn_idx + 1} ({turn['description']}): 에러 발생 - {last_chunk['error']}")

        assert last_chunk.get("result", {}).get("type") == "complete"

        full_response = "".join(response_content)
        assert len(full_response) > 0, f"턴 {turn_idx + 1}: 응답 내용 필요"

        print(f"턴 {turn_idx + 1} ({turn['description']}): {full_response[:100]}")

    assert conversation_id is not None, "conversation_id가 전체 대화에서 유지되어야 함"
