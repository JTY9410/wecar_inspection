"""
데이터베이스 초기화 및 모델 정의
"""
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os

# Docker 환경에서는 /app/data 디렉토리 사용, 로컬에서는 현재 디렉토리 사용
if os.path.exists('/app/data'):
    DB_PATH = '/app/data/wecar_inspection.db'
else:
    # 로컬에서는 data 디렉토리 사용 (존재하지 않으면 생성)
    if os.path.exists('data'):
        DB_PATH = 'data/wecar_inspection.db'
    else:
        DB_PATH = 'wecar_inspection.db'

def get_db_connection():
    """데이터베이스 연결 반환"""
    # 데이터베이스 디렉토리가 없으면 생성
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """데이터베이스 초기화 및 테이블 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 사용자 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL CHECK(user_type IN ('검수신청', '평가사', '관리자')),
            company TEXT,
            position TEXT,
            name TEXT NOT NULL,
            approved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 검수신청 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inspection_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vehicle_number TEXT NOT NULL,
            lot_number TEXT,
            parking_number TEXT,
            request_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT '신청',
            sent_date TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 검수신청 상세내역 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inspection_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            sequence INTEGER NOT NULL,
            content TEXT NOT NULL,
            FOREIGN KEY (request_id) REFERENCES inspection_requests(id) ON DELETE CASCADE
        )
    ''')
    
    # 평가사 배정 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            evaluator_id INTEGER NOT NULL,
            assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT '신청' CHECK(status IN ('신청', '평가사배정', '평가완료')),
            FOREIGN KEY (request_id) REFERENCES inspection_requests(id) ON DELETE CASCADE,
            FOREIGN KEY (evaluator_id) REFERENCES users(id)
        )
    ''')
    
    # 평가답변 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            evaluator_id INTEGER NOT NULL,
            response_date TIMESTAMP,
            confirmed INTEGER DEFAULT 0,
            sent_date TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES inspection_requests(id) ON DELETE CASCADE,
            FOREIGN KEY (evaluator_id) REFERENCES users(id)
        )
    ''')
    
    # 평가답변 상세내역 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evaluation_response_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            response_id INTEGER NOT NULL,
            sequence INTEGER NOT NULL,
            content TEXT NOT NULL,
            note TEXT,
            FOREIGN KEY (response_id) REFERENCES evaluation_responses(id) ON DELETE CASCADE
        )
    ''')
    
    # 정산관리 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            settlement_date DATE NOT NULL,
            evaluator_id INTEGER NOT NULL,
            count INTEGER DEFAULT 0,
            amount INTEGER DEFAULT 0,
            vat INTEGER DEFAULT 0,
            total_amount INTEGER DEFAULT 0,
            FOREIGN KEY (evaluator_id) REFERENCES users(id)
        )
    ''')
    
    # 저장된 정산내역 테이블
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS saved_settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    # 기본 관리자 계정 생성
    admin_password = generate_password_hash('wecar1004')
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, user_type, name, approved)
        VALUES (?, ?, ?, ?, ?)
    ''', ('wecar', admin_password, '관리자', '관리자', 1))
    
    # 테스트 계정 생성
    test1_password = generate_password_hash('1wecar')
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, user_type, name, approved)
        VALUES (?, ?, ?, ?, ?)
    ''', ('wecar1', test1_password, '검수신청', '테스트1', 1))
    
    test2_password = generate_password_hash('2wecar')
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, user_type, name, approved)
        VALUES (?, ?, ?, ?, ?)
    ''', ('wecar2', test2_password, '평가사', '테스트2', 1))
    
    conn.commit()
    conn.close()
    print("데이터베이스 초기화 완료")

if __name__ == '__main__':
    init_db()

