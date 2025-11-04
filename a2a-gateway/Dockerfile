FROM python:3.11-slim

WORKDIR /app

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# 의존성 복사 및 설치
COPY pyproject.toml ./
RUN uv pip install --system --no-cache-dir -r pyproject.toml

# 소스 복사
COPY . .

# 포트 노출
EXPOSE 8080

# 실행
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
