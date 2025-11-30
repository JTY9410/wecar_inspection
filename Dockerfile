FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY . .

# 데이터 디렉토리 생성
RUN mkdir -p /app/data /app/exports

# 환경 변수 설정
ENV FLASK_APP=app.py
ENV PORT=3010
ENV WECAR_DB_DIR=/app/data

# 포트 노출
EXPOSE 3010

# 데이터베이스 초기화 및 애플리케이션 실행
CMD python database.py && python app.py


