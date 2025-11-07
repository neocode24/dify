import pytest
from pydantic import ValidationError

from models.a2a import A2AChatParams, A2AError, A2AMessage, A2ARequest
from models.dify import DifyChatRequest, DifySSEEvent


@pytest.mark.unit
class TestA2AModels:
    """A2A 프로토콜 모델 검증"""

    def test_a2a_request_valid(self):
        """유효한 A2A 요청"""
        request = A2ARequest(
            id="1",
            method="chat.create",
            params=A2AChatParams(messages=[A2AMessage(role="user", content="Hello")]),
        )
        assert request.jsonrpc == "2.0"
        assert request.id == "1"
        assert request.method == "chat.create"

    def test_a2a_request_with_int_id(self):
        """정수 ID도 허용"""
        request = A2ARequest(
            id=123, method="chat.create", params=A2AChatParams(messages=[A2AMessage(role="user", content="Hello")])
        )
        assert request.id == 123

    def test_a2a_message_valid_roles(self):
        """유효한 role 값들"""
        user_msg = A2AMessage(role="user", content="Hello")
        assert user_msg.role == "user"

        agent_msg = A2AMessage(role="agent", content="Hi")
        assert agent_msg.role == "agent"

    def test_a2a_message_invalid_role(self):
        """잘못된 role 거부"""
        with pytest.raises(ValidationError) as exc_info:
            A2AMessage(role="invalid", content="test")

        assert "role" in str(exc_info.value).lower()

    def test_a2a_chat_params_defaults(self):
        """기본값 확인"""
        params = A2AChatParams(messages=[A2AMessage(role="user", content="Hello")])

        assert params.contextId is None
        assert params.stream is True

    def test_a2a_chat_params_with_context_id(self):
        """contextId 설정"""
        params = A2AChatParams(messages=[A2AMessage(role="user", content="Hello")], contextId="session-123")

        assert params.contextId == "session-123"

    def test_a2a_error_default(self):
        """A2A 에러 기본값"""
        error = A2AError(id="test-1")

        assert error.jsonrpc == "2.0"
        assert error.error["code"] == -32000
        assert "error" in error.error["message"].lower()


@pytest.mark.unit
class TestDifyModels:
    """Dify API 모델 검증"""

    def test_dify_chat_request_minimal(self):
        """최소 필수 필드"""
        request = DifyChatRequest(query="Hello", user="test-user")

        assert request.query == "Hello"
        assert request.user == "test-user"

    def test_dify_chat_request_defaults(self):
        """기본값 확인"""
        request = DifyChatRequest(query="Hello", user="test-user")

        assert request.response_mode == "streaming"
        assert request.inputs == {}
        assert request.conversation_id is None
        assert request.files is None

    def test_dify_chat_request_with_conversation_id(self):
        """conversation_id 설정"""
        request = DifyChatRequest(query="Hello", user="test-user", conversation_id="conv-123")

        assert request.conversation_id == "conv-123"

    def test_dify_sse_event_message(self):
        """message 이벤트"""
        event = DifySSEEvent(event="message", answer="안녕하세요", conversation_id="conv-123")

        assert event.event == "message"
        assert event.answer == "안녕하세요"
        assert event.conversation_id == "conv-123"

    def test_dify_sse_event_message_end(self):
        """message_end 이벤트"""
        event = DifySSEEvent(event="message_end", message_id="msg-456", conversation_id="conv-123")

        assert event.event == "message_end"
        assert event.message_id == "msg-456"

    def test_dify_sse_event_error(self):
        """error 이벤트"""
        event = DifySSEEvent(event="error", status=400, code="invalid_api_key", message="API key is invalid")

        assert event.event == "error"
        assert event.status == 400
        assert event.code == "invalid_api_key"
        assert event.message == "API key is invalid"

    def test_dify_sse_event_extra_fields(self):
        """추가 필드 허용 (extra='allow')"""
        event = DifySSEEvent(event="custom_event", custom_field="custom_value")

        assert event.event == "custom_event"
        # Config extra='allow'로 인해 추가 필드도 허용됨
