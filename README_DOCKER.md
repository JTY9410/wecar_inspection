# Docker 배포 가이드

## 빠른 시작

### 1. 초기 배포

```bash
# 배포 스크립트에 실행 권한 부여
chmod +x deploy.sh auto-deploy.sh

# Docker 배포 실행
./deploy.sh
```

애플리케이션이 **http://localhost:2000** 에서 실행됩니다.

### 2. 자동 배포 (파일 변경 감지)

```bash
# 파일 변경 시 자동으로 Docker에 업로드
./auto-deploy.sh
```

이 스크립트는 파일 변경을 감지하고 자동으로 Docker 컨테이너를 재배포합니다.

## Docker 명령어

### 컨테이너 시작
```bash
docker-compose up -d
```

### 컨테이너 중지
```bash
docker-compose down
```

### 로그 확인
```bash
docker-compose logs -f
```

### 컨테이너 재시작
```bash
docker-compose restart
```

### 이미지 재빌드
```bash
docker-compose build --no-cache
docker-compose up -d
```

## 포트 설정

- **애플리케이션 포트: 2000**
- 접속 URL: **http://localhost:2000**

포트를 변경하려면:
1. `docker-compose.yml`의 `ports` 섹션 수정
2. `app.py`의 포트 설정 수정
3. `Dockerfile`의 `EXPOSE` 포트 수정

## 자동 배포 시스템

### 방법 1: 파일 변경 감지 (권장)
```bash
./auto-deploy.sh
```

이 스크립트는 파일 변경을 감지하고 자동으로 배포합니다.

### 방법 2: Git Hook (커밋 시 자동 배포)
Git commit 후 자동으로 배포하려면 `.git/hooks/post-commit`이 활성화되어 있습니다.

### 방법 3: 수동 배포
```bash
./deploy.sh
```

## 자동 배포 도구 설치

### Linux (inotifywait)
```bash
sudo apt-get install inotify-tools
```

### macOS (fswatch)
```bash
brew install fswatch
```

## 문제 해결

### 포트가 이미 사용 중인 경우
```bash
# 포트 2000을 사용하는 프로세스 확인
lsof -i :2000

# 프로세스 종료 후 재시작
docker-compose down
docker-compose up -d
```

### 데이터베이스 초기화
```bash
# 데이터베이스 파일 삭제 후 재시작
rm -rf data/wecar_inspection.db
docker-compose down
docker-compose up -d
```

### 컨테이너 로그 확인
```bash
docker-compose logs wecar-inspection
```

### 컨테이너 상태 확인
```bash
docker-compose ps
```

## 환경 변수

`docker-compose.yml`에서 다음 환경 변수를 설정할 수 있습니다:

- `FLASK_ENV`: Flask 환경 (production/development)
- `FLASK_DEBUG`: 디버그 모드 (0/1)
- `PORT`: 애플리케이션 포트 (기본값: 2000)

## 볼륨 마운트

다음 디렉토리가 볼륨으로 마운트되어 실시간 반영됩니다:

- `/app`: 전체 애플리케이션 코드
- `/app/data`: 데이터베이스 파일 저장 디렉토리
- `/app/static`: 정적 파일
- `/app/templates`: 템플릿 파일

코드 변경 시 컨테이너를 재시작하면 변경사항이 반영됩니다.

## 기본 계정

- 관리자: `wecar` / `wecar1004`
- 검수신청: `wecar1` / `1wecar`
- 평가사: `wecar2` / `2wecar`

## 접속 정보

- URL: http://localhost:2000
- 포트: 2000

## Docker Hub 업로드

프로그램이 수정되면 Docker Hub에 자동으로 업로드할 수 있습니다.

### 빠른 사용법

```bash
# Docker Hub 업로드
./docker-update.sh
```

첫 실행 시 Docker Hub 사용자명을 입력하면 자동으로 저장됩니다.

### 자동 업로드 설정

Git 커밋 시 자동으로 Docker Hub에 업로드하려면:

```bash
# Git hook 활성화 (이미 설정되어 있음)
chmod +x .git/hooks/post-commit
```

이제 커밋할 때마다 자동으로 Docker 이미지가 빌드되고 업로드됩니다.

자세한 내용은 [DOCKER_UPLOAD.md](./DOCKER_UPLOAD.md)를 참조하세요.
