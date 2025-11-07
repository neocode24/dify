import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import chat, tasks

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dify A2A Gateway",
    version="0.4.0",  # Phase 2.1: A2A 표준 준수
    description="A2A Protocol gateway for Dify with full A2A standard compliance",
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
