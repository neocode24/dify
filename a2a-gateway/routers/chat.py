import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from config import settings
from models.a2a import A2ARequest
from services.dify_client import DifyClient
from services.translator import A2ADifyTranslator

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/a2a")
async def handle_a2a_chat(request: A2ARequest):
    """
    A2A Protocol 엔드포인트

    POST /a2a
    {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "message.send",
      "params": {
        "messages": [{"role": "user", "content": "Hello"}],
        "contextId": "session-123",
        "stream": true
      }
    }
    """
    # A2A → Dify 변환
    dify_request = A2ADifyTranslator.a2a_to_dify(request)

    # contextId 추출 (A2A 응답에 포함)
    context_id = request.params.contextId

    # 스트리밍 응답 생성
    async def event_generator():
        # DifyClient를 generator 내부에서 생성하여 lifecycle 관리
        dify = DifyClient(base_url=settings.dify_api_url, api_key=settings.dify_api_key)
        try:
            async for dify_event in dify.stream_chat(dify_request):
                # Dify SSE → A2A JSON-RPC 변환 (contextId 포함)
                a2a_response = A2ADifyTranslator.dify_to_a2a(dify_event, request.id, context_id)

                if a2a_response:
                    # SSE 형식으로 전송
                    yield f"data: {json.dumps(a2a_response)}\n\n"

        except Exception as e:
            # 에러 발생 시 A2A 에러 응답
            error_response = {
                "jsonrpc": "2.0",
                "id": request.id,
                "error": {"code": -32000, "message": str(e)},
            }
            yield f"data: {json.dumps(error_response)}\n\n"

        finally:
            await dify.close()

    return StreamingResponse(event_generator(), media_type="text/event-stream")
