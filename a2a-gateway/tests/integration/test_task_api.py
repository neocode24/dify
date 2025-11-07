"""
Task API Integration Tests

Phase 2: Task-based message.send + Task API (tasks/get, tasks/list, tasks/cancel)
"""

import json
import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from routers.chat import task_store


@pytest.fixture(autouse=True)
def clear_task_store():
    """각 테스트 전후로 TaskStore 초기화"""
    task_store.clear()
    yield
    task_store.clear()


class TestTaskBasedMessageSend:
    """message.send가 Task 기반으로 동작하는지 검증"""

    @pytest.mark.asyncio
    async def test_message_send_returns_task_id(self):
        """message.send 응답에 taskId가 포함되는지 확인 (Breaking Change)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request_data = {
                "jsonrpc": "2.0",
                "id": "test-1",
                "method": "message.send",
                "params": {
                    "messages": [{"role": "user", "content": "Hello"}],
                    "contextId": "session-test-1",
                },
            }

            response = await client.post("/a2a", json=request_data)
            assert response.status_code == 200

            # SSE 응답 파싱
            events = []
            for line in response.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            # taskId가 응답에 포함되어야 함
            assert len(events) > 0
            for event in events:
                if "result" in event:
                    assert "taskId" in event["result"]
                    assert event["result"]["taskId"].startswith("task-")

    @pytest.mark.asyncio
    async def test_message_send_with_context_preserves_conversation(self):
        """동일한 contextId로 두 번 요청 시 conversation_id 재사용"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 첫 번째 요청
            request1 = {
                "jsonrpc": "2.0",
                "id": "test-2",
                "method": "message.send",
                "params": {
                    "messages": [{"role": "user", "content": "My name is Alice"}],
                    "contextId": "session-conversation-test",
                },
            }

            response1 = await client.post("/a2a", json=request1)
            assert response1.status_code == 200

            # taskId 추출
            events1 = []
            for line in response1.text.strip().split("\n"):
                if line.startswith("data: "):
                    events1.append(json.loads(line[6:]))

            task_id_1 = events1[0]["result"]["taskId"]

            # Task 조회로 conversation_id 확인
            tasks = task_store.list(context_id="session-conversation-test")
            assert len(tasks) == 1
            assert "dify_conversation_id" in tasks[0].metadata

            dify_conv_id = tasks[0].metadata["dify_conversation_id"]

            # 두 번째 요청 (같은 contextId)
            request2 = {
                "jsonrpc": "2.0",
                "id": "test-3",
                "method": "message.send",
                "params": {
                    "messages": [{"role": "user", "content": "What is my name?"}],
                    "contextId": "session-conversation-test",
                },
            }

            response2 = await client.post("/a2a", json=request2)
            assert response2.status_code == 200

            # 두 번째 Task도 같은 conversation_id 사용
            tasks2 = task_store.list(context_id="session-conversation-test")
            assert len(tasks2) == 2

            # 두 번째 Task가 첫 번째 conversation_id를 재사용하지 않음 (각각 새 Task)
            # 하지만 contextId는 동일
            assert tasks2[0].contextId == tasks2[1].contextId

    @pytest.mark.asyncio
    async def test_message_send_without_context_creates_auto_context(self):
        """contextId 없이 요청 시 자동 생성"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request_data = {
                "jsonrpc": "2.0",
                "id": "test-4",
                "method": "message.send",
                "params": {
                    "messages": [{"role": "user", "content": "Hello"}],
                },
            }

            response = await client.post("/a2a", json=request_data)
            assert response.status_code == 200

            # SSE 응답 파싱
            events = []
            for line in response.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            # contextId가 자동 생성되어야 함
            assert len(events) > 0
            for event in events:
                if "result" in event:
                    assert "contextId" in event["result"]
                    assert event["result"]["contextId"].startswith("ctx-")


class TestTaskGetAPI:
    """tasks/get API 테스트"""

    @pytest.mark.asyncio
    async def test_get_existing_task(self):
        """존재하는 Task 조회"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 먼저 message.send로 Task 생성
            create_request = {
                "jsonrpc": "2.0",
                "id": "create-1",
                "method": "message.send",
                "params": {
                    "messages": [{"role": "user", "content": "Test"}],
                    "contextId": "session-get-test",
                },
            }
            create_response = await client.post("/a2a", json=create_request)
            assert create_response.status_code == 200

            # taskId 추출
            events = []
            for line in create_response.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            task_id = events[0]["result"]["taskId"]

            # tasks/get 호출
            get_request = {
                "jsonrpc": "2.0",
                "id": "get-1",
                "method": "tasks/get",
                "params": {"taskId": task_id},
            }

            get_response = await client.post("/tasks/get", json=get_request)
            assert get_response.status_code == 200

            result = get_response.json()
            assert result["jsonrpc"] == "2.0"
            assert "result" in result
            assert result["result"]["id"] == task_id
            assert result["result"]["contextId"] == "session-get-test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self):
        """존재하지 않는 Task 조회 시 에러"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": "get-2",
                "method": "tasks/get",
                "params": {"taskId": "task-nonexistent"},
            }

            response = await client.post("/tasks/get", json=request)
            assert response.status_code == 200

            result = response.json()
            assert "error" in result
            assert result["error"]["code"] == -32602


class TestTaskListAPI:
    """tasks/list API 테스트"""

    @pytest.mark.asyncio
    async def test_list_all_tasks(self):
        """전체 Task 목록 조회"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 3개 Task 생성
            for i in range(3):
                create_request = {
                    "jsonrpc": "2.0",
                    "id": f"create-{i}",
                    "method": "message.send",
                    "params": {
                        "messages": [{"role": "user", "content": f"Message {i}"}],
                        "contextId": f"session-{i}",
                    },
                }
                await client.post("/a2a", json=create_request)

            # tasks/list 호출
            list_request = {
                "jsonrpc": "2.0",
                "id": "list-1",
                "method": "tasks/list",
                "params": {"limit": 10, "offset": 0},
            }

            response = await client.post("/tasks/list", json=list_request)
            assert response.status_code == 200

            result = response.json()
            assert "result" in result
            assert "tasks" in result["result"]
            assert len(result["result"]["tasks"]) == 3

    @pytest.mark.asyncio
    async def test_list_tasks_by_context_id(self):
        """contextId 필터링"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 다른 contextId로 Task 생성
            create_request1 = {
                "jsonrpc": "2.0",
                "id": "create-1",
                "method": "message.send",
                "params": {
                    "messages": [{"role": "user", "content": "Message 1"}],
                    "contextId": "session-filter-1",
                },
            }
            await client.post("/a2a", json=create_request1)

            create_request2 = {
                "jsonrpc": "2.0",
                "id": "create-2",
                "method": "message.send",
                "params": {
                    "messages": [{"role": "user", "content": "Message 2"}],
                    "contextId": "session-filter-2",
                },
            }
            await client.post("/a2a", json=create_request2)

            # tasks/list with contextId filter
            list_request = {
                "jsonrpc": "2.0",
                "id": "list-2",
                "method": "tasks/list",
                "params": {
                    "contextId": "session-filter-1",
                    "limit": 10,
                    "offset": 0,
                },
            }

            response = await client.post("/tasks/list", json=list_request)
            assert response.status_code == 200

            result = response.json()
            assert len(result["result"]["tasks"]) == 1
            assert result["result"]["tasks"][0]["contextId"] == "session-filter-1"

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self):
        """페이징 테스트"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 5개 Task 생성
            for i in range(5):
                create_request = {
                    "jsonrpc": "2.0",
                    "id": f"create-{i}",
                    "method": "message.send",
                    "params": {
                        "messages": [{"role": "user", "content": f"Message {i}"}],
                        "contextId": "session-pagination",
                    },
                }
                await client.post("/a2a", json=create_request)

            # 첫 페이지 (limit=2)
            list_request1 = {
                "jsonrpc": "2.0",
                "id": "list-page-1",
                "method": "tasks/list",
                "params": {
                    "contextId": "session-pagination",
                    "limit": 2,
                    "offset": 0,
                },
            }

            response1 = await client.post("/tasks/list", json=list_request1)
            result1 = response1.json()
            assert len(result1["result"]["tasks"]) == 2

            # 두 번째 페이지 (offset=2)
            list_request2 = {
                "jsonrpc": "2.0",
                "id": "list-page-2",
                "method": "tasks/list",
                "params": {
                    "contextId": "session-pagination",
                    "limit": 2,
                    "offset": 2,
                },
            }

            response2 = await client.post("/tasks/list", json=list_request2)
            result2 = response2.json()
            assert len(result2["result"]["tasks"]) == 2


