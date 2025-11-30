"""
유틸리티 함수 (엑셀, PDF, 번역, 이메일 등)
"""
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from googletrans import Translator
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def export_to_excel(data, headers, filename):
    """데이터를 엑셀 파일로 내보내기"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    
    # 헤더 스타일
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF", size=11)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # 헤더 작성
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = border
    
    # 데이터 작성
    for row_idx, row_data in enumerate(data, 2):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.border = border
            cell.alignment = Alignment(horizontal='left', vertical='center')
    
    # 열 너비 자동 조정
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[col_letter].width = adjusted_width
    
    wb.save(filename)
    return filename

def export_to_pdf(data, headers, filename, title="위카아라이 진단시스템"):
    """데이터를 PDF 파일로 내보내기"""
    doc = SimpleDocTemplate(filename, pagesize=A4)
    elements = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#366092'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    # 제목
    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.2*inch))
    
    # 테이블 데이터 준비
    table_data = [headers] + data
    
    # 테이블 생성
    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#366092')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    
    elements.append(table)
    
    doc.build(elements)
    return filename

def translate_to_japanese(text):
    """텍스트를 일본어로 번역"""
    try:
        translator = Translator()
        result = translator.translate(text, src='ko', dest='ja')
        return result.text
    except Exception as e:
        print(f"번역 오류: {e}")
        return text

def format_datetime(dt):
    """날짜시간 포맷팅"""
    if dt is None:
        return ""
    if isinstance(dt, str):
        return dt
    return dt.strftime('%Y-%m-%d %H:%M:%S')

def format_date(d):
    """날짜 포맷팅"""
    if d is None:
        return ""
    if isinstance(d, str):
        return d
    return d.strftime('%Y-%m-%d')

def send_email(to_email, subject, body_html, body_text=None):
    """이메일 전송"""
    try:
        smtp_server = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
        smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        smtp_user = os.environ.get('SMTP_USER', '')
        smtp_password = os.environ.get('SMTP_PASSWORD', '')
        
        # 테스트 모드: 실제 이메일 전송 대신 로그만 출력
        test_mode = os.environ.get('EMAIL_TEST_MODE', 'true').lower() == 'true'
        
        if test_mode:
            print("=" * 50)
            print("📧 이메일 전송 (테스트 모드)")
            print(f"수신자: {to_email}")
            print(f"제목: {subject}")
            print(f"발신자: {smtp_user or 'wecarmobility@example.com'}")
            print("-" * 30)
            print("내용:")
            # HTML 태그 제거하여 간단히 표시
            import re
            clean_text = re.sub('<[^<]+?>', '', body_html)
            print(clean_text[:500] + "..." if len(clean_text) > 500 else clean_text)
            print("=" * 50)
            return True
        
        if not smtp_user or not smtp_password:
            error_msg = "이메일 설정이 없습니다. 환경변수 SMTP_USER, SMTP_PASSWORD를 설정해주세요."
            print(error_msg)
            raise ValueError(error_msg)
        
        if not to_email:
            error_msg = "수신자 이메일 주소가 없습니다."
            print(error_msg)
            raise ValueError(error_msg)
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = to_email
        
        if body_text:
            part1 = MIMEText(body_text, 'plain', 'utf-8')
            msg.attach(part1)
        
        part2 = MIMEText(body_html, 'html', 'utf-8')
        msg.attach(part2)
        
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        
        print(f"이메일 전송 성공: {to_email}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"이메일 인증 실패: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    except smtplib.SMTPException as e:
        error_msg = f"SMTP 오류: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"이메일 전송 오류: {str(e)}"
        print(error_msg)
        raise Exception(error_msg)


