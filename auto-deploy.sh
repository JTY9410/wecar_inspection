#!/bin/bash

set -e

REGISTRY="wecarmobility"
IMAGE_NAME="wecar-diagnosis"
TAG="latest"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo "=== 위카아라이 진단시스템 Docker 자동 배포 ==="

# Docker 빌드
echo "1. Docker 이미지 빌드 중..."
docker build -t ${FULL_IMAGE} .

# Docker 레지스트리 로그인 확인
echo "2. Docker 레지스트리 로그인 확인 중..."
if ! docker info | grep -q "Username"; then
    echo "Docker 레지스트리에 로그인해주세요:"
    docker login
fi

# 이미지 푸시
echo "3. Docker 이미지 푸시 중..."
docker push ${FULL_IMAGE}

# 기존 컨테이너 중지 및 제거
echo "4. 기존 컨테이너 중지 및 제거 중..."
docker-compose down || true

# 최신 이미지 풀
echo "5. 최신 이미지 풀 중..."
docker pull ${FULL_IMAGE}

# 컨테이너 시작
echo "6. 컨테이너 시작 중..."
docker-compose up -d

echo "=== 배포 완료 ==="
echo "애플리케이션은 http://localhost:3010 에서 실행됩니다."
echo "로그 확인: docker-compose logs -f"