class TestTaskCancelAPI:
    """tasks/cancel API 테스트"""

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self):
        """pending 상태 Task 취소"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Task 생성 (하지만 실행하지 않음 - pending 상태로 만들기 위해)
            from models.a2a import Task, TaskStatus, Message, TextPart

            task = Task(
                id="task-cancel-test-1",
                contextId="session-cancel",
                status=TaskStatus.pending,
                history=[Message(role="user", parts=[TextPart(text="Test")])],
            )
            task_store.create(task)

            # tasks/cancel 호출
            cancel_request = {
                "jsonrpc": "2.0",
                "id": "cancel-1",
                "method": "tasks/cancel",
                "params": {"taskId": "task-cancel-test-1"},
            }

            response = await client.post("/tasks/cancel", json=cancel_request)
            assert response.status_code == 200

            result = response.json()
            assert "result" in result
            assert result["result"]["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_cancel_completed_task_fails(self):
        """completed 상태 Task는 취소 불가"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # completed Task 생성
            from models.a2a import Task, TaskStatus, Message, TextPart

            task = Task(
                id="task-cancel-test-2",
                contextId="session-cancel",
                status=TaskStatus.completed,
                history=[Message(role="user", parts=[TextPart(text="Test")])],
            )
            task_store.create(task)

            # tasks/cancel 호출 (실패해야 함)
            cancel_request = {
                "jsonrpc": "2.0",
                "id": "cancel-2",
                "method": "tasks/cancel",
                "params": {"taskId": "task-cancel-test-2"},
            }

            response = await client.post("/tasks/cancel", json=cancel_request)
            assert response.status_code == 200

            result = response.json()
            assert "error" in result
            assert result["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self):
        """존재하지 않는 Task 취소 시 에러"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cancel_request = {
                "jsonrpc": "2.0",
                "id": "cancel-3",
                "method": "tasks/cancel",
                "params": {"taskId": "task-nonexistent"},
            }

            response = await client.post("/tasks/cancel", json=cancel_request)
            assert response.status_code == 200

            result = response.json()
            assert "error" in result
            assert result["error"]["code"] == -32602
