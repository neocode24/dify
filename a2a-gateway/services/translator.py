import hashlib
from typing import Any, Optional

from models.a2a import A2ARequest
from models.dify import DifyChatRequest, DifySSEEvent


class A2ADifyTranslator:
    """A2A ↔ Dify 프로토콜 변환기"""

    @staticmethod
    def a2a_to_dify(a2a_request: A2ARequest) -> DifyChatRequest:
        """
        A2A chat.create → Dify /v1/chat-messages
        """
        params = a2a_request.params

        # A2A messages에서 마지막 user 메시지 추출
        query = ""
        for msg in reversed(params.messages):
            if msg.role == "user":
                query = msg.content
                break

        # 사용자 ID 생성 (A2A는 user 개념 없음)
        user_id = A2ADifyTranslator._generate_user_id(a2a_request.id)

        return DifyChatRequest(
            inputs={},
            query=query,
            response_mode="streaming",
            conversation_id=params.conversation_id,
            user=user_id,
        )

    @staticmethod
    def dify_to_a2a(dify_event: DifySSEEvent, request_id: str | int) -> Optional[dict[str, Any]]:
        """
        Dify SSE → A2A JSON-RPC
        """
        event_type = dify_event.event

        # message 이벤트: 스트리밍 청크
        if event_type == "message":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "type": "content_delta",
                    "delta": dify_event.answer or "",
                    "conversation_id": dify_event.conversation_id,
                },
            }

        # message_end: 완료
        elif event_type == "message_end":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "type": "complete",
                    "message_id": dify_event.message_id,
                    "conversation_id": dify_event.conversation_id,
                },
            }

        # error: 오류
        elif event_type == "error":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32000, "message": dify_event.message or "Unknown error"},
            }

        # agent_thought: Agent 사고 과정 (선택적으로 로깅)
        elif event_type == "agent_thought":
            # A2A에 직접 매핑되지 않으므로 로깅만 하거나 무시
            return None

        # 기타 이벤트는 무시
        return None

    @staticmethod
    def _generate_user_id(request_id: str | int) -> str:
        """요청 ID에서 일관된 user ID 생성"""
        return f"a2a-user-{hashlib.md5(str(request_id).encode()).hexdigest()[:8]}"
