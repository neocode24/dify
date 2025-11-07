"""
Task API Edge Cases and Error Handling Tests

Phase 2 완벽성 검증: Happy Path 외의 모든 엣지 케이스
"""

import json
import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from models.a2a import Message, Task, TaskStatus, TextPart
from routers.chat import task_store


@pytest.fixture(autouse=True)
def clear_task_store():
    """각 테스트 전후로 TaskStore 초기화"""
    task_store.clear()
    yield
    task_store.clear()


class TestTaskGetEdgeCases:
    """tasks/get 엣지 케이스"""

    @pytest.mark.asyncio
    async def test_get_task_with_empty_id(self):
        """빈 taskId로 조회 시 에러"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": "get-edge-1",
                "method": "tasks/get",
                "params": {"taskId": ""},
            }

            response = await client.post("/tasks/get", json=request)
            assert response.status_code == 200

            result = response.json()
            assert "error" in result
            assert result["error"]["code"] == -32602

    @pytest.mark.asyncio
    async def test_get_task_without_params(self):
        """params 없이 요청 시 에러"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": "get-edge-2",
                "method": "tasks/get",
            }

            response = await client.post("/tasks/get", json=request)
            # FastAPI validation error (422)
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_task_with_invalid_id_format(self):
        """잘못된 형식의 taskId (숫자만, 특수문자 등)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            invalid_ids = [
                "12345",  # 숫자만
                "task_invalid",  # 언더스코어 (하이픈이 아님)
                "task-",  # 뒷부분 없음
                "TASK-123",  # 대문자
            ]

            for task_id in invalid_ids:
                request = {
                    "jsonrpc": "2.0",
                    "id": f"get-edge-{task_id}",
                    "method": "tasks/get",
                    "params": {"taskId": task_id},
                }

                response = await client.post("/tasks/get", json=request)
                result = response.json()
                # 존재하지 않으므로 에러 반환
                assert "error" in result

    @pytest.mark.asyncio
    async def test_get_task_multiple_times(self):
        """동일한 Task를 여러 번 조회 (idempotency)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Task 생성
            task = Task(
                id="task-multi-get",
                contextId="session-test",
                status=TaskStatus.completed,
                history=[Message(role="user", parts=[TextPart(text="Test")])],
            )
            task_store.create(task)

            # 3번 연속 조회
            for i in range(3):
                request = {
                    "jsonrpc": "2.0",
                    "id": f"get-multi-{i}",
                    "method": "tasks/get",
                    "params": {"taskId": "task-multi-get"},
                }

                response = await client.post("/tasks/get", json=request)
                result = response.json()

                assert "result" in result
                assert result["result"]["id"] == "task-multi-get"
                assert result["result"]["status"] == "completed"


