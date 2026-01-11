#!/bin/bash

set -e

REGISTRY="wecarmobility"
IMAGE_NAME="wecar-diagnosis"
TAG="latest"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo "=== 위카아라이 진단시스템 Docker Hub 업로드 ==="

# Docker 빌드
echo "1. Docker 이미지 빌드 중..."
docker build -t ${FULL_IMAGE} .

# Docker Hub 로그인 확인
echo "2. Docker Hub 로그인 확인 중..."
if ! docker info 2>/dev/null | grep -q "Username"; then
    echo "Docker Hub에 로그인이 필요합니다."
    echo "Docker Hub 사용자명을 입력해주세요:"
    docker login
else
    echo "이미 로그인되어 있습니다."
fi

# 이미지 푸시
echo "3. Docker Hub에 이미지 푸시 중..."
docker push ${FULL_IMAGE}

echo "=== 업로드 완료 ==="
echo "이미지: ${FULL_IMAGE}"
echo ""
echo "다음 명령어로 이미지를 사용할 수 있습니다:"
echo "  docker pull ${FULL_IMAGE}"
echo "  docker run -p 3010:3010 ${FULL_IMAGE}"
