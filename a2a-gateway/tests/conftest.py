import os

import pytest
import httpx


@pytest.fixture
def a2a_gateway_url():
    """A2A Gateway URL (환경에 따라 변경)"""
    return os.getenv("A2A_GATEWAY_URL", "http://localhost:8080")


@pytest.fixture
def dify_api_key():
    """Dify API Key (실제 테스트용)"""
    api_key = os.getenv("DIFY_API_KEY")
    if not api_key:
        pytest.skip("DIFY_API_KEY not set")
    return api_key


@pytest.fixture
async def http_client():
    """비동기 HTTP 클라이언트"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client
