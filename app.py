"""
위카아라이 검수시스템 Flask 애플리케이션
"""
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db_connection, init_db, DB_PATH
from utils import export_to_excel, export_to_pdf, translate_to_japanese, format_datetime, format_date
from datetime import datetime, date
import os
import json
import traceback

app = Flask(__name__)
app.secret_key = 'wecar_inspection_secret_key_2024'

# 데이터베이스 초기화
try:
    if not os.path.exists(DB_PATH):
        print(f"데이터베이스가 없습니다. 초기화를 시작합니다. 경로: {DB_PATH}")
        init_db()
    else:
        print(f"데이터베이스가 존재합니다. 경로: {DB_PATH}")
except Exception as e:
    print(f"데이터베이스 초기화 중 오류 발생: {str(e)}")
    if app.debug:
        print(traceback.format_exc())

# 에러 핸들러 추가
@app.errorhandler(500)
def internal_error(error):
    """500 에러 핸들러"""
    # JSON 요청인지 확인
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'message': 'Internal Server Error',
            'error': str(error) if app.debug else 'An error occurred'
        }), 500
    # HTML 요청인 경우 에러 페이지 반환
    return f"<h1>Internal Server Error</h1><p>{str(error) if app.debug else 'An error occurred'}</p>", 500

@app.errorhandler(404)
def not_found(error):
    """404 에러 핸들러"""
    if request.is_json or request.path.startswith('/api/'):
        return jsonify({
            'success': False,
            'message': 'Not Found'
        }), 404
    return "<h1>Not Found</h1>", 404

@app.errorhandler(Exception)
def handle_exception(e):
    """모든 예외 처리"""
    # 로그 출력
    print(f"Error: {str(e)}")
    if app.debug:
        print(traceback.format_exc())
    
    # JSON 요청인지 확인
    if request.is_json or request.path.startswith('/api/'):
        if app.debug:
            return jsonify({
                'success': False,
                'message': str(e),
                'traceback': traceback.format_exc()
            }), 500
        return jsonify({
            'success': False,
            'message': 'An error occurred'
        }), 500
    
    # HTML 요청인 경우
    if app.debug:
        return f"<h1>Error</h1><pre>{traceback.format_exc()}</pre>", 500
    return "<h1>An error occurred</h1>", 500

