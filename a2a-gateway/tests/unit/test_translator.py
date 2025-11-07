import pytest

from models.a2a import A2AChatParams, A2AMessage, A2ARequest
from models.dify import DifySSEEvent
from services.translator import A2ADifyTranslator


@pytest.mark.unit
class TestA2ADifyTranslator:
    """프로토콜 변환기 단위 테스트"""

    def test_a2a_to_dify_single_message(self):
        """A2A → Dify 변환: 단일 메시지 (contextId 없음)"""
        a2a_request = A2ARequest(
            id="test-1",
            method="message.send",
            params=A2AChatParams(messages=[A2AMessage(role="user", content="안녕하세요")]),
        )

        dify_request = A2ADifyTranslator.a2a_to_dify(a2a_request)

        assert dify_request.query == "안녕하세요"
        assert dify_request.response_mode == "streaming"
        # contextId 없으면 anonymous 사용
        assert dify_request.user == "anonymous"
        # conversation_id는 None (Dify가 생성)
        assert dify_request.conversation_id is None

    def test_a2a_to_dify_with_context_id(self):
        """A2A → Dify 변환: contextId 포함"""
        a2a_request = A2ARequest(
            id="test-2",
            method="message.send",
            params=A2AChatParams(
                messages=[A2AMessage(role="user", content="계속 이야기해주세요")],
                contextId="session-123",
            ),
        )

        dify_request = A2ADifyTranslator.a2a_to_dify(a2a_request)

        # contextId가 user_id로 매핑
        assert dify_request.user == "session-123"
        # conversation_id는 항상 None
        assert dify_request.conversation_id is None

    def test_a2a_to_dify_multiple_messages(self):
        """A2A → Dify 변환: 여러 메시지 중 마지막 user 메시지 추출"""
        a2a_request = A2ARequest(
            id="test-3",
            method="message.send",
            params=A2AChatParams(
                messages=[
                    A2AMessage(role="user", content="첫 번째 메시지"),
                    A2AMessage(role="agent", content="응답"),
                    A2AMessage(role="user", content="두 번째 메시지"),
                ]
            ),
        )

        dify_request = A2ADifyTranslator.a2a_to_dify(a2a_request)

        # 마지막 user 메시지가 query가 되어야 함
        assert dify_request.query == "두 번째 메시지"

    def test_dify_to_a2a_message_event(self):
        """Dify → A2A 변환: message 이벤트 (스트리밍 청크)"""
        dify_event = DifySSEEvent(event="message", answer="안녕", conversation_id="conv-123")

        a2a_response = A2ADifyTranslator.dify_to_a2a(dify_event, "test-1", "session-123")

        assert a2a_response["jsonrpc"] == "2.0"
        assert a2a_response["id"] == "test-1"
        assert a2a_response["result"]["type"] == "content_delta"
        assert a2a_response["result"]["delta"] == "안녕"
        assert a2a_response["result"]["contextId"] == "session-123"

    def test_dify_to_a2a_message_event_no_context(self):
        """Dify → A2A 변환: message 이벤트 (contextId 없음)"""
        dify_event = DifySSEEvent(event="message", answer="안녕", conversation_id="conv-123")

        a2a_response = A2ADifyTranslator.dify_to_a2a(dify_event, "test-1", None)

        assert a2a_response["jsonrpc"] == "2.0"
        assert a2a_response["result"]["contextId"] is None

    def test_dify_to_a2a_message_end_event(self):
        """Dify → A2A 변환: message_end 이벤트"""
        dify_event = DifySSEEvent(event="message_end", message_id="msg-456", conversation_id="conv-123")

        a2a_response = A2ADifyTranslator.dify_to_a2a(dify_event, "test-1", "session-123")

        assert a2a_response["jsonrpc"] == "2.0"
        assert a2a_response["result"]["type"] == "complete"
        assert a2a_response["result"]["message_id"] == "msg-456"
        assert a2a_response["result"]["contextId"] == "session-123"

    def test_dify_to_a2a_error_event(self):
        """Dify → A2A 변환: error 이벤트"""
        dify_event = DifySSEEvent(event="error", message="API key is invalid")

        a2a_response = A2ADifyTranslator.dify_to_a2a(dify_event, "test-1", None)

        assert a2a_response["jsonrpc"] == "2.0"
        assert "error" in a2a_response
        assert a2a_response["error"]["code"] == -32000
        assert "invalid" in a2a_response["error"]["message"].lower()

    def test_dify_to_a2a_agent_thought_ignored(self):
        """Dify → A2A 변환: agent_thought 이벤트는 무시"""
        dify_event = DifySSEEvent(event="agent_thought", thought="Thinking...")

        a2a_response = A2ADifyTranslator.dify_to_a2a(dify_event, "test-1", None)

        # agent_thought는 None 반환
        assert a2a_response is None
