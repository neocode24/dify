import logging
from typing import Any, Optional

from models.a2a import A2ARequest
from models.dify import DifyChatRequest, DifySSEEvent

logger = logging.getLogger(__name__)


class A2ADifyTranslator:
    """A2A ↔ Dify 프로토콜 변환기"""

    @staticmethod
    def a2a_to_dify(a2a_request: A2ARequest) -> DifyChatRequest:
        """
        A2A message.send → Dify /v1/chat-messages
        """
        params = a2a_request.params

        # A2A messages에서 마지막 user 메시지 추출
        query = ""
        for msg in reversed(params.messages):
            if msg.role == "user":
                query = msg.content
                break

        # User ID: contextId 사용, 없으면 anonymous
        user_id = params.contextId if params.contextId else "anonymous"

        return DifyChatRequest(
            inputs={},
            query=query,
            response_mode="streaming",
            conversation_id=None,  # Dify가 생성
            user=user_id,
        )

    @staticmethod
    def dify_to_a2a(dify_event: DifySSEEvent, request_id: str | int, context_id: Optional[str] = None) -> Optional[dict[str, Any]]:
        """
        Dify SSE → A2A JSON-RPC

        Args:
            dify_event: Dify SSE 이벤트
            request_id: A2A 요청 ID
            context_id: A2A contextId (클라이언트에서 전달받은 값)
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
                    "contextId": context_id,
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
                    "contextId": context_id,
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
