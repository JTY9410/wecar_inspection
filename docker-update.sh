#!/bin/bash

# 위카아라이 검수시스템 Docker 업데이트 및 업로드 스크립트
# 프로그램이 수정되면 자동으로 Docker 이미지를 빌드하고 업로드합니다.

set -e

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 설정 파일 로드
if [ -f .docker-config ]; then
    source .docker-config
fi

# Docker Hub 설정
DOCKER_USERNAME="${DOCKER_USERNAME:-}"
IMAGE_NAME="wecar-inspection"
VERSION="${VERSION:-latest}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# 명령줄 인자로 사용자명 받기
if [ -n "$1" ]; then
    DOCKER_USERNAME="$1"
fi

# Docker Hub 로그인 정보에서 사용자명 가져오기 시도
if [ -z "$DOCKER_USERNAME" ]; then
    DOCKER_USERNAME=$(docker info 2>/dev/null | grep -i "username" | awk '{print $2}' | head -1)
fi

# 설정 확인
if [ -z "$DOCKER_USERNAME" ]; then
    echo -e "${YELLOW}Docker Hub 사용자명이 설정되지 않았습니다.${NC}"
    echo ""
    echo "사용법:"
    echo "  1. ./docker-update.sh your-username"
    echo "  2. export DOCKER_USERNAME=your-username && ./docker-update.sh"
    echo "  3. .docker-config 파일에 DOCKER_USERNAME 설정"
    echo ""
    if [ -t 0 ]; then
        # 터미널에서 실행 중인 경우에만 입력 받기
        read -p "Docker Hub 사용자명을 입력하세요: " DOCKER_USERNAME
        if [ -z "$DOCKER_USERNAME" ]; then
            echo -e "${RED}사용자명이 필요합니다.${NC}"
            exit 1
        fi
        # 설정 파일에 저장
        echo "DOCKER_USERNAME=$DOCKER_USERNAME" > .docker-config
        echo "설정이 저장되었습니다."
    else
        echo -e "${RED}사용자명이 필요합니다.${NC}"
        echo ""
        echo "다음 중 하나의 방법으로 사용자명을 제공하세요:"
        echo "  1. ./docker-update.sh your-username"
        echo "  2. export DOCKER_USERNAME=your-username && ./docker-update.sh"
        exit 1
    fi
fi

FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"
FULL_IMAGE_NAME_WITH_TIMESTAMP="${DOCKER_USERNAME}/${IMAGE_NAME}:${TIMESTAMP}"

echo "=========================================="
echo "위카아라이 검수시스템 Docker 업데이트"
echo "=========================================="
echo "이미지 이름: ${FULL_IMAGE_NAME}"
echo "타임스탬프 버전: ${FULL_IMAGE_NAME_WITH_TIMESTAMP}"
echo ""

# Docker 설치 확인
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker가 설치되어 있지 않습니다.${NC}"
    exit 1
fi

# Docker 서비스 실행 확인
if ! docker info &> /dev/null; then
    echo -e "${RED}Docker 서비스가 실행되지 않았습니다.${NC}"
    exit 1
fi

# Docker Hub 로그인 확인
if ! docker info 2>/dev/null | grep -q "Username"; then
    echo -e "${YELLOW}Docker Hub에 로그인이 필요합니다.${NC}"
    read -p "지금 로그인하시겠습니까? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker login
    else
        echo -e "${RED}로그인이 필요합니다.${NC}"
        exit 1
    fi
fi

# 변경사항 확인 (Git 사용 시)
if [ -d .git ]; then
    echo "변경사항 확인 중..."
    if [ -n "$(git status --porcelain)" ]; then
        echo -e "${YELLOW}커밋되지 않은 변경사항이 있습니다.${NC}"
        read -p "계속하시겠습니까? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 0
        fi
    fi
fi

# Docker 이미지 빌드
echo ""
echo -e "${GREEN}[1/3] Docker 이미지 빌드 중...${NC}"
docker build -t ${FULL_IMAGE_NAME} \
             -t ${FULL_IMAGE_NAME_WITH_TIMESTAMP} \
             -t ${DOCKER_USERNAME}/${IMAGE_NAME}:latest \
             .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 이미지 빌드 완료${NC}"
else
    echo -e "${RED}✗ 이미지 빌드 실패${NC}"
    exit 1
fi

# Docker Hub에 이미지 업로드
echo ""
echo -e "${GREEN}[2/3] Docker Hub에 이미지 업로드 중...${NC}"
docker push ${FULL_IMAGE_NAME_WITH_TIMESTAMP}
docker push ${FULL_IMAGE_NAME}
docker push ${DOCKER_USERNAME}/${IMAGE_NAME}:latest

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 이미지 업로드 완료${NC}"
else
    echo -e "${RED}✗ 이미지 업로드 실패${NC}"
    exit 1
fi

# 로컬 배포 옵션
echo ""
read -p "로컬에서도 배포하시겠습니까? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}[3/3] 로컬 배포 중...${NC}"
    docker-compose down || true
    docker-compose up -d
    echo -e "${GREEN}✓ 로컬 배포 완료${NC}"
    echo "애플리케이션은 http://localhost:2000 에서 실행 중입니다."
fi

echo ""
echo "=========================================="
echo -e "${GREEN}업로드 완료!${NC}"
echo "=========================================="
echo "이미지 정보:"
echo "  - 최신 버전: ${FULL_IMAGE_NAME}"
echo "  - 타임스탬프 버전: ${FULL_IMAGE_NAME_WITH_TIMESTAMP}"
echo "  - Latest 태그: ${DOCKER_USERNAME}/${IMAGE_NAME}:latest"
echo ""
echo "사용 방법:"
echo "  docker pull ${FULL_IMAGE_NAME}"
echo "  docker run -p 2000:2000 ${FULL_IMAGE_NAME}"
echo ""