def login_required(f):
    """로그인 필요 데코레이터"""
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def admin_required(f):
    """관리자 권한 필요 데코레이터"""
    def decorated_function(*args, **kwargs):
        try:
            if 'user_id' not in session:
                return redirect(url_for('login'))
            conn = get_db_connection()
            try:
                user = conn.execute('SELECT user_type FROM users WHERE id = ?', (session['user_id'],)).fetchone()
                if not user or user['user_type'] != '관리자':
                    return redirect(url_for('dashboard'))
            finally:
                conn.close()
            return f(*args, **kwargs)
        except Exception as e:
            if app.debug:
                return jsonify({'success': False, 'message': f'Error: {str(e)}', 'traceback': traceback.format_exc()}), 500
            return jsonify({'success': False, 'message': 'An error occurred'}), 500
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/')
def index():
    """메인 페이지 - 로그인 페이지로 리다이렉트"""
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """로그인 페이지"""
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            password = request.form.get('password')
            
            if not username or not password:
                return jsonify({'success': False, 'message': '아이디와 비밀번호를 입력해주세요.'})
            
            conn = get_db_connection()
            try:
                user = conn.execute(
                    'SELECT * FROM users WHERE username = ?', (username,)
                ).fetchone()
            finally:
                conn.close()
            
            if user and check_password_hash(user['password'], password):
                if user['approved'] == 0:
                    return jsonify({'success': False, 'message': '회원가입승인이 미완료 되었습니다. 완료후 이용하여주세요.'})
                
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['user_type'] = user['user_type']
                session['name'] = user['name']
                
                # 사용자 타입에 따라 대시보드로 이동
                if user['user_type'] == '관리자':
                    return jsonify({'success': True, 'redirect': url_for('admin_dashboard')})
                elif user['user_type'] == '검수신청':
                    return jsonify({'success': True, 'redirect': url_for('inspection_dashboard')})
                elif user['user_type'] == '평가사':
                    return jsonify({'success': True, 'redirect': url_for('evaluator_dashboard')})
            else:
                return jsonify({'success': False, 'message': '아이디 또는 비밀번호가 올바르지 않습니다.'})
        except Exception as e:
            if app.debug:
                return jsonify({'success': False, 'message': f'로그인 중 오류가 발생했습니다: {str(e)}', 'traceback': traceback.format_exc()}), 500
            return jsonify({'success': False, 'message': '로그인 중 오류가 발생했습니다.'}), 500
    
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    """회원가입"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    password_confirm = data.get('password_confirm')
    user_type = data.get('user_type')
    company = data.get('company', '')
    position = data.get('position', '')
    name = data.get('name')
    
    if password != password_confirm:
        return jsonify({'success': False, 'message': '비밀번호가 일치하지 않습니다.'})
    
    conn = get_db_connection()
    try:
        existing_user = conn.execute(
            'SELECT id FROM users WHERE username = ?', (username,)
        ).fetchone()
        
        if existing_user:
            return jsonify({'success': False, 'message': '이미 존재하는 아이디입니다.'})
        
        hashed_password = generate_password_hash(password)
        conn.execute('''
            INSERT INTO users (username, password, user_type, company, position, name, approved)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (username, hashed_password, user_type, company, position, name, 0))
        conn.commit()
        return jsonify({'success': True, 'message': '회원가입 신청이 완료되었습니다. 관리자 승인 후 이용 가능합니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'회원가입 중 오류가 발생했습니다: {str(e)}'})
    finally:
        conn.close()

@app.route('/logout')
def logout():
    """로그아웃"""
    session.clear()
    return redirect(url_for('login'))

# 관리자 페이지
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """관리자 대시보드"""
    return render_template('admin/dashboard.html')

@app.route('/admin/users')
@admin_required
def admin_users():
    """회원관리 페이지"""
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/update', methods=['POST'])
@admin_required
def admin_users_update():
    """회원 정보 수정"""
    data = request.get_json()
    user_id = data.get('id')
    username = data.get('username')
    password = data.get('password')
    user_type = data.get('user_type')
    company = data.get('company', '')
    position = data.get('position', '')
    name = data.get('name')
    
    conn = get_db_connection()
    try:
        if password:
            hashed_password = generate_password_hash(password)
            conn.execute('''
                UPDATE users SET username=?, password=?, user_type=?, company=?, position=?, name=?
                WHERE id=?
            ''', (username, hashed_password, user_type, company, position, name, user_id))
        else:
            conn.execute('''
                UPDATE users SET username=?, user_type=?, company=?, position=?, name=?
                WHERE id=?
            ''', (username, user_type, company, position, name, user_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/users/delete', methods=['POST'])
@admin_required
def admin_users_delete():
    """회원 삭제"""
    data = request.get_json()
    user_id = data.get('id')
    
    conn = get_db_connection()
    try:
        conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/users/approve', methods=['POST'])
@admin_required
def admin_users_approve():
    """회원가입 승인"""
    data = request.get_json()
    user_id = data.get('id')
    approved = data.get('approved', 1)
    
    conn = get_db_connection()
    try:
        conn.execute('UPDATE users SET approved = ? WHERE id = ?', (approved, user_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/inspections')
@admin_required
def admin_inspections():
    """검수신청관리 페이지"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.*, u.name as user_name,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               er.response_date, er.sent_date,
               GROUP_CONCAT(erd.content, '/') as response_contents,
               ea.evaluator_id, ev.name as evaluator_name
        FROM inspection_requests ir
        LEFT JOIN users u ON ir.user_id = u.id
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        LEFT JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN users ev ON ea.evaluator_id = ev.id
        LEFT JOIN evaluation_responses er ON ir.id = er.request_id AND er.evaluator_id = ea.evaluator_id
        LEFT JOIN evaluation_response_details erd ON er.id = erd.response_id
    '''
    
    conditions = []
    if start_date:
        conditions.append(f"DATE(ir.request_date) >= '{start_date}'")
    if end_date:
        conditions.append(f"DATE(ir.request_date) <= '{end_date}'")
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    inspections = conn.execute(query).fetchall()
    conn.close()
    
    return render_template('admin/inspections.html', inspections=inspections, start_date=start_date, end_date=end_date)

@app.route('/admin/inspections/<int:request_id>/details')
@admin_required
def admin_inspection_details(request_id):
    """검수신청 상세보기"""
    conn = get_db_connection()
    request_info = conn.execute('''
        SELECT ir.*, u.name as user_name, ev.name as evaluator_name
        FROM inspection_requests ir
        LEFT JOIN users u ON ir.user_id = u.id
        LEFT JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN users ev ON ea.evaluator_id = ev.id
        WHERE ir.id = ?
    ''', (request_id,)).fetchone()
    
    inspection_details = conn.execute('''
        SELECT * FROM inspection_details WHERE request_id = ? ORDER BY sequence
    ''', (request_id,)).fetchall()
    
    response = conn.execute('''
        SELECT * FROM evaluation_responses WHERE request_id = ? LIMIT 1
    ''', (request_id,)).fetchone()
    
    response_details = []
    if response:
        response_details = conn.execute('''
            SELECT * FROM evaluation_response_details WHERE response_id = ? ORDER BY sequence
        ''', (response['id'],)).fetchall()
    
    conn.close()
    
    return render_template('admin/inspection_details.html', 
                         request_info=request_info,
                         inspection_details=inspection_details,
                         response_details=response_details,
                         response=response)

@app.route('/admin/inspections/<int:request_id>/details/save', methods=['POST'])
@admin_required
def admin_inspection_details_save(request_id):
    """검수신청 상세내역 저장"""
    data = request.get_json()
    details = data.get('details', [])
    
    conn = get_db_connection()
    try:
        for detail in details:
            # 검수신청내역 업데이트
            if detail.get('detail_id'):
                conn.execute('''
                    UPDATE inspection_details SET content = ? WHERE id = ?
                ''', (detail.get('inspection_content', ''), detail['detail_id']))
            
            # 평가답변내역 업데이트 또는 생성
            if detail.get('response_id'):
                conn.execute('''
                    UPDATE evaluation_response_details 
                    SET content = ?, note = ? WHERE id = ?
                ''', (detail.get('response_content', ''), detail.get('response_note', ''), detail['response_id']))
            elif detail.get('response_content'):
                # 새로운 답변 생성
                response = conn.execute('''
                    SELECT id FROM evaluation_responses WHERE request_id = ? LIMIT 1
                ''', (request_id,)).fetchone()
                
                if response:
                    conn.execute('''
                        INSERT INTO evaluation_response_details (response_id, sequence, content, note)
                        VALUES (?, ?, ?, ?)
                    ''', (response['id'], detail['sequence'], detail.get('response_content', ''), detail.get('response_note', '')))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/inspections/<int:request_id>/export/excel')
@admin_required
def admin_inspection_export_excel(request_id):
    """검수신청 상세 엑셀 내보내기"""
    conn = get_db_connection()
    request_info = conn.execute('''
        SELECT ir.*, u.name as user_name, ev.name as evaluator_name
        FROM inspection_requests ir
        LEFT JOIN users u ON ir.user_id = u.id
        LEFT JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN users ev ON ea.evaluator_id = ev.id
        WHERE ir.id = ?
    ''', (request_id,)).fetchone()
    
    inspection_details = conn.execute('''
        SELECT * FROM inspection_details WHERE request_id = ? ORDER BY sequence
    ''', (request_id,)).fetchall()
    
    response = conn.execute('''
        SELECT * FROM evaluation_responses WHERE request_id = ? LIMIT 1
    ''', (request_id,)).fetchone()
    
    response_details = []
    if response:
        response_details = conn.execute('''
            SELECT * FROM evaluation_response_details WHERE response_id = ? ORDER BY sequence
        ''', (response['id'],)).fetchall()
    
    conn.close()
    
    # 엑셀 데이터 준비
    headers = ['순', '검수신청내역', '답변내역', '비고']
    data = []
    for detail in inspection_details:
        resp_detail = next((r for r in response_details if r['sequence'] == detail['sequence']), None)
        data.append([
            detail['sequence'],
            detail['content'],
            resp_detail['content'] if resp_detail else '',
            resp_detail['note'] if resp_detail and resp_detail['note'] else ''
        ])
    
    filename = f"{request_info['vehicle_number'] or 'inspection'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    export_to_excel(data, headers, filename)
    return send_file(filename, as_attachment=True)

@app.route('/admin/inspections/<int:request_id>/export/pdf')
@admin_required
def admin_inspection_export_pdf(request_id):
    """검수신청 상세 PDF 내보내기"""
    conn = get_db_connection()
    request_info = conn.execute('''
        SELECT ir.*, u.name as user_name, ev.name as evaluator_name
        FROM inspection_requests ir
        LEFT JOIN users u ON ir.user_id = u.id
        LEFT JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN users ev ON ea.evaluator_id = ev.id
        WHERE ir.id = ?
    ''', (request_id,)).fetchone()
    
    inspection_details = conn.execute('''
        SELECT * FROM inspection_details WHERE request_id = ? ORDER BY sequence
    ''', (request_id,)).fetchall()
    
    response = conn.execute('''
        SELECT * FROM evaluation_responses WHERE request_id = ? LIMIT 1
    ''', (request_id,)).fetchone()
    
    response_details = []
    if response:
        response_details = conn.execute('''
            SELECT * FROM evaluation_response_details WHERE response_id = ? ORDER BY sequence
        ''', (response['id'],)).fetchall()
    
    conn.close()
    
    # PDF 데이터 준비
    headers = ['순', '검수신청내역', '답변내역', '비고']
    data = []
    for detail in inspection_details:
        resp_detail = next((r for r in response_details if r['sequence'] == detail['sequence']), None)
        data.append([
            str(detail['sequence']),
            detail['content'],
            resp_detail['content'] if resp_detail else '',
            resp_detail['note'] if resp_detail and resp_detail['note'] else ''
        ])
    
    filename = f"{request_info['vehicle_number'] or 'inspection'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    export_to_pdf(data, headers, filename, title=f"검수신청 상세 - {request_info['vehicle_number'] or ''}")
    return send_file(filename, as_attachment=True)

@app.route('/admin/inspections/<int:request_id>/translate')
@admin_required
def admin_inspection_translate(request_id):
    """번역 페이지"""
    conn = get_db_connection()
    request_info = conn.execute('''
        SELECT ir.*, u.name as user_name, ev.name as evaluator_name
        FROM inspection_requests ir
        LEFT JOIN users u ON ir.user_id = u.id
        LEFT JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN users ev ON ea.evaluator_id = ev.id
        WHERE ir.id = ?
    ''', (request_id,)).fetchone()
    
    inspection_details = conn.execute('''
        SELECT * FROM inspection_details WHERE request_id = ? ORDER BY sequence
    ''', (request_id,)).fetchall()
    
    response = conn.execute('''
        SELECT * FROM evaluation_responses WHERE request_id = ? LIMIT 1
    ''', (request_id,)).fetchone()
    
    response_details = []
    if response:
        response_details = conn.execute('''
            SELECT * FROM evaluation_response_details WHERE response_id = ? ORDER BY sequence
        ''', (response['id'],)).fetchall()
    
    conn.close()
    
    return render_template('admin/inspection_translate.html', 
                         request_info=request_info,
                         inspection_details=inspection_details,
                         response_details=response_details,
                         response=response)

@app.route('/admin/inspections/<int:request_id>/send', methods=['POST'])
@admin_required
def admin_inspection_send(request_id):
    """검수 결과 전송"""
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE inspection_requests SET sent_date = CURRENT_TIMESTAMP WHERE id = ?
        ''', (request_id,))
        conn.execute('''
            UPDATE evaluation_responses SET sent_date = CURRENT_TIMESTAMP WHERE request_id = ?
        ''', (request_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/inspections/export/excel')
@admin_required
def admin_inspections_export_excel():
    """검수신청 엑셀 내보내기"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.request_date, ir.vehicle_number, ir.lot_number, ir.parking_number,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               GROUP_CONCAT(erd.content, '/') as response_contents,
               er.response_date, ir.sent_date
        FROM inspection_requests ir
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        LEFT JOIN evaluation_responses er ON ir.id = er.request_id
        LEFT JOIN evaluation_response_details erd ON er.id = erd.response_id
    '''
    
    conditions = []
    if start_date:
        conditions.append(f"DATE(ir.request_date) >= '{start_date}'")
    if end_date:
        conditions.append(f"DATE(ir.request_date) <= '{end_date}'")
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    inspections = conn.execute(query).fetchall()
    conn.close()
    
    headers = ['신청일', '차량번호', '출품번호', '주차번호', '검수신청', '평가답변', '답변일', '전송일']
    data = []
    for row in inspections:
        data.append([
            format_datetime(row['request_date']),
            row['vehicle_number'] or '',
            row['lot_number'] or '',
            row['parking_number'] or '',
            row['inspection_contents'] or '',
            row['response_contents'] or '',
            format_datetime(row['response_date']),
            format_datetime(row['sent_date'])
        ])
    
    filename = f'inspections_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    export_to_excel(data, headers, filename)
    return send_file(filename, as_attachment=True)

@app.route('/admin/inspections/export/pdf')
@admin_required
def admin_inspections_export_pdf():
    """검수신청 PDF 내보내기"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.request_date, ir.vehicle_number, ir.lot_number, ir.parking_number,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               GROUP_CONCAT(erd.content, '/') as response_contents,
               er.response_date, ir.sent_date
        FROM inspection_requests ir
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        LEFT JOIN evaluation_responses er ON ir.id = er.request_id
        LEFT JOIN evaluation_response_details erd ON er.id = erd.response_id
    '''
    
    conditions = []
    if start_date:
        conditions.append(f"DATE(ir.request_date) >= '{start_date}'")
    if end_date:
        conditions.append(f"DATE(ir.request_date) <= '{end_date}'")
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    inspections = conn.execute(query).fetchall()
    conn.close()
    
    headers = ['신청일', '차량번호', '출품번호', '주차번호', '검수신청', '평가답변', '답변일', '전송일']
    data = []
    for row in inspections:
        data.append([
            format_datetime(row['request_date']),
            row['vehicle_number'] or '',
            row['lot_number'] or '',
            row['parking_number'] or '',
            row['inspection_contents'] or '',
            row['response_contents'] or '',
            format_datetime(row['response_date']),
            format_datetime(row['sent_date'])
        ])
    
    filename = f'inspections_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    export_to_pdf(data, headers, filename)
    return send_file(filename, as_attachment=True)

@app.route('/admin/settlements')
@admin_required
def admin_settlements():
    """정산관리 페이지"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    
    # 저장된 정산내역 목록
    saved_settlements = conn.execute('''
        SELECT * FROM saved_settlements ORDER BY created_at DESC
    ''').fetchall()
    
    settlements = []
    settlements_with_totals = []
    if start_date and end_date:
        query = '''
            SELECT DATE(er.response_date) as settlement_date, 
                   ev.id as evaluator_id, ev.name as evaluator_name,
                   COUNT(DISTINCT er.id) as count,
                   COUNT(DISTINCT er.id) * 10000 as amount,
                   COUNT(DISTINCT er.id) * 1000 as vat,
                   COUNT(DISTINCT er.id) * 11000 as total_amount
            FROM evaluation_responses er
            JOIN evaluation_assignments ea ON er.request_id = ea.request_id AND er.evaluator_id = ea.evaluator_id
            JOIN users ev ON er.evaluator_id = ev.id
            WHERE DATE(er.response_date) >= ? AND DATE(er.response_date) <= ?
            GROUP BY DATE(er.response_date), ev.id
            ORDER BY settlement_date, ev.name
        '''
        settlements = conn.execute(query, (start_date, end_date)).fetchall()
        
        # 소계 및 합계 계산
        current_date = None
        date_totals = {}
        grand_totals = {'count': 0, 'amount': 0, 'vat': 0, 'total_amount': 0}
        
        for settlement in settlements:
            settlement_dict = dict(settlement)
            settlement_date = settlement_dict['settlement_date']
            
            if current_date != settlement_date:
                if current_date is not None:
                    # 이전 날짜의 소계 추가
                    settlements_with_totals.append({
                        'type': 'subtotal',
                        'date': current_date,
                        **date_totals[current_date]
                    })
                current_date = settlement_date
                if settlement_date not in date_totals:
                    date_totals[settlement_date] = {'count': 0, 'amount': 0, 'vat': 0, 'total_amount': 0}
            
            settlements_with_totals.append({
                'type': 'data',
                **settlement_dict
            })
            
            # 날짜별 합계
            date_totals[settlement_date]['count'] += settlement_dict['count']
            date_totals[settlement_date]['amount'] += settlement_dict['amount']
            date_totals[settlement_date]['vat'] += settlement_dict['vat']
            date_totals[settlement_date]['total_amount'] += settlement_dict['total_amount']
            
            # 전체 합계
            grand_totals['count'] += settlement_dict['count']
            grand_totals['amount'] += settlement_dict['amount']
            grand_totals['vat'] += settlement_dict['vat']
            grand_totals['total_amount'] += settlement_dict['total_amount']
        
        # 마지막 날짜의 소계 추가
        if current_date is not None:
            settlements_with_totals.append({
                'type': 'subtotal',
                'date': current_date,
                **date_totals[current_date]
            })
        
        # 전체 합계 추가
        settlements_with_totals.append({
            'type': 'grandtotal',
            **grand_totals
        })
    
    conn.close()
    
    return render_template('admin/settlements.html', 
                         settlements=settlements_with_totals, 
                         saved_settlements=saved_settlements,
                         start_date=start_date, 
                         end_date=end_date)

@app.route('/admin/settlements/save', methods=['POST'])
@admin_required
def admin_settlements_save():
    """정산내역 저장"""
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    settlement_data = data.get('data')
    
    conn = get_db_connection()
    try:
        name = f"{start_date}_{end_date}"
        conn.execute('''
            INSERT INTO saved_settlements (name, start_date, end_date, data)
            VALUES (?, ?, ?, ?)
        ''', (name, start_date, end_date, json.dumps(settlement_data)))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/admin/settlements/<int:settlement_id>')
@admin_required
def admin_settlement_view(settlement_id):
    """저장된 정산내역 보기"""
    conn = get_db_connection()
    settlement = conn.execute('''
        SELECT * FROM saved_settlements WHERE id = ?
    ''', (settlement_id,)).fetchone()
    conn.close()
    
    if settlement:
        data = json.loads(settlement['data'])
        return render_template('admin/settlement_view.html', 
                             settlement=settlement, 
                             data=data)
    return redirect(url_for('admin_settlements'))

@app.route('/admin/settlements/export/excel')
@admin_required
def admin_settlements_export_excel():
    """정산관리 엑셀 내보내기"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    if not start_date or not end_date:
        return jsonify({'success': False, 'message': '시작일과 종료일을 입력해주세요.'})
    
    conn = get_db_connection()
    query = '''
        SELECT DATE(er.response_date) as settlement_date, 
               ev.name as evaluator_name,
               COUNT(DISTINCT er.id) as count,
               COUNT(DISTINCT er.id) * 10000 as amount,
               COUNT(DISTINCT er.id) * 1000 as vat,
               COUNT(DISTINCT er.id) * 11000 as total_amount
        FROM evaluation_responses er
        JOIN evaluation_assignments ea ON er.request_id = ea.request_id AND er.evaluator_id = ea.evaluator_id
        JOIN users ev ON er.evaluator_id = ev.id
        WHERE DATE(er.response_date) >= ? AND DATE(er.response_date) <= ?
        GROUP BY DATE(er.response_date), ev.id
        ORDER BY settlement_date, ev.name
    '''
    settlements = conn.execute(query, (start_date, end_date)).fetchall()
    conn.close()
    
    headers = ['일자', '평가사', '건수', '금액', 'VAT', '청구액']
    data = []
    current_date = None
    date_totals = {'count': 0, 'amount': 0, 'vat': 0, 'total_amount': 0}
    grand_totals = {'count': 0, 'amount': 0, 'vat': 0, 'total_amount': 0}
    
    for settlement in settlements:
        settlement_date = settlement['settlement_date']
        
        if current_date != settlement_date:
            if current_date is not None:
                data.append(['소계 (' + current_date + ')', '', date_totals['count'], 
                           date_totals['amount'], date_totals['vat'], date_totals['total_amount']])
                date_totals = {'count': 0, 'amount': 0, 'vat': 0, 'total_amount': 0}
            current_date = settlement_date
        
        data.append([
            settlement_date,
            settlement['evaluator_name'],
            settlement['count'],
            settlement['amount'],
            settlement['vat'],
            settlement['total_amount']
        ])
        
        date_totals['count'] += settlement['count']
        date_totals['amount'] += settlement['amount']
        date_totals['vat'] += settlement['vat']
        date_totals['total_amount'] += settlement['total_amount']
        
        grand_totals['count'] += settlement['count']
        grand_totals['amount'] += settlement['amount']
        grand_totals['vat'] += settlement['vat']
        grand_totals['total_amount'] += settlement['total_amount']
    
    if current_date is not None:
        data.append(['소계 (' + current_date + ')', '', date_totals['count'], 
                   date_totals['amount'], date_totals['vat'], date_totals['total_amount']])
    
    data.append(['합계', '', grand_totals['count'], grand_totals['amount'], 
                grand_totals['vat'], grand_totals['total_amount']])
    
    filename = f'settlements_{start_date}_{end_date}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    export_to_excel(data, headers, filename)
    return send_file(filename, as_attachment=True)

@app.route('/admin/settlements/export/pdf')
@admin_required
def admin_settlements_export_pdf():
    """정산관리 PDF 내보내기"""
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    if not start_date or not end_date:
        return jsonify({'success': False, 'message': '시작일과 종료일을 입력해주세요.'})
    
    conn = get_db_connection()
    query = '''
        SELECT DATE(er.response_date) as settlement_date, 
               ev.name as evaluator_name,
               COUNT(DISTINCT er.id) as count,
               COUNT(DISTINCT er.id) * 10000 as amount,
               COUNT(DISTINCT er.id) * 1000 as vat,
               COUNT(DISTINCT er.id) * 11000 as total_amount
        FROM evaluation_responses er
        JOIN evaluation_assignments ea ON er.request_id = ea.request_id AND er.evaluator_id = ea.evaluator_id
        JOIN users ev ON er.evaluator_id = ev.id
        WHERE DATE(er.response_date) >= ? AND DATE(er.response_date) <= ?
        GROUP BY DATE(er.response_date), ev.id
        ORDER BY settlement_date, ev.name
    '''
    settlements = conn.execute(query, (start_date, end_date)).fetchall()
    conn.close()
    
    headers = ['일자', '평가사', '건수', '금액', 'VAT', '청구액']
    data = []
    current_date = None
    date_totals = {'count': 0, 'amount': 0, 'vat': 0, 'total_amount': 0}
    grand_totals = {'count': 0, 'amount': 0, 'vat': 0, 'total_amount': 0}
    
    for settlement in settlements:
        settlement_date = settlement['settlement_date']
        
        if current_date != settlement_date:
            if current_date is not None:
                data.append(['소계 (' + current_date + ')', '', str(date_totals['count']), 
                           str(date_totals['amount']), str(date_totals['vat']), str(date_totals['total_amount'])])
                date_totals = {'count': 0, 'amount': 0, 'vat': 0, 'total_amount': 0}
            current_date = settlement_date
        
        data.append([
            settlement_date,
            settlement['evaluator_name'],
            str(settlement['count']),
            str(settlement['amount']),
            str(settlement['vat']),
            str(settlement['total_amount'])
        ])
        
        date_totals['count'] += settlement['count']
        date_totals['amount'] += settlement['amount']
        date_totals['vat'] += settlement['vat']
        date_totals['total_amount'] += settlement['total_amount']
        
        grand_totals['count'] += settlement['count']
        grand_totals['amount'] += settlement['amount']
        grand_totals['vat'] += settlement['vat']
        grand_totals['total_amount'] += settlement['total_amount']
    
    if current_date is not None:
        data.append(['소계 (' + current_date + ')', '', str(date_totals['count']), 
                   str(date_totals['amount']), str(date_totals['vat']), str(date_totals['total_amount'])])
    
    data.append(['합계', '', str(grand_totals['count']), str(grand_totals['amount']), 
                str(grand_totals['vat']), str(grand_totals['total_amount'])])
    
    filename = f'settlements_{start_date}_{end_date}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    export_to_pdf(data, headers, filename, title=f"정산관리 ({start_date} ~ {end_date})")
    return send_file(filename, as_attachment=True)

# 검수신청 페이지
@app.route('/inspection/dashboard')
@login_required
def inspection_dashboard():
    """검수신청 대시보드"""
    if session.get('user_type') != '검수신청':
        return redirect(url_for('dashboard'))
    return render_template('inspection/dashboard.html')

@app.route('/inspection/request', methods=['GET', 'POST'])
@login_required
def inspection_request():
    """검수신청 페이지"""
    if session.get('user_type') != '검수신청':
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        data = request.get_json()
        vehicle_number = data.get('vehicle_number')
        lot_number = data.get('lot_number')
        parking_number = data.get('parking_number')
        details = data.get('details', [])
        
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO inspection_requests (user_id, vehicle_number, lot_number, parking_number)
                VALUES (?, ?, ?, ?)
            ''', (session['user_id'], vehicle_number, lot_number, parking_number))
            request_id = cursor.lastrowid
            
            for detail in details:
                cursor.execute('''
                    INSERT INTO inspection_details (request_id, sequence, content)
                    VALUES (?, ?, ?)
                ''', (request_id, detail['sequence'], detail['content']))
            
            conn.commit()
            return jsonify({'success': True, 'message': '검수신청이 완료되었습니다.'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
        finally:
            conn.close()
    
    return render_template('inspection/request.html')

@app.route('/inspection/history')
@login_required
def inspection_history():
    """검수신청내역 페이지"""
    if session.get('user_type') != '검수신청':
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.*,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               er.response_date, er.sent_date,
               GROUP_CONCAT(erd.content, '/') as response_contents
        FROM inspection_requests ir
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        LEFT JOIN evaluation_responses er ON ir.id = er.request_id
        LEFT JOIN evaluation_response_details erd ON er.id = erd.response_id
    '''
    
    conditions = ['ir.user_id = ?']
    params = [session['user_id']]
    
    if start_date:
        conditions.append("DATE(ir.request_date) >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("DATE(ir.request_date) <= ?")
        params.append(end_date)
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    inspections = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('inspection/history.html', 
                         inspections=inspections, 
                         start_date=start_date, 
                         end_date=end_date)

@app.route('/inspection/history/export/excel')
@login_required
def inspection_history_export_excel():
    """검수신청내역 엑셀 내보내기"""
    if session.get('user_type') != '검수신청':
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.request_date, ir.vehicle_number, ir.lot_number, ir.parking_number,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               GROUP_CONCAT(erd.content, '/') as response_contents,
               er.response_date
        FROM inspection_requests ir
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        LEFT JOIN evaluation_responses er ON ir.id = er.request_id
        LEFT JOIN evaluation_response_details erd ON er.id = erd.response_id
    '''
    
    conditions = ['ir.user_id = ?']
    params = [session['user_id']]
    
    if start_date:
        conditions.append("DATE(ir.request_date) >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("DATE(ir.request_date) <= ?")
        params.append(end_date)
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    inspections = conn.execute(query, params).fetchall()
    conn.close()
    
    headers = ['신청일', '차량번호', '출품번호', '주차번호', '검수신청', '평가답변', '답변일']
    data = []
    for row in inspections:
        data.append([
            format_datetime(row['request_date']),
            row['vehicle_number'] or '',
            row['lot_number'] or '',
            row['parking_number'] or '',
            row['inspection_contents'] or '',
            row['response_contents'] or '',
            format_datetime(row['response_date'])
        ])
    
    filename = f'inspection_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    export_to_excel(data, headers, filename)
    return send_file(filename, as_attachment=True)

@app.route('/inspection/history/export/pdf')
@login_required
def inspection_history_export_pdf():
    """검수신청내역 PDF 내보내기"""
    if session.get('user_type') != '검수신청':
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.request_date, ir.vehicle_number, ir.lot_number, ir.parking_number,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               GROUP_CONCAT(erd.content, '/') as response_contents,
               er.response_date
        FROM inspection_requests ir
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        LEFT JOIN evaluation_responses er ON ir.id = er.request_id
        LEFT JOIN evaluation_response_details erd ON er.id = erd.response_id
    '''
    
    conditions = ['ir.user_id = ?']
    params = [session['user_id']]
    
    if start_date:
        conditions.append("DATE(ir.request_date) >= ?")
        params.append(start_date)
    if end_date:
        conditions.append("DATE(ir.request_date) <= ?")
        params.append(end_date)
    
    if conditions:
        query += ' WHERE ' + ' AND '.join(conditions)
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    inspections = conn.execute(query, params).fetchall()
    conn.close()
    
    headers = ['신청일', '차량번호', '출품번호', '주차번호', '검수신청', '평가답변', '답변일']
    data = []
    for row in inspections:
        data.append([
            format_datetime(row['request_date']),
            row['vehicle_number'] or '',
            row['lot_number'] or '',
            row['parking_number'] or '',
            row['inspection_contents'] or '',
            row['response_contents'] or '',
            format_datetime(row['response_date'])
        ])
    
    filename = f'inspection_history_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    export_to_pdf(data, headers, filename, title="검수신청내역")
    return send_file(filename, as_attachment=True)

# 평가사 페이지
@app.route('/evaluator/dashboard')
@login_required
def evaluator_dashboard():
    """평가사 대시보드"""
    if session.get('user_type') != '평가사':
        return redirect(url_for('dashboard'))
    return render_template('evaluator/dashboard.html')

@app.route('/evaluator/status')
@login_required
def evaluator_status():
    """신청현황 페이지"""
    if session.get('user_type') != '평가사':
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.*, 
               COALESCE(ea.status, '신청') as status, 
               ea.id as assignment_id,
               GROUP_CONCAT(id.content, '/') as inspection_contents
        FROM inspection_requests ir
        LEFT JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        WHERE 1=1
    '''
    
    params = []
    if start_date:
        query += ' AND DATE(ir.request_date) >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND DATE(ir.request_date) <= ?'
        params.append(end_date)
    
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    requests = conn.execute(query, params).fetchall()
    
    # 평가사 목록
    evaluators = conn.execute('''
        SELECT id, name FROM users WHERE user_type = '평가사' AND approved = 1
    ''').fetchall()
    
    conn.close()
    
    return render_template('evaluator/status.html', 
                         requests=requests, 
                         evaluators=evaluators,
                         start_date=start_date, 
                         end_date=end_date)

@app.route('/evaluator/status/assign', methods=['POST'])
@login_required
def evaluator_status_assign():
    """평가사 배정"""
    data = request.get_json()
    request_id = data.get('request_id')
    evaluator_id = data.get('evaluator_id')
    evaluator_name = data.get('evaluator_name', '')
    
    conn = get_db_connection()
    try:
        # 평가사 ID 결정
        final_evaluator_id = None
        if evaluator_id:
            final_evaluator_id = evaluator_id
        elif evaluator_name:
            evaluator_user = conn.execute('''
                SELECT id FROM users WHERE name = ? AND user_type = '평가사' AND approved = 1
            ''', (evaluator_name,)).fetchone()
            if evaluator_user:
                final_evaluator_id = evaluator_user['id']
            else:
                return jsonify({'success': False, 'message': '평가사를 찾을 수 없습니다.'})
        else:
            return jsonify({'success': False, 'message': '평가사를 선택하거나 입력해주세요.'})
        
        # 기존 배정 확인
        existing = conn.execute('''
            SELECT id FROM evaluation_assignments WHERE request_id = ?
        ''', (request_id,)).fetchone()
        
        if existing:
            conn.execute('''
                UPDATE evaluation_assignments SET evaluator_id = ?, status = '평가사배정'
                WHERE id = ?
            ''', (final_evaluator_id, existing['id']))
        else:
            conn.execute('''
                INSERT INTO evaluation_assignments (request_id, evaluator_id, status)
                VALUES (?, ?, '평가사배정')
            ''', (request_id, final_evaluator_id))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/evaluator/status/complete', methods=['POST'])
@login_required
def evaluator_status_complete():
    """평가 완료 처리"""
    data = request.get_json()
    assignment_id = data.get('assignment_id')
    
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE evaluation_assignments SET status = '평가완료' WHERE id = ?
        ''', (assignment_id,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/evaluator/status/export/excel')
@login_required
def evaluator_status_export_excel():
    """신청현황 엑셀 내보내기"""
    if session.get('user_type') != '평가사':
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.request_date, ir.vehicle_number, ir.lot_number, ir.parking_number,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               COALESCE(ea.status, '신청') as status,
               ev.name as evaluator_name
        FROM inspection_requests ir
        LEFT JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN users ev ON ea.evaluator_id = ev.id
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        WHERE 1=1
    '''
    
    params = []
    if start_date:
        query += ' AND DATE(ir.request_date) >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND DATE(ir.request_date) <= ?'
        params.append(end_date)
    
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    requests = conn.execute(query, params).fetchall()
    conn.close()
    
    headers = ['구분', '신청일', '차량번호', '출품번호', '주차번호', '검수신청', '평가사입력']
    data = []
    for row in requests:
        data.append([
            row['status'],
            format_datetime(row['request_date']),
            row['vehicle_number'] or '',
            row['lot_number'] or '',
            row['parking_number'] or '',
            row['inspection_contents'] or '',
            row['evaluator_name'] or ''
        ])
    
    filename = f'evaluator_status_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    export_to_excel(data, headers, filename)
    return send_file(filename, as_attachment=True)

@app.route('/evaluator/status/export/pdf')
@login_required
def evaluator_status_export_pdf():
    """신청현황 PDF 내보내기"""
    if session.get('user_type') != '평가사':
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.request_date, ir.vehicle_number, ir.lot_number, ir.parking_number,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               COALESCE(ea.status, '신청') as status,
               ev.name as evaluator_name
        FROM inspection_requests ir
        LEFT JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN users ev ON ea.evaluator_id = ev.id
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        WHERE 1=1
    '''
    
    params = []
    if start_date:
        query += ' AND DATE(ir.request_date) >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND DATE(ir.request_date) <= ?'
        params.append(end_date)
    
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    requests = conn.execute(query, params).fetchall()
    conn.close()
    
    headers = ['구분', '신청일', '차량번호', '출품번호', '주차번호', '검수신청', '평가사입력']
    data = []
    for row in requests:
        data.append([
            row['status'],
            format_datetime(row['request_date']),
            row['vehicle_number'] or '',
            row['lot_number'] or '',
            row['parking_number'] or '',
            row['inspection_contents'] or '',
            row['evaluator_name'] or ''
        ])
    
    filename = f'evaluator_status_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    export_to_pdf(data, headers, filename, title="신청현황")
    return send_file(filename, as_attachment=True)

@app.route('/evaluator/response')
@login_required
def evaluator_response():
    """평가답변 페이지"""
    if session.get('user_type') != '평가사':
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.*, ea.id as assignment_id,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               er.id as response_id, er.response_date, er.confirmed
        FROM inspection_requests ir
        JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        LEFT JOIN evaluation_responses er ON ir.id = er.request_id AND er.evaluator_id = ea.evaluator_id
        WHERE ea.evaluator_id = ?
    '''
    
    params = [session['user_id']]
    if start_date:
        query += ' AND DATE(ir.request_date) >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND DATE(ir.request_date) <= ?'
        params.append(end_date)
    
    query += ' GROUP BY ir.id, ea.id ORDER BY ir.request_date DESC'
    
    requests = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('evaluator/response.html', 
                         requests=requests, 
                         start_date=start_date, 
                         end_date=end_date)

@app.route('/evaluator/response/<int:request_id>')
@login_required
def evaluator_response_form(request_id):
    """평가답변 입력 폼"""
    if session.get('user_type') != '평가사':
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    request_info = conn.execute('''
        SELECT ir.* FROM inspection_requests ir
        JOIN evaluation_assignments ea ON ir.id = ea.request_id
        WHERE ir.id = ? AND ea.evaluator_id = ?
    ''', (request_id, session['user_id'])).fetchone()
    
    if not request_info:
        conn.close()
        return redirect(url_for('evaluator_response'))
    
    inspection_details = conn.execute('''
        SELECT * FROM inspection_details WHERE request_id = ? ORDER BY sequence
    ''', (request_id,)).fetchall()
    
    response = conn.execute('''
        SELECT * FROM evaluation_responses WHERE request_id = ? AND evaluator_id = ?
    ''', (request_id, session['user_id'])).fetchone()
    
    response_details = []
    if response:
        response_details = conn.execute('''
            SELECT * FROM evaluation_response_details WHERE response_id = ? ORDER BY sequence
        ''', (response['id'],)).fetchall()
    
    conn.close()
    
    return render_template('evaluator/response_form.html', 
                         request_info=request_info,
                         inspection_details=inspection_details,
                         response=response,
                         response_details=response_details)

@app.route('/evaluator/response/save', methods=['POST'])
@login_required
def evaluator_response_save():
    """평가답변 저장"""
    data = request.get_json()
    request_id = data.get('request_id')
    details = data.get('details', [])
    
    conn = get_db_connection()
    try:
        # 기존 답변 확인
        existing_response = conn.execute('''
            SELECT id FROM evaluation_responses 
            WHERE request_id = ? AND evaluator_id = ?
        ''', (request_id, session['user_id'])).fetchone()
        
        if existing_response:
            response_id = existing_response['id']
            # 기존 상세내역 삭제
            conn.execute('DELETE FROM evaluation_response_details WHERE response_id = ?', (response_id,))
            # 답변일 업데이트
            conn.execute('''
                UPDATE evaluation_responses SET response_date = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (response_id,))
        else:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO evaluation_responses (request_id, evaluator_id, response_date)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (request_id, session['user_id']))
            response_id = cursor.lastrowid
        
        # 상세내역 저장
        for detail in details:
            conn.execute('''
                INSERT INTO evaluation_response_details (response_id, sequence, content, note)
                VALUES (?, ?, ?, ?)
            ''', (response_id, detail['sequence'], detail['content'], detail.get('note', '')))
        
        conn.commit()
        return jsonify({'success': True, 'message': '답변이 저장되었습니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/evaluator/response/confirm', methods=['POST'])
@login_required
def evaluator_response_confirm():
    """평가답변 확정"""
    data = request.get_json()
    request_id = data.get('request_id')
    
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE evaluation_responses SET confirmed = 1
            WHERE request_id = ? AND evaluator_id = ?
        ''', (request_id, session['user_id']))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        conn.close()

@app.route('/evaluator/response/export/excel')
@login_required
def evaluator_response_export_excel():
    """평가답변 엑셀 내보내기"""
    if session.get('user_type') != '평가사':
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.request_date, ir.vehicle_number, ir.lot_number, ir.parking_number,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               GROUP_CONCAT(erd.content, '/') as response_contents,
               er.response_date, er.confirmed
        FROM inspection_requests ir
        JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        LEFT JOIN evaluation_responses er ON ir.id = er.request_id AND er.evaluator_id = ea.evaluator_id
        LEFT JOIN evaluation_response_details erd ON er.id = erd.response_id
        WHERE ea.evaluator_id = ?
    '''
    
    params = [session['user_id']]
    if start_date:
        query += ' AND DATE(ir.request_date) >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND DATE(ir.request_date) <= ?'
        params.append(end_date)
    
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    requests = conn.execute(query, params).fetchall()
    conn.close()
    
    headers = ['신청일', '차량번호', '출품번호', '주차번호', '검수신청내역', '평가답변', '답변일', '확정여부']
    data = []
    for row in requests:
        data.append([
            format_datetime(row['request_date']),
            row['vehicle_number'] or '',
            row['lot_number'] or '',
            row['parking_number'] or '',
            row['inspection_contents'] or '',
            row['response_contents'] or '',
            format_datetime(row['response_date']),
            '확정' if row['confirmed'] else '미확정'
        ])
    
    filename = f'evaluator_response_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    export_to_excel(data, headers, filename)
    return send_file(filename, as_attachment=True)

@app.route('/evaluator/response/export/pdf')
@login_required
def evaluator_response_export_pdf():
    """평가답변 PDF 내보내기"""
    if session.get('user_type') != '평가사':
        return redirect(url_for('dashboard'))
    
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    conn = get_db_connection()
    query = '''
        SELECT ir.request_date, ir.vehicle_number, ir.lot_number, ir.parking_number,
               GROUP_CONCAT(id.content, '/') as inspection_contents,
               GROUP_CONCAT(erd.content, '/') as response_contents,
               er.response_date, er.confirmed
        FROM inspection_requests ir
        JOIN evaluation_assignments ea ON ir.id = ea.request_id
        LEFT JOIN inspection_details id ON ir.id = id.request_id
        LEFT JOIN evaluation_responses er ON ir.id = er.request_id AND er.evaluator_id = ea.evaluator_id
        LEFT JOIN evaluation_response_details erd ON er.id = erd.response_id
        WHERE ea.evaluator_id = ?
    '''
    
    params = [session['user_id']]
    if start_date:
        query += ' AND DATE(ir.request_date) >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND DATE(ir.request_date) <= ?'
        params.append(end_date)
    
    query += ' GROUP BY ir.id ORDER BY ir.request_date DESC'
    
    requests = conn.execute(query, params).fetchall()
    conn.close()
    
    headers = ['신청일', '차량번호', '출품번호', '주차번호', '검수신청내역', '평가답변', '답변일', '확정여부']
    data = []
    for row in requests:
        data.append([
            format_datetime(row['request_date']),
            row['vehicle_number'] or '',
            row['lot_number'] or '',
            row['parking_number'] or '',
            row['inspection_contents'] or '',
            row['response_contents'] or '',
            format_datetime(row['response_date']),
            '확정' if row['confirmed'] else '미확정'
        ])
    
    filename = f'evaluator_response_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
    export_to_pdf(data, headers, filename, title="평가답변")
    return send_file(filename, as_attachment=True)

@app.route('/api/translate', methods=['POST'])
@login_required
def api_translate():
    """번역 API"""
    data = request.get_json()
    text = data.get('text', '')
    target = data.get('target', 'ja')
    
    try:
        translated = translate_to_japanese(text)
        return jsonify({'success': True, 'translated': translated})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/dashboard')
@login_required
def dashboard():
    """일반 대시보드 (권한에 따라 리다이렉트)"""
    user_type = session.get('user_type')
    if user_type == '관리자':
        return redirect(url_for('admin_dashboard'))
    elif user_type == '검수신청':
        return redirect(url_for('inspection_dashboard'))
    elif user_type == '평가사':
        return redirect(url_for('evaluator_dashboard'))
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 2000))
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1' or os.environ.get('FLASK_ENV') == 'development'
    app.debug = debug_mode
    print(f"Flask 애플리케이션 시작 - 포트: {port}, 디버그 모드: {debug_mode}, DB 경로: {DB_PATH}")
    app.run(debug=debug_mode, host='0.0.0.0', port=port)

