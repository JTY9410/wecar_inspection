# 위카아라이 검수시스템

위카아라이 검수시스템은 검수신청, 평가사 평가, 관리자 관리를 위한 웹 기반 시스템입니다.

## 기술 스택

- Python 3.11
- Flask (웹 프레임워크)
- SQLite (데이터베이스)
- Docker (컨테이너화)
- HTML/CSS/JavaScript (프론트엔드)
- Bootstrap 5 (UI 프레임워크)

## 주요 기능

### 1. 로그인/회원가입
- 사용자 타입별 로그인 (검수신청, 평가사, 관리자)
- 회원가입 및 관리자 승인 시스템

### 2. 관리자 페이지
- 회원관리: 회원 정보 수정, 삭제, 승인
- 검수신청관리: 검수신청 확인, 번역, 전송
- 정산관리: 평가사별 정산 내역 관리

### 3. 검수신청 페이지
- 검수신청 등록
- 검수신청 내역 조회

### 4. 평가사 페이지
- 신청현황: 평가사 배정 및 완료 처리
- 평가답변: 검수신청에 대한 평가답변 작성

## 설치 및 실행

### 로컬 환경

1. Python 3.11 설치
2. 의존성 패키지 설치:
```bash
pip install -r requirements.txt
```

3. 데이터베이스 초기화:
```bash
python database.py
```

4. 애플리케이션 실행:
```bash
python app.py
```

5. 브라우저에서 접속:
```
http://localhost:5000
```

### Docker 사용

1. Docker 이미지 빌드 및 실행:
```bash
docker-compose up -d
```

2. 브라우저에서 접속:
```
http://localhost:5000
```

## 기본 계정

### 관리자
- 아이디: `wecar`
- 비밀번호: `wecar1004`

### 테스트 계정
- 검수신청: `wecar1` / `1wecar`
- 평가사: `wecar2` / `2wecar`

## 프로젝트 구조

```
wecar_inspection/
├── app.py                 # Flask 메인 애플리케이션
├── database.py            # 데이터베이스 초기화 및 모델
├── utils.py              # 유틸리티 함수 (엑셀, PDF, 번역)
├── requirements.txt       # Python 패키지 의존성
├── Dockerfile            # Docker 이미지 설정
├── docker-compose.yml    # Docker Compose 설정
├── templates/            # HTML 템플릿
│   ├── admin/           # 관리자 페이지 템플릿
│   ├── inspection/     # 검수신청 페이지 템플릿
│   └── evaluator/       # 평가사 페이지 템플릿
└── static/              # 정적 파일
    ├── css/             # CSS 파일
    ├── js/              # JavaScript 파일
    └── images/          # 이미지 파일
```

## 주요 기능 상세

### 검수신청 프로세스
1. 검수신청자가 검수신청 등록
2. 관리자가 검수신청 확인
3. 평가사 배정
4. 평가사가 평가답변 작성
5. 관리자가 답변 확인 및 번역
6. 결과 전송

### 정산 프로세스
1. 관리자가 기간별 정산 조회
2. 평가사별 건수 및 금액 계산
3. VAT(10%) 계산
4. 정산내역 저장 및 내보내기

## 라이선스

이 프로젝트는 위카모빌리티 주식회사의 내부 시스템입니다.





