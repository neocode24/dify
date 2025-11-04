from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """A2A Gateway 설정"""

    # Gateway 설정
    port: int = 8080
    host: str = "0.0.0.0"
    log_level: str = "INFO"

    # Dify API 연결
    dify_api_url: str = "http://api:5001"
    dify_api_key: str  # 필수

    # 선택적 설정
    dify_app_id: str = ""
    cors_origins: list[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
