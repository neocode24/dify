import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from config import settings
from models.a2a import A2ARequest
from services.dify_client import DifyClient
from services.session_manager import SessionManager
from services.translator import A2ADifyTranslator

logger = logging.getLogger(__name__)
router = APIRouter()

# SessionManager 전역 인스턴스 (앱 수명주기 동안 유지)
session_manager = SessionManager()


@router.post("/a2a")
async def handle_a2a_chat(request: A2ARequest):
    """
    A2A Protocol 엔드포인트

    POST /a2a
    {
      "jsonrpc": "2.0",
      "id": "1",
      "method": "chat.create",
      "params": {
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": true
      }
    }
    """
    # A2A → Dify 변환 (SessionManager 주입)
    translator = A2ADifyTranslator(session_manager=session_manager)
    dify_request = translator.a2a_to_dify(request)

    # User ID 추출 (conversation_id 매핑 저장용)
    user_id = dify_request.user

    # 스트리밍 응답 생성
    async def event_generator():
        # DifyClient를 generator 내부에서 생성하여 lifecycle 관리
        dify = DifyClient(base_url=settings.dify_api_url, api_key=settings.dify_api_key)
        try:
            async for dify_event in dify.stream_chat(dify_request):
                # 첫 conversation_id 수신 시 Redis 저장
                if dify_event.conversation_id and dify_event.event == "message":
                    translator.store_conversation_user(dify_event.conversation_id, user_id)

                # Dify SSE → A2A JSON-RPC 변환
                a2a_response = translator.dify_to_a2a(dify_event, request.id)

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
