import json
import logging
from typing import AsyncGenerator

import httpx

from models.dify import DifyChatRequest, DifySSEEvent

logger = logging.getLogger(__name__)


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

        # 선택적 직렬화: inputs는 항상 포함, 나머지는 값이 있을 때만 포함
        request_data = {
            "inputs": request.inputs,
            "query": request.query,
            "response_mode": request.response_mode,
            "user": request.user,
        }
        if request.conversation_id:
            request_data["conversation_id"] = request.conversation_id
        if request.files:
            request_data["files"] = request.files

        logger.info(f"Dify API Request: {request_data}")

        # httpx stream - response를 yield 밖에서 유지하기 위해 변수로 저장
        response = self.client.stream("POST", url, json=request_data, headers=headers)
        async with response as resp:
            # 디버깅: 응답 헤더 로깅
            logger.info(f"Response Status: {resp.status_code}")
            logger.info(f"Response Content-Type: {resp.headers.get('content-type')}")

            # 상태 코드 확인
            resp.raise_for_status()

            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    try:
                        data_str = line[5:].strip()  # "data: " 제거
                        if data_str:
                            data = json.loads(data_str)
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
