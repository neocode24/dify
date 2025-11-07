"""
Task Store - InMemory 기반 Task 저장소

Phase 2: InMemory 구현 (서버 재시작 시 데이터 소실)
Phase 3: Redis/DB 영속화 예정
"""

import threading
from datetime import datetime, timezone
from typing import Optional

from models.a2a import Task, TaskStatus


class TaskStore:
    """InMemory Task 저장소 (Thread-safe)"""

    def __init__(self):
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def create(self, task: Task) -> Task:
        """Task 생성"""
        with self._lock:
            if task.id in self._tasks:
                raise ValueError(f"Task already exists: {task.id}")
            self._tasks[task.id] = task
            return task

    def get(self, task_id: str) -> Optional[Task]:
        """Task 조회"""
        with self._lock:
            return self._tasks.get(task_id)

    def update(self, task: Task) -> Task:
        """Task 업데이트"""
        with self._lock:
            if task.id not in self._tasks:
                raise ValueError(f"Task not found: {task.id}")
            task.updatedAt = datetime.now(timezone.utc)
            self._tasks[task.id] = task
            return task

    def delete(self, task_id: str) -> bool:
        """Task 삭제"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                return True
            return False

    def list(
        self,
        context_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Task]:
        """Task 목록 조회 (필터링 + 페이징)"""
        with self._lock:
            tasks = list(self._tasks.values())

            # 필터링
            if context_id:
                tasks = [t for t in tasks if t.contextId == context_id]
            if status:
                tasks = [t for t in tasks if t.status == status]

            # 정렬 (최신순)
            tasks.sort(key=lambda t: t.createdAt, reverse=True)

            # 페이징
            return tasks[offset : offset + limit]

    def count(
        self,
        context_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
    ) -> int:
        """Task 개수 조회"""
        with self._lock:
            tasks = list(self._tasks.values())

            if context_id:
                tasks = [t for t in tasks if t.contextId == context_id]
            if status:
                tasks = [t for t in tasks if t.status == status]

            return len(tasks)

    def clear(self) -> None:
        """모든 Task 삭제 (테스트용)"""
        with self._lock:
            self._tasks.clear()
