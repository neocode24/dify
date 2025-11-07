"""
Task API Router

A2A Task API endpoints:
- tasks/get: Task 조회
- tasks/list: Task 목록 조회
- tasks/cancel: Task 취소
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from models.a2a import Task, TaskGetParams, TaskListParams, TaskCancelParams, TaskStatus
from routers.chat import task_manager

logger = logging.getLogger(__name__)
router = APIRouter()


class TaskGetRequest(BaseModel):
    """tasks/get 요청"""

    jsonrpc: str = "2.0"
    id: str | int
    method: str = "tasks/get"
    params: TaskGetParams


class TaskListRequest(BaseModel):
    """tasks/list 요청"""

    jsonrpc: str = "2.0"
    id: str | int
    method: str = "tasks/list"
    params: TaskListParams


class TaskCancelRequest(BaseModel):
    """tasks/cancel 요청"""

    jsonrpc: str = "2.0"
    id: str | int
    method: str = "tasks/cancel"
    params: TaskCancelParams


@router.post("/tasks/get")
async def get_task(request: TaskGetRequest):
    """
    Task 조회

    POST /tasks/get
    {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "tasks/get",
      "params": {
        "taskId": "task-xxx"
      }
    }
    """
    task = task_manager.get_task(request.params.taskId)

    if not task:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {
                "code": -32602,
                "message": f"Task not found: {request.params.taskId}",
            },
        }

    # Task 객체를 dict로 변환
    return {
        "jsonrpc": "2.0",
        "id": request.id,
        "result": task.model_dump(mode="json"),
    }


@router.post("/tasks/list")
async def list_tasks(request: TaskListRequest):
    """
    Task 목록 조회

    POST /tasks/list
    {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "tasks/list",
      "params": {
        "contextId": "session-123",  // optional
        "status": "completed",       // optional
        "limit": 10,
        "offset": 0
      }
    }
    """
    tasks = task_manager.list_tasks(
        context_id=request.params.contextId,
        status=request.params.status,
        limit=request.params.limit,
        offset=request.params.offset,
    )

    return {
        "jsonrpc": "2.0",
        "id": request.id,
        "result": {
            "tasks": [t.model_dump(mode="json") for t in tasks],
            "total": len(tasks),
        },
    }


@router.post("/tasks/cancel")
async def cancel_task(request: TaskCancelRequest):
    """
    Task 취소

    POST /tasks/cancel
    {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "tasks/cancel",
      "params": {
        "taskId": "task-xxx"
      }
    }
    """
    try:
        task = task_manager.cancel_task(request.params.taskId)

        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "result": task.model_dump(mode="json"),
        }

    except ValueError as e:
        return {
            "jsonrpc": "2.0",
            "id": request.id,
            "error": {
                "code": -32602,
                "message": str(e),
            },
        }
