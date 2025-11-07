from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """A2A Gateway 설정"""

    # Gateway 설정
    port: int = 8080
    host: str = "0.0.0.0"
    log_level: str = "INFO"
    debug: bool = False  # Debug 모드 (상세 로깅 활성화)

    # Dify API 연결
    dify_api_url: str = "http://api:5001"
    dify_api_key: str  # 필수

    # 선택적 설정
    dify_app_id: str = ""
    cors_origins: list[str] = ["*"]

    # Debug 전용 설정
    debug_log_requests: bool = False  # 모든 요청 로깅
    debug_log_responses: bool = False  # 모든 응답 로깅
    debug_log_dify_calls: bool = False  # Dify API 호출 로깅

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
