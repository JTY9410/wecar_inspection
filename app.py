from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import (
    Flask,
    abort,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from database import DB_PATH, fetch_settlement, init_db, list_users, save_settlement_payload
from utils import export_to_excel, export_to_pdf, format_datetime, send_email, translate_to_japanese

BASE_DIR = Path(__file__).resolve().parent
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

init_db()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("WECAR_SECRET_KEY", "wecar-dev-secret")
app.permanent_session_lifetime = timedelta(hours=6)

DEFAULT_REQUEST_ITEMS = [
    "외관 점검 내역",
    "실내 및 전장 점검 내역",
    "엔진/동력계 점검 내역",
    "하부/프레임 점검 내역",
    "기타 요청사항",
]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_: Optional[BaseException]) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def login_required(func):
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return func(*args, **kwargs)

    return wrapper


def role_required(*roles):
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if "user_type" not in session or session["user_type"] not in roles:
                abort(403)
            return func(*args, **kwargs)

        return wrapper

    return decorator


def current_user() -> Optional[sqlite3.Row]:
    if "user_id" not in session:
        return None
    if hasattr(g, "current_user"):
        return g.current_user
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    g.current_user = row
    return row


def _resolve_redirect(user_type: str) -> str:
    mapping = {
        "관리자": "admin_dashboard",
        "진단신청": "diagnosis_dashboard",
        "평가사": "evaluator_dashboard",
    }
    route = mapping.get(user_type, "login")
    return url_for(route)


def _parse_date_range(default_days: int = 7) -> Tuple[Optional[str], Optional[str]]:
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    if not start_date or not end_date:
        today = datetime.now().date()
        start = today - timedelta(days=default_days)
        start_date = start.isoformat()
        end_date = today.isoformat()
    return start_date, end_date


def _fetch_diagnosis(diagnosis_id: int) -> Optional[sqlite3.Row]:
    db = get_db()
    return db.execute(
        """
        SELECT dr.*, applicant.name AS applicant_name, evaluator.name AS evaluator_name
        FROM diagnosis_requests dr
        JOIN users AS applicant ON applicant.id = dr.applicant_id
        LEFT JOIN users AS evaluator ON evaluator.id = dr.evaluator_id
        WHERE dr.id = ?
        """,
        (diagnosis_id,),
    ).fetchone()


def _fetch_request_details(diagnosis_id: int) -> List[sqlite3.Row]:
    db = get_db()
    return db.execute(
        """
        SELECT * FROM diagnosis_request_items
        WHERE diagnosis_id = ?
        ORDER BY sequence ASC
        LIMIT 5
        """,
        (diagnosis_id,),
    ).fetchall()


def _fetch_response_details(diagnosis_id: int) -> List[sqlite3.Row]:
    db = get_db()
    return db.execute(
        """
        SELECT d.*, u.name AS responder_name
        FROM diagnosis_response_details d
        JOIN users u ON u.id = d.responder_id
        WHERE d.diagnosis_id = ?
        ORDER BY sequence ASC
        """,
        (diagnosis_id,),
    ).fetchall()


def _summarize_details(rows: Iterable[sqlite3.Row], field: str) -> str:
    parts: List[str] = []
    for row in rows:
        value = row[field]
        if not value:
            continue
        parts.append(value.strip())
    return "/".join(parts[:5])


