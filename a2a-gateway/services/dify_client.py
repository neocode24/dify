import json
from typing import AsyncGenerator

import httpx
from httpx_sse import aconnect_sse

from models.dify import DifyChatRequest, DifySSEEvent


class DifyClient:
    """Dify API 클라이언트"""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=300.0)

    async def stream_chat(self, request: DifyChatRequest) -> AsyncGenerator[DifySSEEvent, None]:
        """
        Dify Chat API 스트리밍 호출

        POST /v1/chat-messages
        """
        url = f"{self.base_url}/v1/chat-messages"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        async with aconnect_sse(self.client, "POST", url, json=request.model_dump(), headers=headers) as event_source:
            async for sse in event_source.aiter_sse():
                try:
                    data = json.loads(sse.data)
                    yield DifySSEEvent(**data)
                except json.JSONDecodeError:
                    # 잘못된 JSON은 건너뛰기
                    continue
                except Exception as e:
                    # 기타 에러는 로깅 후 건너뛰기
                    print(f"Error parsing SSE event: {e}")
                    continue

    async def close(self):
        """클라이언트 종료"""
        await self.client.aclose()
