"""
Task Manager - Task 생명주기 관리

Task 생성, 실행, 조회, 취소 등 비즈니스 로직 담당
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from models.a2a import (
    Task,
    TaskStatus,
    Message,
    Artifact,
    TextPart,
)
from models.dify import DifyChatRequest, DifySSEEvent
from services.task_store import TaskStore
from services.dify_client import DifyClient
from config import settings


class TaskManager:
    """Task 생명주기 관리자"""

    def __init__(self, task_store: TaskStore):
        self.task_store = task_store

    async def create_task(
        self,
        context_id: Optional[str],
        initial_message: Message,
    ) -> Task:
        """
        새로운 Task 생성

        Args:
            context_id: 세션 식별자 (없으면 자동 생성)
            initial_message: 초기 사용자 메시지

        Returns:
            생성된 Task 객체
        """
        # contextId 생성 또는 사용
        if not context_id:
            context_id = f"ctx-{uuid.uuid4()}"

        # Task 생성
        task = Task(
            id=f"task-{uuid.uuid4()}",
            contextId=context_id,
            status=TaskStatus.pending,
            history=[initial_message],
            metadata={},
        )

        # 저장
        return self.task_store.create(task)

    async def run_task(self, task_id: str) -> Task:
        """
        Task 실행 (Dify API 호출 + 응답 저장)

        Args:
            task_id: 실행할 Task ID

        Returns:
            실행 완료된 Task 객체
        """
        task = self.task_store.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # 상태 변경: pending → running
        task.status = TaskStatus.running
        self.task_store.update(task)

        try:
            # Dify API 요청 준비
            dify_request = self._convert_to_dify_request(task)

            # Dify API 스트리밍 호출
            dify_client = DifyClient(
                base_url=settings.dify_api_url,
                api_key=settings.dify_api_key,
            )

            full_response = ""
            dify_conversation_id = None

            try:
                async for event in dify_client.stream_chat(dify_request):
                    # 응답 누적
                    if event.event == "message" and event.answer:
                        full_response += event.answer

                    # conversation_id 저장
                    if event.conversation_id:
                        dify_conversation_id = event.conversation_id
            finally:
                await dify_client.close()

            # Agent 응답을 history에 추가
            agent_message = Message(
                role="agent",
                parts=[TextPart(text=full_response)],
            )
            task.history.append(agent_message)

            # Artifact 생성 (응답을 artifact로 저장)
            artifact = Artifact(
                artifactId=f"artifact-{uuid.uuid4()}",
                name="Dify Response",
                parts=[TextPart(text=full_response)],
                metadata={"event_type": "message"},
            )
            task.artifacts.append(artifact)

            # Dify conversation_id 저장 (다음 요청에서 재사용)
            if dify_conversation_id:
                task.metadata["dify_conversation_id"] = dify_conversation_id

            # 상태 변경: running → completed
            task.status = TaskStatus.completed
            task.completedAt = datetime.now(timezone.utc)

        except Exception as e:
            # 실패 처리
            task.status = TaskStatus.failed
            task.error = str(e)
            task.completedAt = datetime.now(timezone.utc)

        # 업데이트 저장
        return self.task_store.update(task)

    def get_task(self, task_id: str) -> Optional[Task]:
        """Task 조회"""
        return self.task_store.get(task_id)

    def list_tasks(
        self,
        context_id: Optional[str] = None,
        status: Optional[TaskStatus] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[Task]:
        """Task 목록 조회"""
        return self.task_store.list(
            context_id=context_id,
            status=status,
            limit=limit,
            offset=offset,
        )

    def cancel_task(self, task_id: str) -> Task:
        """
        Task 취소

        Args:
            task_id: 취소할 Task ID

        Returns:
            취소된 Task 객체
        """
        task = self.task_store.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # 이미 완료된 Task는 취소 불가
        if task.status in [TaskStatus.completed, TaskStatus.failed, TaskStatus.canceled]:
            raise ValueError(f"Cannot cancel task in status: {task.status}")

        # 상태 변경
        task.status = TaskStatus.canceled
        task.completedAt = datetime.now(timezone.utc)

        return self.task_store.update(task)

    def _convert_to_dify_request(self, task: Task) -> DifyChatRequest:
        """
        Task → DifyChatRequest 변환

        마지막 사용자 메시지를 query로 사용
        """
        # 마지막 사용자 메시지 추출
        query = ""
        for msg in reversed(task.history):
            if msg.role == "user":
                # Parts에서 텍스트 추출
                for part in msg.parts:
                    if isinstance(part, TextPart):
                        query = part.text
                        break
                if query:
                    break

        # user_id = contextId (또는 anonymous)
        user_id = task.contextId if task.contextId else "anonymous"

        # Dify conversation_id 재사용 (있으면)
        conversation_id = task.metadata.get("dify_conversation_id")

        return DifyChatRequest(
            inputs={},
            query=query,
            response_mode="streaming",
            conversation_id=conversation_id,  # 재사용으로 컨텍스트 유지
            user=user_id,
        )