@app.route("/")
def index():
    """루트 경로: 로그인되지 않은 사용자는 로그인 페이지로, 로그인된 사용자는 역할별 대시보드로"""
    if "user_id" not in session:
        return redirect(url_for("login"))
    return redirect(_resolve_redirect(session.get("user_type", "")))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()

    if not username or not password:
        return jsonify(success=False, message="아이디와 비밀번호를 입력해주세요.")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(success=False, message="아이디 또는 비밀번호가 올바르지 않습니다.")

    if not user["approved"]:
        return jsonify(
            success=False,
            message="회원가입승인이 미완료 되었습니다 완료후 이용하여주세요",
        )

    session.permanent = True
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["user_type"] = user["user_type"]
    session["name"] = user["name"]

    return jsonify(success=True, redirect=_resolve_redirect(user["user_type"]))


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    user_type = data.get("user_type", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    password_confirm = data.get("password_confirm", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    company = data.get("company", "").strip()
    position = data.get("position", "").strip()
    name = data.get("name", "").strip()

    if not user_type or user_type not in ("진단신청", "평가사"):
        return jsonify(success=False, message="회원가입구분을 선택해주세요.")
    if not username:
        return jsonify(success=False, message="아이디를 입력해주세요.")
    if not password or password != password_confirm:
        return jsonify(success=False, message="비밀번호가 일치하지 않습니다.")
    if not name:
        return jsonify(success=False, message="이름을 입력해주세요.")

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        return jsonify(success=False, message="이미 사용 중인 아이디입니다.")

    db.execute(
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
            0,
        ),
    )
    db.commit()

    return jsonify(success=True, message="회원가입 신청이 완료되었습니다. 관리자 승인 후 이용 가능합니다.")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ------------------- 관리자 영역 ------------------- #


@app.route("/admin/dashboard")
@login_required
@role_required("관리자")
def admin_dashboard():
    return render_template("admin/dashboard.html")


@app.route("/admin/users")
@login_required
@role_required("관리자")
def admin_users():
    users = list(list_users())
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/create", methods=["POST"])
@login_required
@role_required("관리자")
def admin_users_create():
    data = request.get_json()
    user_type = data.get("user_type", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    password_confirm = data.get("password_confirm", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    company = data.get("company", "").strip()
    position = data.get("position", "").strip()
    name = data.get("name", "").strip()

    if not user_type or user_type not in ("진단신청", "평가사", "관리자"):
        return jsonify(success=False, message="회원가입구분을 선택해주세요.")
    if not username:
        return jsonify(success=False, message="아이디를 입력해주세요.")
    if not password or password != password_confirm:
        return jsonify(success=False, message="비밀번호가 일치하지 않습니다.")
    if not name:
        return jsonify(success=False, message="이름을 입력해주세요.")

    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        return jsonify(success=False, message="이미 사용 중인 아이디입니다.")

    db.execute(
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
    db.commit()

    return jsonify(success=True)


@app.route("/admin/users/update", methods=["POST"])
@login_required
@role_required("관리자")
def admin_users_update():
    data = request.get_json()
    user_id = data.get("id")
    if not user_id:
        return jsonify(success=False, message="잘못된 요청입니다.")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify(success=False, message="사용자를 찾을 수 없습니다.")

    user_type = data.get("user_type", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    password_confirm = data.get("password_confirm", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    company = data.get("company", "").strip()
    position = data.get("position", "").strip()
    name = data.get("name", "").strip()
    approved = data.get("approved", False)

    if password and password != password_confirm:
        return jsonify(success=False, message="비밀번호가 일치하지 않습니다.")

    update_fields = []
    params = []

    if user_type:
        update_fields.append("user_type = ?")
        params.append(user_type)
    if username and username != user["username"]:
        existing = db.execute("SELECT 1 FROM users WHERE username = ? AND id != ?", (username, user_id)).fetchone()
        if existing:
            return jsonify(success=False, message="이미 사용 중인 아이디입니다.")
        update_fields.append("username = ?")
        params.append(username)
    if password:
        update_fields.append("password_hash = ?")
        params.append(generate_password_hash(password))
    if email is not None:
        update_fields.append("email = ?")
        params.append(email)
    if phone is not None:
        update_fields.append("phone = ?")
        params.append(phone)
    if company is not None:
        update_fields.append("company = ?")
        params.append(company)
    if position is not None:
        update_fields.append("position = ?")
        params.append(position)
    if name:
        update_fields.append("name = ?")
        params.append(name)
    if approved is not None:
        update_fields.append("approved = ?")
        params.append(1 if approved else 0)

    if update_fields:
        params.append(user_id)
        db.execute(
            f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?",
            params,
        )
        db.commit()

    return jsonify(success=True)


@app.route("/admin/users/delete", methods=["POST"])
@login_required
@role_required("관리자")
def admin_users_delete():
    data = request.get_json()
    user_id = data.get("id")
    if not user_id:
        return jsonify(success=False, message="잘못된 요청입니다.")
    if user_id == session.get("user_id"):
        return jsonify(success=False, message="본인 계정은 삭제할 수 없습니다.")
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    return jsonify(success=True)


def _filter_clause(date_field: str = "request_date") -> Tuple[str, List[Any]]:
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    clauses = []
    params: List[Any] = []
    if start_date:
        clauses.append(f"date({date_field}) >= date(?)")
        params.append(start_date)
    if end_date:
        clauses.append(f"date({date_field}) <= date(?)")
        params.append(end_date)
    clause = ""
    if clauses:
        clause = " AND " + " AND ".join(clauses)
    return clause, params


@app.route("/admin/diagnosis")
@login_required
@role_required("관리자")
def admin_diagnosis():
    clause, params = _filter_clause("dr.request_date")
    db = get_db()
    rows = db.execute(
        f"""
        SELECT dr.*, applicant.name AS applicant_name, evaluator.name AS evaluator_name
        FROM diagnosis_requests dr
        JOIN users applicant ON applicant.id = dr.applicant_id
        LEFT JOIN users evaluator ON evaluator.id = dr.evaluator_id
        WHERE 1=1 {clause}
        ORDER BY dr.request_date DESC
        """,
        params,
    ).fetchall()

    enriched = []
    for row in rows:
        details = _fetch_request_details(row["id"])
        responses = _fetch_response_details(row["id"])
        enriched.append(
            {
                "row": row,
                "request_summary": _summarize_details(details, "content"),
                "response_summary": _summarize_details(responses, "content"),
            }
        )

    # 평가사 목록 가져오기
    evaluators = db.execute(
        "SELECT id, name, email FROM users WHERE user_type = '평가사' ORDER BY name"
    ).fetchall()

    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    return render_template(
        "admin/diagnosis.html",
        diagnoses=enriched,
        evaluators=evaluators,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/admin/diagnosis/<int:diagnosis_id>")
@login_required
@role_required("관리자")
def admin_diagnosis_details(diagnosis_id: int):
    diagnosis = _fetch_diagnosis(diagnosis_id)
    if not diagnosis:
        abort(404)
    details = _fetch_request_details(diagnosis_id)
    responses = _fetch_response_details(diagnosis_id)
    return render_template(
        "admin/diagnosis_details.html",
        diagnosis=diagnosis,
        request_details=details,
        response_details=responses,
    )


@app.route("/admin/diagnosis/<int:diagnosis_id>/json")
@login_required
def admin_diagnosis_details_json(diagnosis_id: int):
    """진단신청 상세 정보를 JSON으로 반환 (관리자 및 본인 신청건만 접근 가능)"""
    diagnosis = _fetch_diagnosis(diagnosis_id)
    if not diagnosis:
        return jsonify(success=False, message="진단신청을 찾을 수 없습니다."), 404
    
    # 권한 체크: 관리자이거나 본인이 신청한 건만 접근 가능
    user = current_user()
    if user["user_type"] != "관리자" and diagnosis["applicant_id"] != user["id"]:
        return jsonify(success=False, message="접근 권한이 없습니다."), 403
    
    details = _fetch_request_details(diagnosis_id)
    responses = _fetch_response_details(diagnosis_id)
    
    # 응답을 시퀀스별로 매핑
    response_map = {resp["sequence"]: resp for resp in responses}
    
    # 테이블 데이터 구성
    table_data = []
    for detail in details:
        resp = response_map.get(detail["sequence"])
        table_data.append({
            "sequence": detail["sequence"],
            "request_content": detail["content"],
            "response_content": resp["content"] if resp else "",
            "note": resp["note"] if resp else "",
        })
    
    return jsonify(
        success=True,
        diagnosis={
            "id": diagnosis["id"],
            "request_date": diagnosis["request_date"],
            "vehicle_number": diagnosis["vehicle_number"] or "",
            "lot_number": diagnosis["lot_number"] or "",
            "parking_number": diagnosis["parking_number"] or "",
            "evaluator_name": diagnosis["evaluator_name"] or "",
            "status": diagnosis["status"],
            "confirmed_at": diagnosis["confirmed_at"] or "",
        },
        table_data=table_data,
    )


@app.route("/admin/diagnosis/<int:diagnosis_id>/confirm", methods=["POST"])
@login_required
@role_required("관리자")
def admin_diagnosis_confirm(diagnosis_id: int):
    if not _fetch_diagnosis(diagnosis_id):
        abort(404)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db = get_db()
    db.execute(
        "UPDATE diagnosis_requests SET confirmed_at = ? WHERE id = ?",
        (now, diagnosis_id),
    )
    db.commit()
    return jsonify(success=True, confirmed_at=now)


@app.route("/admin/diagnosis/<int:diagnosis_id>/translate")
@login_required
@role_required("관리자")
def admin_diagnosis_translate(diagnosis_id: int):
    diagnosis = _fetch_diagnosis(diagnosis_id)
    if not diagnosis:
        abort(404)
    details = _fetch_request_details(diagnosis_id)
    responses = _fetch_response_details(diagnosis_id)

    # 헤더 정보 번역 (sqlite3.Row는 딕셔너리처럼 접근)
    header_translations = {}
    vehicle_number = diagnosis['vehicle_number'] if diagnosis['vehicle_number'] else None
    lot_number = diagnosis['lot_number'] if diagnosis['lot_number'] else None
    parking_number = diagnosis['parking_number'] if diagnosis['parking_number'] else None
    evaluator_name = diagnosis['evaluator_name'] if diagnosis['evaluator_name'] else None
    
    if vehicle_number:
        header_translations['vehicle_number'] = translate_to_japanese(f"차량번호: {vehicle_number}")
    if lot_number:
        header_translations['lot_number'] = translate_to_japanese(f"출품번호: {lot_number}")
    if parking_number:
        header_translations['parking_number'] = translate_to_japanese(f"주차번호: {parking_number}")
    if evaluator_name:
        header_translations['evaluator_name'] = translate_to_japanese(f"평가사명: {evaluator_name}")

    # 표 형식으로 번역 데이터 구성
    translated_table_data = []
    response_map = {resp['sequence']: resp for resp in responses}
    
    for detail in details:
        resp = response_map.get(detail['sequence'])
        # 각 항목 번역
        translated_request = translate_to_japanese(detail['content']) if detail['content'] else ""
        translated_response = translate_to_japanese(resp['content']) if resp and resp['content'] else ""
        translated_note = translate_to_japanese(resp['note']) if resp and resp['note'] else ""
        
        translated_table_data.append({
            'sequence': detail['sequence'],
            'request_content': translated_request,
            'response_content': translated_response,
            'note': translated_note,
        })

    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 번역된 내용을 저장 (표 형식 유지를 위해 JSON 형태로 저장)
    translated_data = {
        'headers': header_translations,
        'table_data': translated_table_data,
    }
    translated_summary = json.dumps(translated_data, ensure_ascii=False)
    
    db.execute(
        """
        UPDATE diagnosis_requests
        SET translated_summary = ?, translated_at = ?
        WHERE id = ?
        """,
        (translated_summary, now, diagnosis_id),
    )
    db.commit()

    return render_template(
        "admin/diagnosis_translate.html",
        diagnosis=diagnosis,
        translated_headers=header_translations,
        translated_table_data=translated_table_data,
        generated_at=now,
    )


@app.route("/admin/diagnosis/<int:diagnosis_id>/send", methods=["POST"])
@login_required
@role_required("관리자")
def admin_diagnosis_send(diagnosis_id: int):
    diagnosis = _fetch_diagnosis(diagnosis_id)
    if not diagnosis:
        abort(404)

    db = get_db()
    applicant = db.execute("SELECT * FROM users WHERE id = ?", (diagnosis["applicant_id"],)).fetchone()
    if not applicant or not applicant["email"]:
        return jsonify(success=False, message="회원의 이메일 주소가 없습니다.")

    translated_summary = diagnosis["translated_summary"] or ""
    if not translated_summary:
        return jsonify(success=False, message="번역된 내용이 없습니다. 먼저 번역을 진행해주세요.")

    # JSON 형태로 저장된 번역 데이터 파싱
    try:
        translated_data = json.loads(translated_summary)
        translated_headers = translated_data.get('headers', {})
        translated_table_data = translated_data.get('table_data', [])
    except:
        # 기존 형식 호환성 유지
        translated_headers = {}
        translated_table_data = []
        translated_text = translated_summary
    else:
        # 표 형식으로 HTML 생성
        header_html = ""
        if translated_headers.get('vehicle_number'):
            header_html += f"<p><strong>{translated_headers['vehicle_number']}</strong></p>"
        if translated_headers.get('lot_number'):
            header_html += f"<p><strong>{translated_headers['lot_number']}</strong></p>"
        if translated_headers.get('parking_number'):
            header_html += f"<p><strong>{translated_headers['parking_number']}</strong></p>"
        if translated_headers.get('evaluator_name'):
            header_html += f"<p><strong>{translated_headers['evaluator_name']}</strong></p>"
        
        table_html = "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"
        table_html += "<thead><tr style='background-color: #366092; color: white;'><th>順</th><th>診断申請内容</th><th>回答</th><th>備考</th></tr></thead>"
        table_html += "<tbody>"
        for row in translated_table_data:
            table_html += f"<tr>"
            table_html += f"<td>{row.get('sequence', '')}</td>"
            table_html += f"<td>{row.get('request_content', '')}</td>"
            table_html += f"<td>{row.get('response_content', '')}</td>"
            table_html += f"<td>{row.get('note', '')}</td>"
            table_html += f"</tr>"
        table_html += "</tbody></table>"
        translated_text = header_html + table_html

    subject = f"진단 결과 - {diagnosis['vehicle_number'] or '차량번호 없음'}"
    body_html = f"""
    <html>
    <body>
        <h2>위카아라이 진단 결과</h2>
        <p>안녕하세요, {applicant['name']}님</p>
        <p>진단 신청 결과를 전송드립니다.</p>
        <hr>
        {translated_text}
        <hr>
        <p>위카모빌리티 주식회사</p>
    </body>
    </html>
    """

    if send_email(applicant["email"], subject, body_html):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "UPDATE diagnosis_requests SET sent_at = ?, status = '전송완료' WHERE id = ?",
            (now, diagnosis_id),
        )
        db.commit()
        return jsonify(success=True, sent_at=now)
    else:
        return jsonify(success=False, message="이메일 전송에 실패했습니다.")


@app.route("/admin/diagnosis/<int:diagnosis_id>/detail/export/<string:fmt>")
@login_required
@role_required("관리자")
def admin_diagnosis_detail_export(diagnosis_id: int, fmt: str):
    if fmt not in ("xlsx", "pdf"):
        abort(404)
    diagnosis = _fetch_diagnosis(diagnosis_id)
    if not diagnosis:
        abort(404)
    details = _fetch_request_details(diagnosis_id)
    responses = _fetch_response_details(diagnosis_id)
    headers = ["순", "진단신청내역", "답변내역", "비고"]
    data = []
    response_map = {resp["sequence"]: resp for resp in responses}
    for detail in details:
        resp = response_map.get(detail["sequence"])
        data.append(
            [
                detail["sequence"],
                detail["content"],
                resp["content"] if resp else "",
                resp["note"] if resp else "",
            ]
        )
    safe_vehicle = (diagnosis["vehicle_number"] or f"diagnosis_{diagnosis_id}").replace(" ", "_")
    filename = EXPORT_DIR / f"{safe_vehicle}_detail.{fmt}"
    if fmt == "xlsx":
        export_to_excel(data, headers, filename)
    else:
        export_to_pdf(data, headers, filename, title="진단신청 상세")
    return send_file(filename, as_attachment=True)


def _collect_admin_export_rows(start_date: str, end_date: str) -> List[sqlite3.Row]:
    db = get_db()
    clause = "WHERE date(dr.request_date) BETWEEN date(?) AND date(?)"
    return db.execute(
        f"""
        SELECT dr.*, applicant.name AS applicant_name, evaluator.name AS evaluator_name
        FROM diagnosis_requests dr
        JOIN users applicant ON applicant.id = dr.applicant_id
        LEFT JOIN users evaluator ON evaluator.id = dr.evaluator_id
        {clause}
        ORDER BY dr.request_date DESC
        """,
        (start_date, end_date),
    ).fetchall()


@app.route("/admin/diagnosis/export/<string:fmt>")
@login_required
@role_required("관리자")
def admin_diagnosis_export(fmt: str):
    if fmt not in ("xlsx", "pdf"):
        abort(404)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    if not start_date or not end_date:
        return redirect(url_for("admin_diagnosis"))

    rows = _collect_admin_export_rows(start_date, end_date)
    headers = [
        "순",
        "신청일",
        "상태",
        "차량번호",
        "출품번호",
        "주차번호",
        "진단신청",
        "답변일",
        "답변",
        "평가사",
        "확인일",
        "전송일",
    ]
    data = []
    for idx, row in enumerate(rows, 1):
        details = _fetch_request_details(row["id"])
        responses = _fetch_response_details(row["id"])
        data.append(
            [
                idx,
                row["request_date"],
                row["status"],
                row["vehicle_number"],
                row["lot_number"],
                row["parking_number"],
                _summarize_details(details, "content"),
                row["answer_date"] or "",
                _summarize_details(responses, "content"),
                row["evaluator_name"] or row["evaluator_name"] or "",
                row["confirmed_at"] or "",
                row["sent_at"] or "",
            ]
        )
    filename = EXPORT_DIR / f"admin_diagnosis_{start_date}_{end_date}.{fmt}"
    if fmt == "xlsx":
        export_to_excel(data, headers, filename)
    else:
        export_to_pdf(data, headers, filename, title="진단신청관리")
    return send_file(filename, as_attachment=True)


def _aggregate_settlement_rows(year: int, month: int) -> Dict[str, Any]:
    db = get_db()
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    rows = db.execute(
        """
        SELECT date(dr.answer_date) AS answer_day,
               COALESCE(evaluator.name, dr.evaluator_name) AS evaluator_name,
               COUNT(*) AS cnt
        FROM diagnosis_requests dr
        LEFT JOIN users evaluator ON evaluator.id = dr.evaluator_id
        WHERE dr.answer_date IS NOT NULL
          AND dr.status = '답변완료'
          AND date(dr.answer_date) >= date(?)
          AND date(dr.answer_date) < date(?)
        GROUP BY answer_day, evaluator_name
        ORDER BY answer_day ASC, evaluator_name ASC
        """,
        (start_date, end_date),
    ).fetchall()

    grouped: Dict[str, Dict[str, Any]] = {}
    total_amount = 0
    total_count = 0

    for row in rows:
        day = row["answer_day"]
        evaluator_name = row["evaluator_name"] or "미지정"
        if day not in grouped:
            grouped[day] = {
                "rows": [],
                "subtotal_count": 0,
                "subtotal_amount": 0,
            }
        # 금액 = 건수 * 15,000
        count = row["cnt"]
        amount = count * 15000
        vat = int(amount * 0.1)
        grand = amount + vat
        grouped[day]["rows"].append(
            {
                "evaluator_name": evaluator_name,
                "count": count,
                "amount": amount,
                "vat": vat,
                "grand": grand,
            }
        )
        grouped[day]["subtotal_count"] += count
        grouped[day]["subtotal_amount"] += amount
        total_amount += amount
        total_count += count

    total_vat = int(total_amount * 0.1)
    payload = {
        "days": grouped,
        "total_count": total_count,
        "total_amount": total_amount,
        "total_vat": total_vat,
        "total_grand": total_amount + total_vat,
    }
    return payload


@app.route("/admin/settlements")
@login_required
@role_required("관리자")
def admin_settlements():
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month:
        now = datetime.now()
        year = now.year
        month = now.month

    payload = _aggregate_settlement_rows(year, month)
    db = get_db()
    saved = db.execute(
        "SELECT * FROM settlements WHERE year = ? AND month = ? ORDER BY created_at DESC",
        (year, month),
    ).fetchall()
    return render_template(
        "admin/settlements.html",
        year=year,
        month=month,
        payload=payload,
        saved_settlements=saved,
    )


@app.route("/admin/settlements/save", methods=["POST"])
@login_required
@role_required("관리자")
def admin_settlements_save():
    year = request.form.get("year", type=int)
    month = request.form.get("month", type=int)
    if not year or not month:
        return redirect(url_for("admin_settlements"))

    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"

    payload = _aggregate_settlement_rows(year, month)
    title = f"{year}년 {month}월"
    settlement_id = save_settlement_payload(year, month, title, start_date, end_date, payload)
    return redirect(url_for("admin_settlement_view", settlement_id=settlement_id))


@app.route("/admin/settlements/<int:settlement_id>")
@login_required
@role_required("관리자")
def admin_settlement_view(settlement_id: int):
    row = fetch_settlement(settlement_id)
    if not row:
        abort(404)
    payload = json.loads(row["payload"])
    return render_template(
        "admin/settlement_view.html",
        settlement=row,
        payload=payload,
    )


@app.route("/admin/settlements/export/<string:fmt>")
@login_required
@role_required("관리자")
def admin_settlements_export(fmt: str):
    if fmt not in ("xlsx", "pdf"):
        abort(404)
    year = request.args.get("year", type=int)
    month = request.args.get("month", type=int)
    if not year or not month:
        return redirect(url_for("admin_settlements"))

    payload = _aggregate_settlement_rows(year, month)
    headers = ["일자", "평가사", "건수", "금액", "VAT", "청구액"]
    data: List[List[Any]] = []
    for day, info in payload["days"].items():
        for row in info["rows"]:
            data.append(
                [
                    day,
                    row["evaluator_name"],
                    row["count"],
                    row["amount"],
                    row["vat"],
                    row["grand"],
                ]
            )
        data.append(
            [
                day,
                "소계",
                info["subtotal_count"],
                info["subtotal_amount"],
                int(info["subtotal_amount"] * 0.1),
                info["subtotal_amount"] + int(info["subtotal_amount"] * 0.1),
            ]
        )
    data.append(
        [
            "총합",
            "",
            payload["total_count"],
            payload["total_amount"],
            payload["total_vat"],
            payload["total_grand"],
        ]
    )
    filename = EXPORT_DIR / f"settlement_{year}_{month:02d}.{fmt}"
    if fmt == "xlsx":
        export_to_excel(data, headers, filename)
    else:
        export_to_pdf(data, headers, filename, title="정산내역")
    return send_file(filename, as_attachment=True)


# ------------------- 진단신청자 영역 ------------------- #


@app.route("/diagnosis/dashboard")
@login_required
@role_required("진단신청")
def diagnosis_dashboard():
    """진단신청 메인페이지"""
    return render_template("diagnosis/dashboard.html")


@app.route("/diagnosis/request", methods=["GET", "POST"])
@login_required
@role_required("진단신청")
def diagnosis_request():
    if request.method == "GET":
        return render_template("diagnosis/request.html")

    vehicle_number = request.form.get("vehicle_number", "").strip()
    lot_number = request.form.get("lot_number", "").strip()
    parking_number = request.form.get("parking_number", "").strip()

    sequences = request.form.getlist("detail_sequence")
    contents = request.form.getlist("detail_content")
    details: List[Tuple[int, str]] = []
    for seq_str, content in zip(sequences, contents):
        content = content.strip()
        if not content:
            continue
        try:
            seq = int(seq_str)
        except ValueError:
            continue
        details.append((seq, content))

    if not vehicle_number or not details:
        return render_template(
            "diagnosis/request.html",
            error="차량번호와 진단신청내역을 입력해주세요.",
            vehicle_number=vehicle_number,
            lot_number=lot_number,
            parking_number=parking_number,
            details=details,
        )

    db = get_db()
    cur = db.cursor()
    cur.execute(
        """
        INSERT INTO diagnosis_requests (applicant_id, vehicle_number, lot_number, parking_number)
        VALUES (?, ?, ?, ?)
        """,
        (session["user_id"], vehicle_number, lot_number, parking_number),
    )
    diagnosis_id = cur.lastrowid

    for seq, content in details:
        cur.execute(
            """
            INSERT INTO diagnosis_request_items (diagnosis_id, sequence, content)
            VALUES (?, ?, ?)
            """,
            (diagnosis_id, seq, content),
        )

    db.commit()
    return redirect(url_for("diagnosis_dashboard"))


@app.route("/diagnosis/history")
@login_required
@role_required("진단신청")
def diagnosis_history():
    db = get_db()
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    query = """
        SELECT * FROM diagnosis_requests
        WHERE applicant_id = ?
    """
    params: List[Any] = [session["user_id"]]
    if start_date:
        query += " AND date(request_date) >= date(?)"
        params.append(start_date)
    if end_date:
        query += " AND date(request_date) <= date(?)"
        params.append(end_date)
    query += " ORDER BY request_date DESC LIMIT 10"
    rows = db.execute(query, params).fetchall()
    enriched = []
    for row in rows:
        details = _fetch_request_details(row["id"])
        responses = _fetch_response_details(row["id"])
        enriched.append(
            {
                "row": row,
                "request_summary": _summarize_details(details, "content"),
                "response_summary": _summarize_details(responses, "content"),
            }
        )
    return render_template(
        "diagnosis/history.html",
        diagnoses=enriched,
        start_date=start_date or "",
        end_date=end_date or "",
    )


@app.route("/diagnosis/history/export/<string:fmt>")
@login_required
@role_required("진단신청")
def diagnosis_history_export(fmt: str):
    if fmt not in ("xlsx", "pdf"):
        abort(404)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    db = get_db()
    query = """
        SELECT * FROM diagnosis_requests
        WHERE applicant_id = ?
    """
    params: List[Any] = [session["user_id"]]
    if start_date:
        query += " AND date(request_date) >= date(?)"
        params.append(start_date)
    if end_date:
        query += " AND date(request_date) <= date(?)"
        params.append(end_date)
    rows = db.execute(query, params).fetchall()
    headers = ["신청일", "상태", "차량번호", "출품번호", "주차번호", "진단신청", "답변", "답변일"]
    data = []
    for row in rows:
        details = _fetch_request_details(row["id"])
        responses = _fetch_response_details(row["id"])
        data.append(
            [
                row["request_date"],
                row["status"],
                row["vehicle_number"],
                row["lot_number"],
                row["parking_number"],
                _summarize_details(details, "content"),
                _summarize_details(responses, "content"),
                row["answer_date"] or "",
            ]
        )
    filename = EXPORT_DIR / f"diagnosis_history_{session['username']}.{fmt}"
    if fmt == "xlsx":
        export_to_excel(data, headers, filename)
    else:
        export_to_pdf(data, headers, filename, title="진단신청내역")
    return send_file(filename, as_attachment=True)


# ------------------- 평가사 영역 ------------------- #


@app.route("/evaluator/dashboard")
@login_required
@role_required("평가사")
def evaluator_dashboard():
    return render_template("evaluator/dashboard.html")


@app.route("/evaluator/status")
@login_required
@role_required("평가사")
def evaluator_status():
    clause, params = _filter_clause("dr.request_date")
    db = get_db()
    rows = db.execute(
        f"""
        SELECT dr.*, applicant.name AS applicant_name
        FROM diagnosis_requests dr
        JOIN users applicant ON applicant.id = dr.applicant_id
        WHERE 1=1 {clause}
        ORDER BY dr.request_date DESC
        """,
        params,
    ).fetchall()

    evaluators = db.execute(
        "SELECT * FROM users WHERE user_type = '평가사' AND approved = 1"
    ).fetchall()

    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    return render_template(
        "evaluator/status.html",
        requests=rows,
        evaluators=evaluators,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/admin/diagnosis/<int:diagnosis_id>/assign-evaluator", methods=["POST"])
@login_required
@role_required("관리자")
def admin_assign_evaluator(diagnosis_id: int):
    """관리자가 평가사를 배정하는 API"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(success=False, message="요청 데이터가 없습니다."), 400
        
        evaluator_id = data.get("evaluator_id")
        manual_name = data.get("manual_name", "").strip() if data.get("manual_name") else ""

        if not evaluator_id and not manual_name:
            return jsonify(success=False, message="평가사를 선택하거나 입력해주세요."), 400

        db = get_db()
        if evaluator_id:
            evaluator = db.execute("SELECT * FROM users WHERE id = ? AND user_type = '평가사'", (evaluator_id,)).fetchone()
            if not evaluator:
                return jsonify(success=False, message="평가사를 찾을 수 없습니다."), 404
            evaluator_name = evaluator["name"] if evaluator["name"] else ""
            evaluator_email = evaluator["email"] if evaluator["email"] else None
        elif manual_name:
            evaluator_name = manual_name
            evaluator_id = None
            evaluator_email = None
        else:
            return jsonify(success=False, message="평가사를 선택하거나 입력해주세요."), 400

        # 진단신청 정보 가져오기
        diagnosis = _fetch_diagnosis(diagnosis_id)
        if not diagnosis:
            return jsonify(success=False, message="진단신청을 찾을 수 없습니다."), 404

        # 평가사 배정
        db.execute(
            """
            UPDATE diagnosis_requests
            SET evaluator_id = ?, evaluator_name = ?, status = '평가사배정'
            WHERE id = ?
            """,
            (evaluator_id, evaluator_name, diagnosis_id),
        )
        db.commit()

        # 평가사에게 알림 이메일 전송 (이메일이 있는 경우)
        if evaluator_email:
            try:
                # sqlite3.Row는 딕셔너리처럼 접근 (None 체크 필요)
                vehicle_num = diagnosis['vehicle_number'] or '차량번호 없음'
                lot_num = diagnosis['lot_number'] or ''
                parking_num = diagnosis['parking_number'] or ''
                request_date = diagnosis['request_date'] or ''
                
                subject = f"진단 신청 배정 알림 - {vehicle_num}"
                body_html = f"""
                <html>
                <body>
                    <h2>진단 신청 배정 알림</h2>
                    <p>안녕하세요, {evaluator_name}님</p>
                    <p>새로운 진단 신청이 배정되었습니다.</p>
                    <hr>
                    <p><strong>차량번호:</strong> {vehicle_num}</p>
                    <p><strong>출품번호:</strong> {lot_num}</p>
                    <p><strong>주차번호:</strong> {parking_num}</p>
                    <p><strong>신청일:</strong> {request_date}</p>
                    <hr>
                    <p>평가사 페이지에서 답변을 입력해주세요.</p>
                    <p>위카모빌리티 주식회사</p>
                </body>
                </html>
                """
                send_email(evaluator_email, subject, body_html)
            except Exception as e:
                # 이메일 전송 실패해도 평가사 배정은 성공으로 처리
                print(f"이메일 전송 실패 (평가사 배정은 성공): {e}")

        return jsonify(success=True, evaluator_name=evaluator_name)
    except Exception as e:
        print(f"평가사 배정 오류: {e}")
        import traceback
        traceback.print_exc()
        return jsonify(success=False, message=f"오류가 발생했습니다: {str(e)}"), 500


@app.route("/evaluator/status/assign", methods=["POST"])
@login_required
@role_required("평가사")
def evaluator_assign():
    data = request.get_json()
    diagnosis_id = data.get("diagnosis_id")
    evaluator_id = data.get("evaluator_id")
    manual_name = data.get("manual_name", "").strip()

    if not diagnosis_id:
        return jsonify(success=False, message="잘못된 요청입니다.")

    db = get_db()
    if evaluator_id:
        evaluator = db.execute("SELECT * FROM users WHERE id = ?", (evaluator_id,)).fetchone()
        if not evaluator:
            return jsonify(success=False, message="평가사를 찾을 수 없습니다.")
        evaluator_name = evaluator["name"]
    elif manual_name:
        evaluator_name = manual_name
        evaluator_id = None
    else:
        return jsonify(success=False, message="평가사를 선택하거나 입력해주세요.")

    db.execute(
        """
        UPDATE diagnosis_requests
        SET evaluator_id = ?, evaluator_name = ?, status = '평가사배정'
        WHERE id = ?
        """,
        (evaluator_id, evaluator_name, diagnosis_id),
    )
    db.commit()

    return jsonify(success=True)


@app.route("/evaluator/status/complete", methods=["POST"])
@login_required
@role_required("평가사")
def evaluator_complete():
    data = request.get_json()
    diagnosis_id = data.get("diagnosis_id")

    if not diagnosis_id:
        return jsonify(success=False, message="잘못된 요청입니다.")

    db = get_db()
    db.execute(
        "UPDATE diagnosis_requests SET status = '평가완료' WHERE id = ?",
        (diagnosis_id,),
    )
    db.commit()

    return jsonify(success=True)


@app.route("/evaluator/response")
@login_required
@role_required("평가사")
def evaluator_response():
    clause, params = _filter_clause("dr.request_date")
    db = get_db()
    rows = db.execute(
        f"""
        SELECT dr.*, applicant.name AS applicant_name
        FROM diagnosis_requests dr
        JOIN users applicant ON applicant.id = dr.applicant_id
        WHERE (dr.evaluator_id = ? OR dr.evaluator_name = (SELECT name FROM users WHERE id = ?))
          {clause}
        ORDER BY dr.request_date DESC
        """,
        [session["user_id"], session["user_id"]] + params,
    ).fetchall()

    enriched = []
    for row in rows:
        details = _fetch_request_details(row["id"])
        responses = _fetch_response_details(row["id"])
        enriched.append(
            {
                "row": row,
                "request_summary": _summarize_details(details, "content"),
                "response_summary": _summarize_details(responses, "content"),
            }
        )

    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    return render_template(
        "evaluator/response.html",
        requests=enriched,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/evaluator/response/<int:diagnosis_id>")
@login_required
@role_required("평가사")
def evaluator_response_form(diagnosis_id: int):
    diagnosis = _fetch_diagnosis(diagnosis_id)
    if not diagnosis:
        abort(404)

    details = _fetch_request_details(diagnosis_id)
    if not details:
        db = get_db()
        for idx, default_item in enumerate(DEFAULT_REQUEST_ITEMS, 1):
            db.execute(
                """
                INSERT INTO diagnosis_request_items (diagnosis_id, sequence, content)
                VALUES (?, ?, ?)
                """,
                (diagnosis_id, idx, default_item),
            )
        db.commit()
        details = _fetch_request_details(diagnosis_id)

    responses = _fetch_response_details(diagnosis_id)
    return render_template(
        "evaluator/response_form.html",
        diagnosis=diagnosis,
        request_details=details[:5],
        response_details=responses,
    )


@app.route("/evaluator/response/<int:diagnosis_id>/json")
@login_required
@role_required("평가사")
def evaluator_response_form_json(diagnosis_id: int):
    """평가사 답변 입력 폼 데이터를 JSON으로 반환"""
    diagnosis = _fetch_diagnosis(diagnosis_id)
    if not diagnosis:
        return jsonify(success=False, message="진단신청을 찾을 수 없습니다."), 404

    details = _fetch_request_details(diagnosis_id)
    if not details:
        db = get_db()
        for idx, default_item in enumerate(DEFAULT_REQUEST_ITEMS, 1):
            db.execute(
                """
                INSERT INTO diagnosis_request_items (diagnosis_id, sequence, content)
                VALUES (?, ?, ?)
                """,
                (diagnosis_id, idx, default_item),
            )
        db.commit()
        details = _fetch_request_details(diagnosis_id)

    responses = _fetch_response_details(diagnosis_id)
    response_map = {resp["sequence"]: resp for resp in responses}
    
    # 테이블 데이터 구성
    table_data = []
    for detail in details[:5]:
        resp = response_map.get(detail["sequence"])
        table_data.append({
            "sequence": detail["sequence"],
            "request_content": detail["content"],
            "response_content": resp["content"] if resp else "",
            "note": resp["note"] if resp else "",
        })
    
    return jsonify(
        success=True,
        diagnosis={
            "id": diagnosis["id"],
            "request_date": diagnosis["request_date"],
            "vehicle_number": diagnosis["vehicle_number"] or "",
            "lot_number": diagnosis["lot_number"] or "",
            "parking_number": diagnosis["parking_number"] or "",
            "evaluator_name": diagnosis["evaluator_name"] or "",
        },
        table_data=table_data,
    )


@app.route("/evaluator/response/save", methods=["POST"])
@login_required
@role_required("평가사")
def evaluator_response_save():
    data = request.get_json()
    diagnosis_id = data.get("diagnosis_id")
    details = data.get("details", [])

    if not diagnosis_id:
        return jsonify(success=False, message="잘못된 요청입니다.")

    db = get_db()
    for detail in details:
        seq = detail.get("sequence")
        content = detail.get("content", "").strip()
        note = detail.get("note", "").strip()

        if not content:
            continue

        db.execute(
            """
            INSERT OR REPLACE INTO diagnosis_response_details
            (diagnosis_id, responder_id, sequence, content, note, updated_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """,
            (diagnosis_id, session["user_id"], seq, content, note),
        )

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE diagnosis_requests SET answer_date = ?, status = '답변완료' WHERE id = ?",
        (now, diagnosis_id),
    )
    db.commit()

    return jsonify(success=True, message="저장되었습니다.")


@app.route("/evaluator/response/history")
@login_required
@role_required("평가사")
def evaluator_response_history():
    """답변내역 페이지 - 이미 답변이 입력된 건들만 표시"""
    clause, params = _filter_clause("dr.request_date")
    db = get_db()
    rows = db.execute(
        f"""
        SELECT dr.*, applicant.name AS applicant_name
        FROM diagnosis_requests dr
        JOIN users applicant ON applicant.id = dr.applicant_id
        WHERE (dr.evaluator_id = ? OR dr.evaluator_name = (SELECT name FROM users WHERE id = ?))
          AND dr.answer_date IS NOT NULL
          {clause}
        ORDER BY dr.request_date DESC
        """,
        [session["user_id"], session["user_id"]] + params,
    ).fetchall()

    enriched = []
    for row in rows:
        details = _fetch_request_details(row["id"])
        responses = _fetch_response_details(row["id"])
        enriched.append(
            {
                "row": row,
                "request_summary": _summarize_details(details, "content"),
                "response_summary": _summarize_details(responses, "content"),
            }
        )

    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    return render_template(
        "evaluator/response_history.html",
        requests=enriched,
        start_date=start_date,
        end_date=end_date,
    )


@app.route("/evaluator/response/confirm", methods=["POST"])
@login_required
@role_required("평가사")
def evaluator_response_confirm():
    data = request.get_json()
    diagnosis_id = data.get("diagnosis_id")

    if not diagnosis_id:
        return jsonify(success=False, message="잘못된 요청입니다.")

    db = get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        "UPDATE diagnosis_requests SET status = '답변완료', answer_date = ? WHERE id = ?",
        (now, diagnosis_id),
    )
    db.commit()

    return jsonify(success=True)


@app.route("/evaluator/response/export/<string:fmt>")
@login_required
@role_required("평가사")
def evaluator_response_export(fmt: str):
    if fmt not in ("xlsx", "pdf"):
        abort(404)
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    if not start_date or not end_date:
        return redirect(url_for("evaluator_response"))

    clause, params = _filter_clause("dr.request_date")
    db = get_db()
    rows = db.execute(
        f"""
        SELECT dr.*, applicant.name AS applicant_name
        FROM diagnosis_requests dr
        JOIN users applicant ON applicant.id = dr.applicant_id
        WHERE (dr.evaluator_id = ? OR dr.evaluator_name = (SELECT name FROM users WHERE id = ?))
          {clause}
        ORDER BY dr.request_date DESC
        """,
        [session["user_id"], session["user_id"]] + params,
    ).fetchall()

    headers = [
        "신청일",
        "차량번호",
        "출품번호",
        "주차번호",
        "진단신청내역",
        "답변내역",
        "답변일",
    ]
    data: List[List[Any]] = []
    for row in rows:
        request_details = _fetch_request_details(row["id"])
        response_details = _fetch_response_details(row["id"])
        data.append(
            [
                row["request_date"],
                row["vehicle_number"],
                row["lot_number"],
                row["parking_number"],
                _summarize_details(request_details, "content"),
                _summarize_details(response_details, "content"),
                row["answer_date"] or "",
            ]
        )

    filename = EXPORT_DIR / f"evaluator_response_{start_date}_{end_date}.{fmt}"
    if fmt == "xlsx":
        export_to_excel(data, headers, filename)
    else:
        export_to_pdf(data, headers, filename, title="평가답변")
    return send_file(filename, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3010))
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)

