from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, Union

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


# ============================================================================
# Task API Models (Phase 2)
# ============================================================================


class TaskStatus(str, Enum):
    """Task 실행 상태"""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"
    input_required = "input-required"
    auth_required = "auth-required"


class TextPart(BaseModel):
    """텍스트 Part"""

    type: Literal["text"] = "text"
    text: str


class FilePart(BaseModel):
    """파일 Part (bytes 또는 URI)"""

    type: Literal["file"] = "file"
    name: str
    mimeType: Optional[str] = None
    uri: Optional[str] = None
    bytes: Optional[str] = None  # Base64 encoded


class DataPart(BaseModel):
    """구조화된 데이터 Part"""

    type: Literal["data"] = "data"
    data: dict[str, Any]


# Part 타입 Union
Part = Union[TextPart, FilePart, DataPart]


class Message(BaseModel):
    """Task에 포함되는 메시지 (Parts 기반)"""

    role: Literal["user", "agent"]
    parts: list[Part]
    timestamp: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))


class Artifact(BaseModel):
    """Task 실행 결과물"""

    artifactId: str
    name: Optional[str] = None
    description: Optional[str] = None
    parts: list[Part]
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Task(BaseModel):
    """A2A Task 객체"""

    id: str  # task-{uuid}
    contextId: str  # 세션 식별자
    status: TaskStatus
    history: list[Message] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)  # dify_conversation_id 저장
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completedAt: Optional[datetime] = None
    error: Optional[str] = None


# ============================================================================
# Task API Request/Response Parameters
# ============================================================================


class TaskCreateParams(BaseModel):
    """tasks/create 파라미터"""

    contextId: Optional[str] = None  # 없으면 자동 생성
    message: Message  # 초기 사용자 메시지


class TaskGetParams(BaseModel):
    """tasks/get 파라미터"""

    taskId: str


class TaskListParams(BaseModel):
    """tasks/list 파라미터"""

    contextId: Optional[str] = None  # 없으면 전체 조회
    status: Optional[TaskStatus] = None
    limit: int = 10
    offset: int = 0


class TaskCancelParams(BaseModel):
    """tasks/cancel 파라미터"""

    taskId: str


class TaskRequest(BaseModel):
    """Task API JSON-RPC 요청"""

    jsonrpc: str = "2.0"
    id: str | int
    method: str  # "tasks/create", "tasks/get", "tasks/list", "tasks/cancel"
    params: Union[TaskCreateParams, TaskGetParams, TaskListParams, TaskCancelParams]
