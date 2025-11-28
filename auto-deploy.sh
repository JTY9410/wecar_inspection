#!/bin/bash
# 파일 변경 감지 및 자동 배포 스크립트 (향상된 버전)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "위카아라이 검수시스템 자동 배포 모니터링"
echo "포트: 2000"
echo "파일 변경 시 자동으로 Docker에 업로드됩니다."
echo "종료하려면 Ctrl+C를 누르세요."
echo "=========================================="

# 초기 배포
echo "초기 배포 실행 중..."
./deploy.sh

# 파일 변경 감지 및 자동 배포
if command -v fswatch &> /dev/null; then
    # macOS용 fswatch
    echo "파일 변경 감지 시작 (fswatch 사용)..."
    fswatch -o . --exclude='(__pycache__|\.pyc|\.db|\.xlsx|\.pdf|\.git|data/)' | while read f; do
        echo ""
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 파일 변경 감지됨. 자동 배포 시작..."
        ./deploy.sh
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 자동 배포 완료. 계속 모니터링 중..."
    done
elif command -v inotifywait &> /dev/null; then
    # Linux용 inotifywait
    echo "파일 변경 감지 시작 (inotifywait 사용)..."
    while true; do
        inotifywait -r -e modify,create,delete,move \
            --exclude '(__pycache__|\.pyc|\.db|\.xlsx|\.pdf|\.git|data/)' \
            . 2>/dev/null || true
        
        echo ""
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 파일 변경 감지됨. 자동 배포 시작..."
        ./deploy.sh
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 자동 배포 완료. 계속 모니터링 중..."
    done
else
    echo "경고: 파일 변경 감지 도구가 설치되어 있지 않습니다."
    echo ""
    echo "자동 배포를 사용하려면 다음 중 하나를 설치하세요:"
    echo "  - Linux: sudo apt-get install inotify-tools"
    echo "  - macOS: brew install fswatch"
    echo ""
    echo "수동 배포를 계속 사용할 수 있습니다: ./deploy.sh"
    echo ""
    echo "현재 상태:"
    docker-compose ps
    exit 1
fi





