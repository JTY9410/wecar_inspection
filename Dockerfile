FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 파일 복사
COPY . .

# 포트 노출
EXPOSE 2000

# 환경 변수 설정
ENV FLASK_ENV=production
ENV FLASK_DEBUG=0
ENV PORT=2000

# 데이터베이스 디렉토리 생성
RUN mkdir -p /app/data

# 데이터베이스 초기화 및 애플리케이션 실행
CMD ["sh", "-c", "python database.py && python app.py"]

