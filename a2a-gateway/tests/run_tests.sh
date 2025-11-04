#!/bin/bash
set -e

echo "🧪 A2A Gateway 테스트 실행"
echo ""

# 색상 정의
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. 단위 테스트 (빠름, Mock 사용)
echo "${GREEN}✅ 단위 테스트 실행...${NC}"
if pytest tests/unit/ -v -m unit; then
    echo "${GREEN}✅ 단위 테스트 통과!${NC}"
else
    echo "${RED}❌ 단위 테스트 실패${NC}"
    exit 1
fi
echo ""

# 2. 통합 테스트 (Docker 필요)
echo "${GREEN}✅ 통합 테스트 실행 확인...${NC}"

# Docker Compose 실행 여부 확인
if command -v docker &> /dev/null; then
    cd ../../docker
    if docker compose ps a2a-gateway 2>/dev/null | grep -q "Up"; then
        echo "${GREEN}✅ Docker Compose 실행 중. 통합 테스트 시작...${NC}"
        cd ../a2a-gateway

        # A2A Gateway URL 설정
        export A2A_GATEWAY_URL="${A2A_GATEWAY_URL:-http://localhost:8080}"

        # Health check
        echo "${YELLOW}⏳ Gateway health check...${NC}"
        for i in {1..10}; do
            if curl -sf "$A2A_GATEWAY_URL/health" > /dev/null 2>&1; then
                echo "${GREEN}✅ Gateway 응답 확인${NC}"
                break
            fi
            if [ $i -eq 10 ]; then
                echo "${RED}❌ Gateway가 응답하지 않습니다${NC}"
                exit 1
            fi
            echo "${YELLOW}   재시도 $i/10...${NC}"
            sleep 2
        done

        # 통합 테스트 실행
        if pytest tests/integration/ -v -m integration; then
            echo "${GREEN}✅ 통합 테스트 통과!${NC}"
        else
            echo "${RED}❌ 통합 테스트 실패${NC}"
            exit 1
        fi
    else
        echo "${YELLOW}⚠️  Docker Compose가 실행되지 않음. 통합 테스트 Skip.${NC}"
        echo "${YELLOW}   실행 방법: cd docker && docker compose up -d a2a-gateway${NC}"
    fi
else
    echo "${YELLOW}⚠️  Docker가 설치되지 않음. 통합 테스트 Skip.${NC}"
fi
echo ""

echo "${GREEN}✅ 모든 테스트 완료!${NC}"
