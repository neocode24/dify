import logging
from typing import Any, Optional

from models.a2a import A2ARequest
from models.dify import DifyChatRequest, DifySSEEvent

logger = logging.getLogger(__name__)


class A2ADifyTranslator:
    """A2A ↔ Dify 프로토콜 변환기"""

    def __init__(self, session_manager: Optional["SessionManager"] = None):
        """
        Args:
            session_manager: Redis 기반 세션 관리자 (선택적)
        """
        self.session_manager = session_manager

    def a2a_to_dify(self, a2a_request: A2ARequest) -> DifyChatRequest:
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

        # User ID 결정
        user_id = self._determine_user_id(a2a_request, params.conversation_id)

        return DifyChatRequest(
            inputs={},
            query=query,
            response_mode="streaming",
            conversation_id=params.conversation_id,
            user=user_id,
        )

    def _determine_user_id(self, a2a_request: A2ARequest, conversation_id: Optional[str]) -> str:
        """User ID 결정: conversation_id 있으면 Redis 조회, 없으면 새로 생성"""

        # Redis 사용 불가능하면 fallback
        if not self.session_manager or not self.session_manager.is_enabled():
            logger.warning("Redis 비활성화 - 고정 user_id 사용 (다중 클라이언트 미지원)")
            return "a2a-gateway-user"

        # conversation_id 있으면 Redis 조회
        if conversation_id:
            user_id = self.session_manager.get_user_id_for_conversation(conversation_id)
            if user_id:
                return user_id
            # Redis에 없으면 fallback
            logger.warning(f"conversation_id {conversation_id}의 user_id를 찾을 수 없음 - fallback")
            return "a2a-gateway-user"

        # 새 대화: request.id로 user_id 생성
        return self.session_manager.generate_user_id(a2a_request.id)

    def store_conversation_user(self, conversation_id: str, user_id: str):
        """대화-사용자 매핑 저장"""
        if self.session_manager:
            self.session_manager.save_conversation_mapping(conversation_id, user_id)

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
