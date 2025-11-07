import json
import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from models.a2a import (
    A2ARequest,
    Message,
    TextPart,
    Artifact,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    TaskStatus,
)
from services.task_store import TaskStore
from services.task_manager import TaskManager

logger = logging.getLogger(__name__)
router = APIRouter()

# Global TaskStore instance (singleton)
task_store = TaskStore()
task_manager = TaskManager(task_store)


@router.post("/a2a")
async def handle_a2a_chat(request: A2ARequest):
    """
    A2A Protocol 엔드포인트 (Phase 2.1: 표준 준수)

    POST /a2a
    {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "message.send",
      "params": {
        "task": null,  # 선택: 기존 Task
        "messages": [{"role": "user", "parts": [{"type": "text", "text": "Hello"}]}],
        "configuration": {"stream": true}
      }
    }

    Breaking Changes (v0.4.0):
    - messages는 Parts 기반 (content → parts)
    - SSE 이벤트: TaskStatusUpdateEvent, TaskArtifactUpdateEvent
    """
    # 마지막 사용자 메시지 추출
    a2a_messages = request.params.messages
    last_user_message = None

    for msg in reversed(a2a_messages):
        if msg.role == "user":
            last_user_message = msg
            break

    if not last_user_message:
        # 사용자 메시지가 없으면 에러
        error_response = {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {"code": -32602, "message": "No user message found"},
        }
        return StreamingResponse(
            iter([f"data: {json.dumps(error_response)}\n\n"]),
            media_type="text/event-stream",
        )

    # Task 생성 또는 재사용
    if request.params.task:
        # 기존 Task에 메시지 추가 (향후 구현)
        task = request.params.task
        logger.info(f"Reusing existing task {task.id}")
    else:
        # 새 Task 생성
        # contextId: params.contextId 또는 자동 생성
        context_id = request.params.contextId if hasattr(request.params, 'contextId') else None
        task = await task_manager.create_task(
            context_id=context_id,
            initial_message=last_user_message,
        )
        logger.info(f"Created task {task.id} for contextId {task.contextId}")

    # 스트리밍 응답 생성 (A2A 표준 이벤트)
    async def event_generator():
        try:
            # Task 실행 (비동기 background로 실행)
            result = await task_manager.run_task(task.id)

            # A2A 표준: TaskStatusUpdateEvent 전송
            if result.status.value == "completed":
                # 1. TaskStatusUpdateEvent (running → completed)
                status_event = TaskStatusUpdateEvent(
                    taskId=result.id,
                    status=TaskStatus.completed,
                    contextId=result.contextId,
                )
                status_response = {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "result": status_event.model_dump(mode="json"),
                }
                yield f"data: {json.dumps(status_response)}\n\n"

                # 2. TaskArtifactUpdateEvent (각 Artifact마다)
                for artifact in result.artifacts:
                    artifact_event = TaskArtifactUpdateEvent(
                        taskId=result.id,
                        artifact=artifact,
                        contextId=result.contextId,
                    )
                    artifact_response = {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": artifact_event.model_dump(mode="json"),
                    }
                    yield f"data: {json.dumps(artifact_response)}\n\n"

            elif result.status.value == "failed":
                # TaskStatusUpdateEvent (failed)
                status_event = TaskStatusUpdateEvent(
                    taskId=result.id,
                    status=TaskStatus.failed,
                    contextId=result.contextId,
                )
                status_response = {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "result": status_event.model_dump(mode="json"),
                }
                yield f"data: {json.dumps(status_response)}\n\n"

                # 에러 정보
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "error": {
                        "code": -32000,
                        "message": result.error or "Task failed",
                        "data": {"taskId": result.id},
                    },
                }
                yield f"data: {json.dumps(error_response)}\n\n"

        except Exception as e:
            logger.error(f"Error in task execution: {e}", exc_info=True)
            error_response = {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32000, "message": str(e)},
            }
            yield f"data: {json.dumps(error_response)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
