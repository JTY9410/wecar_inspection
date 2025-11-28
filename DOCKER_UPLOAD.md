# Docker 업로드 가이드

프로그램이 수정되면 Docker Hub에 자동으로 업로드하는 방법입니다.

## 빠른 시작

### 1. 기본 사용법

```bash
# Docker Hub 업로드 스크립트 실행
./docker-update.sh
```

첫 실행 시 Docker Hub 사용자명을 입력하면 `.docker-config` 파일에 저장되어 다음부터는 자동으로 사용됩니다.

### 2. 환경 변수로 설정

```bash
# Docker Hub 사용자명 설정
export DOCKER_USERNAME=your-username

# 버전 태그 설정 (선택사항)
export VERSION=v1.0.0

# 업로드 실행
./docker-update.sh
```

### 3. 설정 파일 사용

`.docker-config` 파일을 직접 생성할 수도 있습니다:

```bash
echo "DOCKER_USERNAME=your-username" > .docker-config
echo "VERSION=latest" >> .docker-config
```

## 스크립트 설명

### docker-update.sh

프로그램이 수정되면 다음 작업을 수행합니다:

1. **변경사항 확인**: Git 저장소의 변경사항 확인
2. **Docker 이미지 빌드**: 최신 코드로 이미지 빌드
3. **Docker Hub 업로드**: 
   - `latest` 태그
   - 타임스탬프 태그 (예: `20241201_143022`)
   - 지정한 버전 태그
4. **로컬 배포** (선택사항): 로컬에서도 배포할지 선택

### docker-push.sh

기존 Docker Hub 업로드 스크립트 (수동 실행용)

```bash
./docker-push.sh
```

## 자동 업로드 설정

### Git Hook 사용 (커밋 시 자동 업로드)

Git 커밋 후 자동으로 Docker에 업로드하려면:

```bash
# Git hook 활성화
chmod +x .git/hooks/post-commit
```

커밋할 때마다 자동으로 Docker 이미지가 빌드되고 업로드됩니다.

**주의**: 이 기능을 비활성화하려면 `.git/hooks/post-commit` 파일을 삭제하거나 이름을 변경하세요.

### 파일 변경 감지 (watch 모드)

파일 변경을 감지하여 자동으로 업로드하려면:

```bash
# macOS
brew install fswatch

# Linux
sudo apt-get install inotify-tools

# watch 스크립트 실행 (별도 구현 필요)
```

## Docker Hub 이미지 사용

업로드된 이미지를 사용하려면:

```bash
# 이미지 다운로드
docker pull your-username/wecar-inspection:latest

# 컨테이너 실행
docker run -d -p 2000:2000 \
  -v $(pwd)/data:/app/data \
  your-username/wecar-inspection:latest
```

또는 `docker-compose.yml`에서:

```yaml
services:
  wecar-inspection:
    image: your-username/wecar-inspection:latest
    ports:
      - "2000:2000"
    volumes:
      - ./data:/app/data
```

## 문제 해결

### Docker Hub 로그인 실패

```bash
# 수동 로그인
docker login

# 로그인 정보 확인
docker info | grep Username
```

### 이미지 빌드 실패

```bash
# 빌드 로그 확인
docker build -t test-image . 2>&1 | tee build.log

# Dockerfile 확인
cat Dockerfile
```

### 업로드 권한 오류

Docker Hub에서 해당 레포지토리에 대한 쓰기 권한이 있는지 확인하세요.

## 업로드된 이미지 확인

```bash
# Docker Hub에서 확인
# https://hub.docker.com/r/your-username/wecar-inspection

# 로컬 이미지 확인
docker images | grep wecar-inspection

# 이미지 태그 확인
docker images your-username/wecar-inspection
```

## 버전 관리

타임스탬프 버전과 함께 업로드되므로, 특정 시점의 이미지를 사용할 수 있습니다:

```bash
# 타임스탬프 버전 사용
docker pull your-username/wecar-inspection:20241201_143022

# 특정 버전 사용
export VERSION=v1.0.0
./docker-update.sh
docker pull your-username/wecar-inspection:v1.0.0
```

## 주의사항

1. **Docker Hub 제한**: 무료 계정은 일일 업로드 제한이 있습니다.
2. **자동 업로드**: Git hook을 사용하면 커밋할 때마다 자동으로 업로드됩니다.
3. **비용**: Docker Hub의 프라이빗 레포지토리는 유료입니다.
4. **보안**: `.docker-config` 파일에는 민감한 정보가 포함될 수 있으므로 Git에 커밋하지 마세요.

## 설정 파일 예시

`.docker-config`:
```bash
DOCKER_USERNAME=myusername
VERSION=latest
```

`.gitignore`에 추가:
```
.docker-config
```

