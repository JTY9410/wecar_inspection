#!/bin/bash

# Docker Hub 업로드 간편 스크립트
# 사용법: ./docker-upload.sh [DOCKER_USERNAME]

set -e

DOCKER_USERNAME="${1:-${DOCKER_USERNAME}}"

if [ -z "$DOCKER_USERNAME" ]; then
    echo "=========================================="
    echo "Docker Hub 업로드"
    echo "=========================================="
    echo ""
    echo "사용법: ./docker-upload.sh [DOCKER_USERNAME]"
    echo ""
    echo "예시:"
    echo "  ./docker-upload.sh myusername"
    echo ""
    echo "또는 환경 변수로 설정:"
    echo "  export DOCKER_USERNAME=myusername"
    echo "  ./docker-upload.sh"
    echo ""
    exit 1
fi

# docker-update.sh 실행
./docker-update.sh "$DOCKER_USERNAME"

