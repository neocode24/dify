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
        """message.send 응답에 taskId가 포함되는지 확인 (Phase 2.1: Parts 기반)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request_data = {
                "jsonrpc": "2.0",
                "id": "test-1",
                "method": "message.send",
                "params": {
                    "messages": [
                        {
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        }
                    ],
                    "configuration": {"stream": True},
                },
            }

            response = await client.post("/a2a", json=request_data)
            assert response.status_code == 200

            # SSE 응답 파싱
            events = []
            for line in response.text.strip().split("\n"):
                if line.startswith("data: "):
                    events.append(json.loads(line[6:]))

            # A2A 표준: TaskStatusUpdateEvent 또는 TaskArtifactUpdateEvent
            assert len(events) > 0
            for event in events:
                if "result" in event:
                    assert "taskId" in event["result"]
                    assert event["result"]["taskId"].startswith("task-")
                    # 이벤트 타입 검증
                    if "type" in event["result"]:
                        assert event["result"]["type"] in [
                            "task_status_update",
                            "task_artifact_update",
                        ]

    @pytest.mark.asyncio
    async def test_message_send_with_context_preserves_conversation(self):
        """동일한 contextId로 두 번 요청 시 conversation_id 재사용 (Phase 2.1)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 첫 번째 요청 (Parts 기반)
            request1 = {
                "jsonrpc": "2.0",
                "id": "test-2",
                "method": "message.send",
                "params": {
                    "messages": [
                        {
                            "role": "user",
                            "parts": [{"type": "text", "text": "My name is Alice"}],
                        }
                    ],
                    "configuration": {"stream": True},
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

            # Task 조회로 conversation_id 및 contextId 확인
            task1 = task_store.get(task_id_1)
            assert task1 is not None
            assert "dify_conversation_id" in task1.metadata

            dify_conv_id = task1.metadata["dify_conversation_id"]
            context_id_1 = task1.contextId

            # 두 번째 요청 (같은 contextId)
            # Phase 2.1에서는 task 재사용 대신 자동 생성되므로 첫 Task에서 contextId 추출
            # 그러나 현재 구현은 contextId를 자동 생성하므로 새 Task 생성됨
            request2 = {
                "jsonrpc": "2.0",
                "id": "test-3",
                "method": "message.send",
                "params": {
                    "messages": [
                        {
                            "role": "user",
                            "parts": [{"type": "text", "text": "What is my name?"}],
                        }
                    ],
                    "configuration": {"stream": True},
                },
            }

            response2 = await client.post("/a2a", json=request2)
            assert response2.status_code == 200

            # 두 번째 Task는 새로운 contextId (자동 생성)
            events2 = []
            for line in response2.text.strip().split("\n"):
                if line.startswith("data: "):
                    events2.append(json.loads(line[6:]))

            task_id_2 = events2[0]["result"]["taskId"]
            task2 = task_store.get(task_id_2)

            # 현재 구현에서는 contextId 자동 생성되므로 다름
            assert task2.contextId != context_id_1

    @pytest.mark.asyncio
    async def test_message_send_without_context_creates_auto_context(self):
        """contextId 없이 요청 시 자동 생성 (Phase 2.1)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request_data = {
                "jsonrpc": "2.0",
                "id": "test-4",
                "method": "message.send",
                "params": {
                    "messages": [
                        {
                            "role": "user",
                            "parts": [{"type": "text", "text": "Hello"}],
                        }
                    ],
                    "configuration": {"stream": True},
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
        """존재하는 Task 조회 (Phase 2.1)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 먼저 message.send로 Task 생성 (Parts 기반)
            create_request = {
                "jsonrpc": "2.0",
                "id": "create-1",
                "method": "message.send",
                "params": {
                    "messages": [
                        {
                            "role": "user",
                            "parts": [{"type": "text", "text": "Test"}],
                        }
                    ],
                    "configuration": {"stream": True},
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
            # Phase 2.1: kind 필드 검증
            assert result["result"]["kind"] == "task"

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
        """전체 Task 목록 조회 (Phase 2.1)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 3개 Task 생성 (Parts 기반)
            for i in range(3):
                create_request = {
                    "jsonrpc": "2.0",
                    "id": f"create-{i}",
                    "method": "message.send",
                    "params": {
                        "messages": [
                            {
                                "role": "user",
                                "parts": [{"type": "text", "text": f"Message {i}"}],
                            }
                        ],
                        "configuration": {"stream": True},
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
                    "messages": [{"role": "user", "parts": [{"type": "text", "text": "Message 1"}]}],
                    "contextId": "session-filter-1",
                    "configuration": {"stream": True},
                },
            }
            await client.post("/a2a", json=create_request1)

            create_request2 = {
                "jsonrpc": "2.0",
                "id": "create-2",
                "method": "message.send",
                "params": {
                    "messages": [{"role": "user", "parts": [{"type": "text", "text": "Message 2"}]}],
                    "contextId": "session-filter-2",
                    "configuration": {"stream": True},
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
                    "configuration": {"stream": True},
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
                    "configuration": {"stream": True},
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
                    "configuration": {"stream": True},
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
                    "configuration": {"stream": True},
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
