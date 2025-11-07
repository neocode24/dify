"""
Task Store Unit Tests

TaskStore CRUD 동작 검증
"""

import pytest
from datetime import datetime

from models.a2a import Task, TaskStatus, Message, TextPart
from services.task_store import TaskStore


class TestTaskStore:
    """TaskStore 단위 테스트"""

    @pytest.fixture
    def store(self):
        """각 테스트마다 새로운 TaskStore 생성"""
        return TaskStore()

    @pytest.fixture
    def sample_task(self):
        """샘플 Task 생성"""
        return Task(
            id="task-123",
            contextId="session-456",
            status=TaskStatus.pending,
            history=[
                Message(
                    role="user",
                    parts=[TextPart(text="Hello")],
                )
            ],
            metadata={"dify_conversation_id": "conv-789"},
        )

    def test_create_task(self, store, sample_task):
        """Task 생성 테스트"""
        result = store.create(sample_task)

        assert result.id == "task-123"
        assert result.contextId == "session-456"
        assert result.status == TaskStatus.pending
        assert len(result.history) == 1
        assert result.metadata["dify_conversation_id"] == "conv-789"

    def test_create_duplicate_task_fails(self, store, sample_task):
        """중복 Task 생성 시 에러"""
        store.create(sample_task)

        with pytest.raises(ValueError, match="Task already exists"):
            store.create(sample_task)

    def test_get_existing_task(self, store, sample_task):
        """존재하는 Task 조회"""
        store.create(sample_task)

        result = store.get("task-123")
        assert result is not None
        assert result.id == "task-123"

    def test_get_nonexistent_task(self, store):
        """존재하지 않는 Task 조회 시 None"""
        result = store.get("task-nonexistent")
        assert result is None

    def test_update_task(self, store, sample_task):
        """Task 업데이트 테스트"""
        store.create(sample_task)

        # 상태 변경
        sample_task.status = TaskStatus.running
        result = store.update(sample_task)

        assert result.status == TaskStatus.running
        assert result.updatedAt >= sample_task.createdAt  # updatedAt 자동 갱신

    def test_update_nonexistent_task_fails(self, store, sample_task):
        """존재하지 않는 Task 업데이트 시 에러"""
        with pytest.raises(ValueError, match="Task not found"):
            store.update(sample_task)

    def test_delete_task(self, store, sample_task):
        """Task 삭제 테스트"""
        store.create(sample_task)

        deleted = store.delete("task-123")
        assert deleted is True

        # 삭제 후 조회 시 None
        assert store.get("task-123") is None

    def test_delete_nonexistent_task(self, store):
        """존재하지 않는 Task 삭제 시 False"""
        deleted = store.delete("task-nonexistent")
        assert deleted is False

    def test_list_tasks_all(self, store):
        """전체 Task 목록 조회"""
        task1 = Task(id="task-1", contextId="session-1", status=TaskStatus.pending)
        task2 = Task(id="task-2", contextId="session-2", status=TaskStatus.running)
        task3 = Task(id="task-3", contextId="session-1", status=TaskStatus.completed)

        store.create(task1)
        store.create(task2)
        store.create(task3)

        tasks = store.list()
        assert len(tasks) == 3

    def test_list_tasks_by_context_id(self, store):
        """contextId 필터링"""
        task1 = Task(id="task-1", contextId="session-1", status=TaskStatus.pending)
        task2 = Task(id="task-2", contextId="session-2", status=TaskStatus.running)
        task3 = Task(id="task-3", contextId="session-1", status=TaskStatus.completed)

        store.create(task1)
        store.create(task2)
        store.create(task3)

        tasks = store.list(context_id="session-1")
        assert len(tasks) == 2
        assert all(t.contextId == "session-1" for t in tasks)

    def test_list_tasks_by_status(self, store):
        """status 필터링"""
        task1 = Task(id="task-1", contextId="session-1", status=TaskStatus.pending)
        task2 = Task(id="task-2", contextId="session-2", status=TaskStatus.running)
        task3 = Task(id="task-3", contextId="session-1", status=TaskStatus.completed)

        store.create(task1)
        store.create(task2)
        store.create(task3)

        tasks = store.list(status=TaskStatus.running)
        assert len(tasks) == 1
        assert tasks[0].status == TaskStatus.running

    def test_list_tasks_pagination(self, store):
        """페이징 테스트"""
        for i in range(15):
            task = Task(id=f"task-{i}", contextId="session-1", status=TaskStatus.pending)
            store.create(task)

        # 첫 페이지 (0-9)
        page1 = store.list(limit=10, offset=0)
        assert len(page1) == 10

        # 두 번째 페이지 (10-14)
        page2 = store.list(limit=10, offset=10)
        assert len(page2) == 5

    def test_count_tasks(self, store):
        """Task 개수 조회"""
        task1 = Task(id="task-1", contextId="session-1", status=TaskStatus.pending)
        task2 = Task(id="task-2", contextId="session-2", status=TaskStatus.running)
        task3 = Task(id="task-3", contextId="session-1", status=TaskStatus.completed)

        store.create(task1)
        store.create(task2)
        store.create(task3)

        # 전체 개수
        assert store.count() == 3

        # contextId 필터
        assert store.count(context_id="session-1") == 2

        # status 필터
        assert store.count(status=TaskStatus.running) == 1

    def test_clear_tasks(self, store):
        """모든 Task 삭제"""
        task1 = Task(id="task-1", contextId="session-1", status=TaskStatus.pending)
        task2 = Task(id="task-2", contextId="session-2", status=TaskStatus.running)

        store.create(task1)
        store.create(task2)

        store.clear()

        assert store.count() == 0
        assert store.get("task-1") is None
        assert store.get("task-2") is None
