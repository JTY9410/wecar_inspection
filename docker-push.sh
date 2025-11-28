#!/bin/bash

# 위카아라이 검수시스템 Docker Hub 업로드 스크립트

set -e

# Docker Hub 설정 (필요시 수정)
DOCKER_USERNAME="${DOCKER_USERNAME:-your-username}"
IMAGE_NAME="wecar-inspection"
VERSION="${VERSION:-latest}"

FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}:${VERSION}"

echo "=========================================="
echo "위카아라이 검수시스템 Docker Hub 업로드"
echo "=========================================="
echo "이미지 이름: ${FULL_IMAGE_NAME}"
echo ""

# Docker Hub 로그인 확인
if ! docker info | grep -q "Username"; then
    echo "Docker Hub에 로그인이 필요합니다."
    echo "다음 명령어로 로그인하세요: docker login"
    read -p "지금 로그인하시겠습니까? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        docker login
    else
        echo "로그인을 취소했습니다."
        exit 1
    fi
fi

# Docker 이미지 빌드
echo "Docker 이미지 빌드 중..."
docker build -t ${FULL_IMAGE_NAME} -t ${DOCKER_USERNAME}/${IMAGE_NAME}:latest .

# 이미지 푸시
echo "Docker Hub에 이미지 업로드 중..."
docker push ${FULL_IMAGE_NAME}
docker push ${DOCKER_USERNAME}/${IMAGE_NAME}:latest

echo ""
echo "=========================================="
echo "업로드 완료!"
echo "이미지: ${FULL_IMAGE_NAME}"
echo "=========================================="
echo ""
echo "다음 명령어로 이미지를 사용할 수 있습니다:"
echo "  docker pull ${FULL_IMAGE_NAME}"
echo "  docker run -p 2000:2000 ${FULL_IMAGE_NAME}"

