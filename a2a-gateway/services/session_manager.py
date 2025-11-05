import hashlib
import logging
from typing import Optional

import redis

from config import settings

logger = logging.getLogger(__name__)


class SessionManager:
    """Conversation ID → User ID 매핑 관리"""

    def __init__(self):
        """설정에서 Redis 연결 정보 가져오기"""
        self.enabled = settings.redis_enabled
        self.ttl_seconds = settings.redis_ttl_days * 24 * 3600

        if self.enabled:
            try:
                self.redis = redis.Redis.from_url(
                    settings.redis_connection_url, decode_responses=True, socket_connect_timeout=5
                )
                # 연결 테스트
                self.redis.ping()
                logger.info(f"Redis 연결 성공: {settings.redis_host}:{settings.redis_port}")
            except Exception as e:
                logger.warning(f"Redis 연결 실패: {e}. Fallback 모드로 동작합니다.")
                self.enabled = False
                self.redis = None
        else:
            logger.info("Redis가 비활성화되었습니다. 단일 user_id 모드로 동작합니다.")
            self.redis = None

    def is_enabled(self) -> bool:
        """Redis 사용 가능 여부"""
        return self.enabled and self.redis is not None

    def get_user_id_for_conversation(self, conversation_id: str) -> Optional[str]:
        """conversation_id로 user_id 조회"""
        if not self.is_enabled():
            return None

        try:
            key = f"conv:{conversation_id}"
            user_id = self.redis.get(key)
            if user_id:
                logger.debug(f"Redis 조회 성공: {conversation_id} → {user_id}")
            return user_id
        except Exception as e:
            logger.error(f"Redis 조회 실패: {e}")
            return None

    def save_conversation_mapping(self, conversation_id: str, user_id: str):
        """conversation_id → user_id 매핑 저장"""
        if not self.is_enabled():
            return

        try:
            key = f"conv:{conversation_id}"
            self.redis.setex(key, self.ttl_seconds, user_id)
            logger.debug(f"Redis 저장 성공: {conversation_id} → {user_id} (TTL: {settings.redis_ttl_days}일)")
        except Exception as e:
            logger.error(f"Redis 저장 실패: {e}")

    def generate_user_id(self, identifier: str) -> str:
        """식별자로부터 user_id 생성"""
        hash_value = hashlib.md5(identifier.encode()).hexdigest()[:8]
        return f"a2a-user-{hash_value}"

    def health_check(self) -> dict:
        """Redis 상태 확인"""
        if not self.is_enabled():
            return {"redis_enabled": False, "status": "disabled", "message": "Redis is disabled in configuration"}

        try:
            self.redis.ping()
            info = self.redis.info("server")
            return {
                "redis_enabled": True,
                "status": "healthy",
                "redis_version": info.get("redis_version"),
                "uptime_days": info.get("uptime_in_days"),
            }
        except Exception as e:
            return {"redis_enabled": True, "status": "error", "message": str(e)}
