import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import chat, tasks

logger = logging.getLogger(__name__)

# Debug 모드 활성화 시 로깅 레벨 조정
if settings.debug:
    logging.getLogger().setLevel(logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    logger.info("🐛 Debug mode enabled")

app = FastAPI(
    title="Dify A2A Gateway",
    version="0.4.0",  # Phase 2.1: A2A 표준 준수
    description="A2A Protocol gateway for Dify with full A2A standard compliance",
)


# Debug 미들웨어
@app.middleware("http")
async def debug_middleware(request: Request, call_next):
    """Debug 모드 활성화 시 요청/응답 로깅"""
    if settings.debug_log_requests:
        logger.debug(f"📥 Request: {request.method} {request.url}")
        logger.debug(f"   Headers: {dict(request.headers)}")
        if request.method in ["POST", "PUT", "PATCH"]:
            body = await request.body()
            logger.debug(f"   Body: {body.decode('utf-8')[:500]}")  # 처음 500자만

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    if settings.debug_log_responses:
        logger.debug(f"📤 Response: {response.status_code} (took {process_time:.3f}s)")

    return response

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chat.router)
app.include_router(tasks.router)


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 초기화"""
    logger.info("🚀 Dify A2A Gateway 시작")
    logger.info(f"  - Dify API: {settings.dify_api_url}")


@app.get("/health")
async def health():
    """헬스체크 엔드포인트"""
    return {
        "status": "ok",
        "service": "dify-a2a-gateway",
        "version": "0.4.0",  # Phase 2.1
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
