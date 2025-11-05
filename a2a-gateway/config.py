from typing import Optional

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

    # Redis 설정 (Session 관리)
    redis_enabled: bool = True  # Redis 사용 여부
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    redis_url: Optional[str] = None  # 우선순위: redis_url > redis_host
    redis_ttl_days: int = 1  # conversation 매핑 TTL (일 단위)

    # 선택적 설정
    dify_app_id: str = ""
    cors_origins: list[str] = ["*"]

    @property
    def redis_connection_url(self) -> str:
        """Redis 연결 URL 생성"""
        if self.redis_url:
            return self.redis_url

        password_part = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{password_part}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