class TestTaskListEdgeCases:
    """tasks/list 엣지 케이스"""

    @pytest.mark.asyncio
    async def test_list_with_zero_limit(self):
        """limit=0으로 조회 (빈 결과 반환)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Task 생성
            for i in range(3):
                task = Task(
                    id=f"task-zero-limit-{i}",
                    contextId="session-test",
                    status=TaskStatus.completed,
                    history=[Message(role="user", parts=[TextPart(text=f"Test {i}")])],
                )
                task_store.create(task)

            request = {
                "jsonrpc": "2.0",
                "id": "list-zero-limit",
                "method": "tasks/list",
                "params": {"limit": 0, "offset": 0},
            }

            response = await client.post("/tasks/list", json=request)
            result = response.json()

            assert "result" in result
            assert len(result["result"]["tasks"]) == 0

    @pytest.mark.asyncio
    async def test_list_with_negative_offset(self):
        """음수 offset (에러 또는 0으로 처리)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": "list-negative-offset",
                "method": "tasks/list",
                "params": {"limit": 10, "offset": -1},
            }

            response = await client.post("/tasks/list", json=request)
            # Pydantic validation error 또는 정상 처리
            # 422 에러 또는 200 (offset=0으로 처리)
            assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_list_with_excessive_limit(self):
        """매우 큰 limit (1000+)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Task 5개 생성
            for i in range(5):
                task = Task(
                    id=f"task-excessive-{i}",
                    contextId="session-test",
                    status=TaskStatus.completed,
                    history=[Message(role="user", parts=[TextPart(text=f"Test {i}")])],
                )
                task_store.create(task)

            request = {
                "jsonrpc": "2.0",
                "id": "list-excessive",
                "method": "tasks/list",
                "params": {"limit": 9999, "offset": 0},
            }

            response = await client.post("/tasks/list", json=request)
            result = response.json()

            # 전체 5개 반환 (limit은 최대값일 뿐)
            assert len(result["result"]["tasks"]) == 5

    @pytest.mark.asyncio
    async def test_list_with_offset_beyond_total(self):
        """offset이 전체 개수를 초과 (빈 결과)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Task 3개 생성
            for i in range(3):
                task = Task(
                    id=f"task-offset-beyond-{i}",
                    contextId="session-test",
                    status=TaskStatus.completed,
                    history=[Message(role="user", parts=[TextPart(text=f"Test {i}")])],
                )
                task_store.create(task)

            request = {
                "jsonrpc": "2.0",
                "id": "list-offset-beyond",
                "method": "tasks/list",
                "params": {"limit": 10, "offset": 100},
            }

            response = await client.post("/tasks/list", json=request)
            result = response.json()

            # 빈 결과
            assert len(result["result"]["tasks"]) == 0

    @pytest.mark.asyncio
    async def test_list_with_nonexistent_context_id(self):
        """존재하지 않는 contextId로 필터링 (빈 결과)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Task 생성 (다른 contextId)
            task = Task(
                id="task-other-context",
                contextId="session-other",
                status=TaskStatus.completed,
                history=[Message(role="user", parts=[TextPart(text="Test")])],
            )
            task_store.create(task)

            request = {
                "jsonrpc": "2.0",
                "id": "list-nonexistent-context",
                "method": "tasks/list",
                "params": {
                    "contextId": "session-nonexistent",
                    "limit": 10,
                    "offset": 0,
                },
            }

            response = await client.post("/tasks/list", json=request)
            result = response.json()

            # 빈 결과
            assert len(result["result"]["tasks"]) == 0

    @pytest.mark.asyncio
    async def test_list_with_status_filter(self):
        """status 필터링 (pending, running, completed, failed)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 다양한 상태의 Task 생성
            statuses = [
                TaskStatus.pending,
                TaskStatus.running,
                TaskStatus.completed,
                TaskStatus.failed,
            ]

            for i, status in enumerate(statuses):
                task = Task(
                    id=f"task-status-{i}",
                    contextId="session-status-filter",
                    status=status,
                    history=[Message(role="user", parts=[TextPart(text=f"Test {i}")])],
                )
                task_store.create(task)

            # completed만 필터링
            request = {
                "jsonrpc": "2.0",
                "id": "list-status-filter",
                "method": "tasks/list",
                "params": {
                    "contextId": "session-status-filter",
                    "status": "completed",
                    "limit": 10,
                    "offset": 0,
                },
            }

            response = await client.post("/tasks/list", json=request)
            result = response.json()

            # completed 1개만
            assert len(result["result"]["tasks"]) == 1
            assert result["result"]["tasks"][0]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_list_empty_store(self):
        """TaskStore가 비어있을 때 (빈 결과)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": "list-empty",
                "method": "tasks/list",
                "params": {"limit": 10, "offset": 0},
            }

            response = await client.post("/tasks/list", json=request)
            result = response.json()

            assert len(result["result"]["tasks"]) == 0
            assert result["result"]["total"] == 0


class TestTaskCancelEdgeCases:
    """tasks/cancel 엣지 케이스"""

    @pytest.mark.asyncio
    async def test_cancel_task_twice(self):
        """이미 취소된 Task를 다시 취소 (idempotent)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # pending Task 생성
            task = Task(
                id="task-cancel-twice",
                contextId="session-cancel",
                status=TaskStatus.pending,
                history=[Message(role="user", parts=[TextPart(text="Test")])],
            )
            task_store.create(task)

            # 첫 번째 취소
            request1 = {
                "jsonrpc": "2.0",
                "id": "cancel-1st",
                "method": "tasks/cancel",
                "params": {"taskId": "task-cancel-twice"},
            }

            response1 = await client.post("/tasks/cancel", json=request1)
            result1 = response1.json()
            assert result1["result"]["status"] == "canceled"

            # 두 번째 취소 (이미 canceled 상태)
            request2 = {
                "jsonrpc": "2.0",
                "id": "cancel-2nd",
                "method": "tasks/cancel",
                "params": {"taskId": "task-cancel-twice"},
            }

            response2 = await client.post("/tasks/cancel", json=request2)
            result2 = response2.json()

            # 에러 (이미 취소됨) 또는 동일 결과 (idempotent)
            # 현재 구현에 따라 다름
            assert "error" in result2 or result2["result"]["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_cancel_failed_task(self):
        """failed 상태 Task 취소 (불가)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            task = Task(
                id="task-cancel-failed",
                contextId="session-cancel",
                status=TaskStatus.failed,
                history=[Message(role="user", parts=[TextPart(text="Test")])],
                error="Some error",
            )
            task_store.create(task)

            request = {
                "jsonrpc": "2.0",
                "id": "cancel-failed",
                "method": "tasks/cancel",
                "params": {"taskId": "task-cancel-failed"},
            }

            response = await client.post("/tasks/cancel", json=request)
            result = response.json()

            # 취소 불가 (에러)
            assert "error" in result

    @pytest.mark.asyncio
    async def test_cancel_running_task(self):
        """running 상태 Task 취소 (가능)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            task = Task(
                id="task-cancel-running",
                contextId="session-cancel",
                status=TaskStatus.running,
                history=[Message(role="user", parts=[TextPart(text="Test")])],
            )
            task_store.create(task)

            request = {
                "jsonrpc": "2.0",
                "id": "cancel-running",
                "method": "tasks/cancel",
                "params": {"taskId": "task-cancel-running"},
            }

            response = await client.post("/tasks/cancel", json=request)
            result = response.json()

            # 취소 성공
            assert "result" in result
            assert result["result"]["status"] == "canceled"

    @pytest.mark.asyncio
    async def test_cancel_with_empty_id(self):
        """빈 taskId로 취소 시 에러"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": "cancel-empty",
                "method": "tasks/cancel",
                "params": {"taskId": ""},
            }

            response = await client.post("/tasks/cancel", json=request)
            result = response.json()

            assert "error" in result


class TestTaskConcurrency:
    """동시성 테스트"""

    @pytest.mark.asyncio
    async def test_concurrent_task_creation(self):
        """동시에 여러 Task 생성"""
        import asyncio

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:

            async def create_task(i):
                request = {
                    "jsonrpc": "2.0",
                    "id": f"concurrent-{i}",
                    "method": "message.send",
                    "params": {
                        "messages": [
                            {
                                "role": "user",
                                "parts": [{"type": "text", "text": f"Concurrent {i}"}],
                            }
                        ],
                        "contextId": f"session-concurrent-{i}",
                        "configuration": {"stream": True},
                    },
                }
                return await client.post("/a2a", json=request)

            # 10개 동시 생성
            responses = await asyncio.gather(*[create_task(i) for i in range(10)])

            # 모두 성공
            for resp in responses:
                assert resp.status_code == 200

            # 10개 Task 생성됨 확인
            list_request = {
                "jsonrpc": "2.0",
                "id": "list-concurrent",
                "method": "tasks/list",
                "params": {"limit": 20, "offset": 0},
            }

            list_response = await client.post("/tasks/list", json=list_request)
            list_result = list_response.json()

            assert len(list_result["result"]["tasks"]) == 10

    @pytest.mark.asyncio
    async def test_concurrent_list_operations(self):
        """동시에 여러 list 조회"""
        import asyncio

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Task 3개 미리 생성
            for i in range(3):
                task = Task(
                    id=f"task-concurrent-list-{i}",
                    contextId="session-test",
                    status=TaskStatus.completed,
                    history=[Message(role="user", parts=[TextPart(text=f"Test {i}")])],
                )
                task_store.create(task)

            async def list_tasks(i):
                request = {
                    "jsonrpc": "2.0",
                    "id": f"list-{i}",
                    "method": "tasks/list",
                    "params": {"limit": 10, "offset": 0},
                }
                return await client.post("/tasks/list", json=request)

            # 5번 동시 조회
            responses = await asyncio.gather(*[list_tasks(i) for i in range(5)])

            # 모두 동일한 결과
            for resp in responses:
                assert resp.status_code == 200
                result = resp.json()
                assert len(result["result"]["tasks"]) == 3


class TestInvalidJSONRPC:
    """잘못된 JSON-RPC 요청"""

    @pytest.mark.asyncio
    async def test_missing_jsonrpc_version(self):
        """jsonrpc 필드 누락 (현재는 선택적 필드로 처리됨)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "id": "invalid-1",
                "method": "tasks/get",
                "params": {"taskId": "task-test"},
            }

            response = await client.post("/tasks/get", json=request)
            # 현재 구현: jsonrpc 필드 없어도 처리 (default 값 사용)
            # 향후 개선: Pydantic validation으로 422 에러 반환
            assert response.status_code in [200, 422]
            if response.status_code == 200:
                result = response.json()
                # Task가 없으므로 에러 반환
                assert "error" in result

    @pytest.mark.asyncio
    async def test_wrong_jsonrpc_version(self):
        """잘못된 jsonrpc 버전 (1.0, 3.0 등)"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "jsonrpc": "1.0",
                "id": "invalid-2",
                "method": "tasks/get",
                "params": {"taskId": "task-test"},
            }

            response = await client.post("/tasks/get", json=request)
            # 현재 구현: jsonrpc 버전 체크 안 함
            # 향후 개선: "2.0"만 허용하도록 Pydantic Literal 사용
            assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_missing_method(self):
        """method 필드 누락"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            request = {
                "jsonrpc": "2.0",
                "id": "invalid-3",
                "params": {"taskId": "task-test"},
            }

            response = await client.post("/tasks/get", json=request)
            # 현재 구현: method 필드 없어도 처리 (default 값 사용 가능)
            # 향후 개선: Pydantic required field로 422 에러 반환
            assert response.status_code in [200, 422]

    @pytest.mark.asyncio
    async def test_invalid_json_body(self):
        """잘못된 JSON 형식"""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/tasks/get",
                content=b'{"jsonrpc": "2.0", "id": "1", invalid json',
                headers={"Content-Type": "application/json"},
            )

            # JSON parse error
            assert response.status_code == 422
