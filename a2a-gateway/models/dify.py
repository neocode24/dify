from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class DifyChatRequest(BaseModel):
    """Dify Chat API 요청"""

    inputs: dict[str, Any] = {}
    query: str
    response_mode: str = "streaming"  # or "blocking"
    conversation_id: Optional[str] = None
    user: str
    files: Optional[list[dict]] = None


class DifySSEEvent(BaseModel):
    """Dify SSE 이벤트"""

    event: str  # "message", "message_end", "error", "agent_thought" 등
    task_id: Optional[str] = None
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    answer: Optional[str] = None
    created_at: Optional[int] = None

    # Agent 관련 필드
    thought: Optional[str] = None
    tool: Optional[str] = None
    tool_input: Optional[dict] = None
    observation: Optional[str] = None

    # 에러 관련
    status: Optional[int] = None
    code: Optional[str] = None
    message: Optional[str] = None

    # 기타 필드를 처리하기 위한 설정 (Pydantic v2)
    model_config = ConfigDict(extra="allow")
