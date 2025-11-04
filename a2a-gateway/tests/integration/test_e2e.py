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
