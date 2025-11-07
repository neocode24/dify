"""
Task Manager Unit Tests

TaskManager 비즈니스 로직 검증 (Dify Client는 Mock 처리)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from models.a2a import Task, TaskStatus, Message, TextPart
from models.dify import DifySSEEvent
from services.task_store import TaskStore
from services.task_manager import TaskManager


class TestTaskManager:
    """TaskManager 단위 테스트"""

    @pytest.fixture
    def store(self):
        """각 테스트마다 새로운 TaskStore 생성"""
        return TaskStore()

    @pytest.fixture
    def manager(self, store):
        """TaskManager 생성"""
        return TaskManager(task_store=store)

    @pytest.mark.asyncio
    async def test_create_task_with_context_id(self, manager):
        """contextId가 주어진 경우 Task 생성"""
        initial_message = Message(
            role="user",
            parts=[TextPart(text="Hello")],
        )

        task = await manager.create_task(
            context_id="session-123",
            initial_message=initial_message,
        )

        assert task.contextId == "session-123"
        assert task.status == TaskStatus.pending
        assert len(task.history) == 1
        assert task.history[0].role == "user"

    @pytest.mark.asyncio
    async def test_create_task_without_context_id(self, manager):
        """contextId가 없으면 자동 생성"""
        initial_message = Message(
            role="user",
            parts=[TextPart(text="Hello")],
        )

        task = await manager.create_task(
            context_id=None,
            initial_message=initial_message,
        )

        assert task.contextId.startswith("ctx-")
        assert task.status == TaskStatus.pending

    @pytest.mark.asyncio
    async def test_get_task(self, manager, store):
        """Task 조회 테스트"""
        task = Task(
            id="task-123",
            contextId="session-123",
            status=TaskStatus.pending,
        )
        store.create(task)

        result = manager.get_task("task-123")

        assert result is not None
        assert result.id == "task-123"

    def test_list_tasks(self, manager, store):
        """Task 목록 조회 테스트"""
        task1 = Task(id="task-1", contextId="session-1", status=TaskStatus.pending)
        task2 = Task(id="task-2", contextId="session-2", status=TaskStatus.running)
        task3 = Task(id="task-3", contextId="session-1", status=TaskStatus.completed)

        store.create(task1)
        store.create(task2)
        store.create(task3)

        # 전체 조회
        tasks = manager.list_tasks()
        assert len(tasks) == 3

        # contextId 필터
        tasks = manager.list_tasks(context_id="session-1")
        assert len(tasks) == 2

        # status 필터
        tasks = manager.list_tasks(status=TaskStatus.running)
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_cancel_task(self, manager, store):
        """Task 취소 테스트"""
        task = Task(
            id="task-123",
            contextId="session-123",
            status=TaskStatus.pending,
        )
        store.create(task)

        result = manager.cancel_task("task-123")

        assert result.status == TaskStatus.canceled
        assert result.completedAt is not None

    @pytest.mark.asyncio
    async def test_cancel_completed_task_fails(self, manager, store):
        """완료된 Task는 취소 불가"""
        task = Task(
            id="task-123",
            contextId="session-123",
            status=TaskStatus.completed,
        )
        store.create(task)

        with pytest.raises(ValueError, match="Cannot cancel task"):
            manager.cancel_task("task-123")

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task_fails(self, manager):
        """존재하지 않는 Task 취소 시 에러"""
        with pytest.raises(ValueError, match="Task not found"):
            manager.cancel_task("task-nonexistent")

    @pytest.mark.asyncio
    async def test_run_task_success(self, manager, store):
        """Task 실행 성공 시나리오 (Dify API Mock)"""
        # Task 생성
        initial_message = Message(
            role="user",
            parts=[TextPart(text="Hello Dify")],
        )
        task = await manager.create_task(
            context_id="session-123",
            initial_message=initial_message,
        )

        # Dify Client Mock
        mock_events = [
            DifySSEEvent(
                event="message",
                conversation_id="conv-dify-456",
                message_id="msg-1",
                answer="Hello ",
            ),
            DifySSEEvent(
                event="message",
                conversation_id="conv-dify-456",
                message_id="msg-1",
                answer="back!",
            ),
            DifySSEEvent(
                event="message_end",
                conversation_id="conv-dify-456",
                message_id="msg-1",
            ),
        ]

        # Async generator for mocking
        async def async_gen():
            for event in mock_events:
                yield event

        with patch("services.task_manager.DifyClient") as MockClient:
            # Mock stream_chat
            mock_instance = MagicMock()
            mock_instance.stream_chat = MagicMock(return_value=async_gen())
            mock_instance.close = AsyncMock()
            MockClient.return_value = mock_instance

            # Task 실행
            result = await manager.run_task(task.id)

            # 검증
            assert result.status == TaskStatus.completed
            assert len(result.history) == 2  # user + agent
            assert result.history[1].role == "agent"
            assert result.history[1].parts[0].text == "Hello back!"
            assert len(result.artifacts) == 1
            assert result.artifacts[0].parts[0].text == "Hello back!"
            assert result.metadata["dify_conversation_id"] == "conv-dify-456"
            assert result.completedAt is not None

    @pytest.mark.asyncio
    async def test_run_task_with_existing_conversation(self, manager, store):
        """기존 conversation_id가 있을 때 재사용"""
        # Task 생성 (기존 conversation_id 포함)
        initial_message = Message(
            role="user",
            parts=[TextPart(text="What is my name?")],
        )
        task = Task(
            id="task-123",
            contextId="session-123",
            status=TaskStatus.pending,
            history=[initial_message],
            metadata={"dify_conversation_id": "conv-existing-789"},
        )
        store.create(task)

        # Dify Client Mock
        mock_events = [
            DifySSEEvent(
                event="message",
                conversation_id="conv-existing-789",
                message_id="msg-2",
                answer="Your name is John",
            ),
        ]

        # Async generator for mocking
        async def async_gen():
            for event in mock_events:
                yield event

        with patch("services.task_manager.DifyClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.stream_chat = MagicMock(return_value=async_gen())
            mock_instance.close = AsyncMock()
            MockClient.return_value = mock_instance

            # Task 실행
            result = await manager.run_task(task.id)

            # Dify API 호출 시 conversation_id 전달 확인
            call_args = mock_instance.stream_chat.call_args[0][0]
            assert call_args.conversation_id == "conv-existing-789"
            assert result.metadata["dify_conversation_id"] == "conv-existing-789"

    @pytest.mark.asyncio
    async def test_run_task_failure(self, manager, store):
        """Task 실행 실패 시나리오"""
        initial_message = Message(
            role="user",
            parts=[TextPart(text="Hello")],
        )
        task = await manager.create_task(
            context_id="session-123",
            initial_message=initial_message,
        )

        # Async generator that raises exception
        async def failing_gen():
            raise Exception("API Error")
            yield  # unreachable but needed for generator syntax

        # Dify Client Mock (에러 발생)
        with patch("services.task_manager.DifyClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.stream_chat = MagicMock(return_value=failing_gen())
            mock_instance.close = AsyncMock()
            MockClient.return_value = mock_instance

            # Task 실행
            result = await manager.run_task(task.id)

            # 검증
            assert result.status == TaskStatus.failed
            assert result.error == "API Error"
            assert result.completedAt is not None

    @pytest.mark.asyncio
    async def test_run_nonexistent_task_fails(self, manager):
        """존재하지 않는 Task 실행 시 에러"""
        with pytest.raises(ValueError, match="Task not found"):
            await manager.run_task("task-nonexistent")

    def test_convert_to_dify_request(self, manager, store):
        """Task → DifyChatRequest 변환 로직 테스트"""
        task = Task(
            id="task-123",
            contextId="session-123",
            status=TaskStatus.pending,
            history=[
                Message(role="user", parts=[TextPart(text="Hello")]),
                Message(role="agent", parts=[TextPart(text="Hi there!")]),
                Message(role="user", parts=[TextPart(text="How are you?")]),
            ],
            metadata={},
        )

        dify_request = manager._convert_to_dify_request(task)

        # 마지막 사용자 메시지가 query로 설정
        assert dify_request.query == "How are you?"
        assert dify_request.user == "session-123"
        assert dify_request.conversation_id is None

    def test_convert_to_dify_request_with_conversation_id(self, manager, store):
        """conversation_id 재사용 검증"""
        task = Task(
            id="task-123",
            contextId="session-123",
            status=TaskStatus.pending,
            history=[
                Message(role="user", parts=[TextPart(text="Continue")]),
            ],
            metadata={"dify_conversation_id": "conv-456"},
        )

        dify_request = manager._convert_to_dify_request(task)

        assert dify_request.conversation_id == "conv-456"
