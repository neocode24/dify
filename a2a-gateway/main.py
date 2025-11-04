from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import chat

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


@app.get("/health")
async def health():
    """헬스체크 엔드포인트"""
    return {"status": "ok", "service": "dify-a2a-gateway"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
