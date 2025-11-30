"""
SQLite 데이터베이스 초기화 및 헬퍼 함수.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_DIR = Path(os.environ.get("WECAR_DB_DIR", BASE_DIR / "data"))
DB_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DB_DIR / "wecar_diagnosis.db"


def get_connection() -> sqlite3.Connection:
    """
    sqlite3 Connection 을 row factory 와 함께 반환한다.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _has_column(cur: sqlite3.Cursor, table: str, column: str) -> bool:
    """
    테이블에 특정 컬럼이 있는지 확인한다.
    """
    cur.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cur.fetchall())


def init_db(seed_demo_data: bool = True) -> None:
    """
    테이블 생성 및 기본 데이터 시드.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript(
        """
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            company TEXT,
            position TEXT,
            name TEXT NOT NULL,
            approved INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS diagnosis_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            applicant_id INTEGER NOT NULL,
            request_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            vehicle_number TEXT,
            lot_number TEXT,
            parking_number TEXT,
            status TEXT NOT NULL DEFAULT '신청',
            evaluator_id INTEGER,
            evaluator_name TEXT,
            answer_date TEXT,
            confirmed_at TEXT,
            translated_summary TEXT,
            translated_at TEXT,
            sent_at TEXT,
            fee INTEGER DEFAULT 120000,
            FOREIGN KEY (applicant_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (evaluator_id) REFERENCES users(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS diagnosis_request_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnosis_id INTEGER NOT NULL,
            sequence INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (diagnosis_id) REFERENCES diagnosis_requests(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS diagnosis_response_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnosis_id INTEGER NOT NULL,
            responder_id INTEGER NOT NULL,
            sequence INTEGER NOT NULL,
            content TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            UNIQUE(diagnosis_id, sequence),
            FOREIGN KEY (diagnosis_id) REFERENCES diagnosis_requests(id) ON DELETE CASCADE,
            FOREIGN KEY (responder_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            title TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        );
        """
    )

    if seed_demo_data:
        _seed_users(cur)

    conn.commit()
    conn.close()


def _seed_users(cur: sqlite3.Cursor) -> None:
    """
    기본 계정이 없으면 생성한다.
    """
    seeds = [
        ("관리자", "wecar", "wecar1004", None, None, "위카모빌리티", "관리자", "관리자"),
        ("진단신청", "wecar1", "1wecar", None, None, "위카모빌리티", "고객", "진단신청자"),
        ("평가사", "wecar2", "2wecar", None, None, "위카모빌리티", "평가사", "평가사1"),
    ]
    for user_type, username, password, email, phone, company, position, name in seeds:
        cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            continue
        cur.execute(
            """
            INSERT INTO users (user_type, username, password_hash, email, phone, company, position, name, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_type,
                username,
                generate_password_hash(password),
                email,
                phone,
                company,
                position,
                name,
                1,
            ),
        )


def list_users() -> Iterable[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users ORDER BY created_at DESC"
        ).fetchall()


def save_settlement_payload(year: int, month: int, title: str, start_date: str, end_date: str, payload: dict) -> int:
    """
    정산 데이터를 저장하고 식별자를 반환한다.
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO settlements (year, month, title, start_date, end_date, payload)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (year, month, title, start_date, end_date, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
        return cur.lastrowid


def fetch_settlement(settlement_id: int) -> Optional[sqlite3.Row]:
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM settlements WHERE id = ?", (settlement_id,)
        ).fetchone()


__all__ = [
    "DB_PATH",
    "get_connection",
    "init_db",
    "list_users",
    "save_settlement_payload",
    "fetch_settlement",
]


