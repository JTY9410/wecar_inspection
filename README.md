# 위카아라이 진단시스템

위카모빌리티의 차량 진단 신청 및 평가 시스템입니다.

## 기술 스택

- Python 3.11
- Flask (웹 프레임워크)
- SQLite (데이터베이스)
- Docker (컨테이너화)
- Bootstrap 5 (UI 프레임워크)

## 주요 기능

### 1. 로그인/회원가입
- 사용자 인증 및 권한 관리
- 회원가입 승인 시스템
- 역할별 페이지 자동 이동

### 2. 관리자 페이지
- 회원 관리 (신규추가, 수정, 삭제)
- 진단신청 관리 (확인, 번역, 전송)
- 정산 관리 (월별 정산 내역)

### 3. 진단신청자 페이지
- 진단 신청 (차량번호, 출품번호, 주차번호, 진단신청내역)
- 신청 내역 조회 및 확인

### 4. 평가사 페이지
- 신청 현황 조회 및 평가사 배정
- 평가 답변 입력 및 확인

## 설치 및 실행

### 로컬 개발 환경

1. 의존성 설치:
```bash
pip install -r requirements.txt
```

2. 데이터베이스 초기화:
```bash
python database.py
```

3. 애플리케이션 실행:
```bash
python app.py
```

애플리케이션은 http://localhost:3010 에서 실행됩니다.

### Docker를 사용한 배포

1. 자동 배포 스크립트 실행:
```bash
./auto-deploy.sh
```

또는 수동으로:

2. Docker 이미지 빌드:
```bash
docker build -t wecarmobility/wecar-diagnosis:latest .
```

3. Docker Compose로 실행:
```bash
docker-compose up -d
```

## 기본 계정

- 관리자: `wecar` / `wecar1004`
- 진단신청자: `wecar1` / `1wecar`
- 평가사: `wecar2` / `2wecar`

## 환경 변수

- `PORT`: 애플리케이션 포트 (기본값: 3010)
- `WECAR_DB_DIR`: 데이터베이스 디렉토리 경로
- `FLASK_DEBUG`: 디버그 모드 (0 또는 1)
- `SMTP_SERVER`: 이메일 전송 서버
- `SMTP_USER`: 이메일 계정
- `SMTP_PASSWORD`: 이메일 비밀번호

## 디렉토리 구조

```
wecar_inspection/
├── app.py                 # Flask 애플리케이션
├── database.py            # 데이터베이스 초기화
├── utils.py               # 유틸리티 함수
├── requirements.txt       # Python 의존성
├── Dockerfile            # Docker 이미지 정의
├── docker-compose.yml    # Docker Compose 설정
├── auto-deploy.sh        # 자동 배포 스크립트
├── templates/           # HTML 템플릿
├── static/              # 정적 파일 (CSS, JS, 이미지)
├── data/                # 데이터베이스 파일
└── exports/             # 내보낸 파일 (Excel, PDF)
```

## 모바일/태블릿 최적화

평가사 페이지는 모바일과 태블릿에서 사용하기 쉽도록 반응형 디자인으로 구성되었습니다.

## 라이선스

위카모빌리티 주식회사


