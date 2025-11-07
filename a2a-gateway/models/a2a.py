from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class A2AMessage(BaseModel):
    """A2A 프로토콜 메시지"""

    role: Literal["user", "agent"]
    content: str


class A2AChatParams(BaseModel):
    """A2A message.send 파라미터"""

    messages: list[A2AMessage]
    contextId: Optional[str] = None
    stream: bool = True


class A2ARequest(BaseModel):
    """A2A JSON-RPC 요청"""

    jsonrpc: str = "2.0"
    id: str | int
    method: str  # "chat.create", "chat.listMessages" 등
    params: A2AChatParams


class A2AResponse(BaseModel):
    """A2A JSON-RPC 응답"""

    jsonrpc: str = "2.0"
    id: str | int
    result: Optional[Any] = None
    error: Optional[dict] = None


class A2AError(BaseModel):
    """A2A 에러 응답"""

    jsonrpc: str = "2.0"
    id: str | int
    error: dict = Field(
        default_factory=lambda: {
            "code": -32000,
            "message": "Server error",
        }
    )
