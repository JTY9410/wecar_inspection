#!/bin/bash

# 위카아라이 검수시스템 Docker 배포 스크립트

set -e

echo "=========================================="
echo "위카아라이 검수시스템 Docker 배포 시작"
echo "=========================================="

# 기존 컨테이너 중지 및 제거
echo "기존 컨테이너 중지 중..."
docker-compose down || true

# 이미지 빌드
echo "Docker 이미지 빌드 중..."
docker-compose build --no-cache

# 컨테이너 시작
echo "컨테이너 시작 중..."
docker-compose up -d

# 컨테이너 상태 확인
echo "컨테이너 상태 확인 중..."
sleep 5
docker-compose ps

echo "=========================================="
echo "배포 완료!"
echo "애플리케이션은 http://localhost:2000 에서 실행 중입니다."
echo "=========================================="

# 로그 확인
echo ""
echo "로그를 확인하려면: docker-compose logs -f"
echo "컨테이너 중지하려면: docker-compose down"





