import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from models.a2a import A2ARequest, Message, TextPart
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
    A2A Protocol 엔드포인트 (Task 기반)

    POST /a2a
    {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "message.send",
      "params": {
        "messages": [{"role": "user", "content": "Hello"}],
        "contextId": "session-123",
        "stream": true
      }
    }

    응답에 taskId 추가 (Breaking Change v0.3.0)
    """
    # A2A 메시지 → Task Message 변환
    a2a_messages = request.params.messages
    last_user_message = None

    for msg in reversed(a2a_messages):
        if msg.role == "user":
            last_user_message = Message(
                role="user",
                parts=[TextPart(text=msg.content)],
            )
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

    # Task 생성
    context_id = request.params.contextId
    task = await task_manager.create_task(
        context_id=context_id,
        initial_message=last_user_message,
    )

    logger.info(f"Created task {task.id} for contextId {task.contextId}")

    # 스트리밍 응답 생성
    async def event_generator():
        try:
            # Task 실행 (비동기 background로 실행)
            result = await task_manager.run_task(task.id)

            # Agent 응답을 스트리밍으로 전송
            if result.status.value == "completed":
                # 마지막 agent 메시지 추출
                agent_message = None
                for msg in reversed(result.history):
                    if msg.role == "agent":
                        agent_message = msg
                        break

                if agent_message:
                    # Parts에서 텍스트 추출
                    full_text = ""
                    for part in agent_message.parts:
                        if isinstance(part, TextPart):
                            full_text += part.text

                    # content_delta 이벤트 전송
                    delta_response = {
                        "jsonrpc": "2.0",
                        "id": request.id,
                        "result": {
                            "type": "content_delta",
                            "delta": full_text,
                            "contextId": result.contextId,
                            "taskId": result.id,  # Breaking Change: taskId 추가
                        },
                    }
                    yield f"data: {json.dumps(delta_response)}\n\n"

                # message_end 이벤트 전송
                end_response = {
                    "jsonrpc": "2.0",
                    "id": request.id,
                    "result": {
                        "type": "message_end",
                        "contextId": result.contextId,
                        "taskId": result.id,
                    },
                }
                yield f"data: {json.dumps(end_response)}\n\n"

            elif result.status.value == "failed":
                # 실패 시 에러 응답
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
