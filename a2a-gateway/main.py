import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import chat
from services.session_manager import SessionManager

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dify A2A Gateway",
    version="0.1.0",
    description="A2A Protocol gateway for Dify",
)

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


@app.on_event("startup")
async def startup_event():
    """앱 시작 시 초기화"""
    logger.info("🚀 Dify A2A Gateway 시작")
    logger.info(f"  - Dify API: {settings.dify_api_url}")
    logger.info(f"  - Redis: {'Enabled' if settings.redis_enabled else 'Disabled'}")

    # SessionManager 초기화 확인 (chat.router에서 생성됨)
    if settings.redis_enabled:
        health_status = chat.session_manager.health_check()
        if health_status["status"] == "healthy":
            logger.info(f"  - Redis 연결 성공: {settings.redis_host}:{settings.redis_port}")
        elif health_status["status"] == "error":
            logger.warning(f"  - Redis 연결 실패: {health_status.get('message')}")
        else:
            logger.info("  - Redis 비활성화 모드로 동작")


@app.get("/health")
async def health():
    """헬스체크 엔드포인트 (Redis 상태 포함)"""
    base_health = {
        "status": "ok",
        "service": "dify-a2a-gateway",
        "version": "0.1.0",
    }

    # Redis 상태 확인
    if settings.redis_enabled:
        redis_health = chat.session_manager.health_check()
        base_health["redis"] = redis_health

    return base_health


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
