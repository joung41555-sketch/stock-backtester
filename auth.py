import sqlite3
import hashlib
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st

# SQLite DB 경로 설정 (어떤 환경에서도 항상 동일한 절대 경로 유지)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")
# 보안 강화를 위한 솔트(Salt) 값 설정
PASSWORD_SALT = "antigravity-secure-salt-2026!#"

# 듀얼 SMTP 설정 로딩 (보안 연동)
try:
    GMAIL_USER = st.secrets.get("GMAIL_USER") or st.secrets.get("gmail_user") or ""
    GMAIL_PASSWORD = st.secrets.get("GMAIL_PASSWORD") or st.secrets.get("gmail_password") or ""
    
    NAVER_USER = st.secrets.get("NAVER_USER") or st.secrets.get("naver_user") or ""
    NAVER_PASSWORD = st.secrets.get("NAVER_PASSWORD") or st.secrets.get("naver_password") or ""
except Exception:
    GMAIL_USER = GMAIL_PASSWORD = NAVER_USER = NAVER_PASSWORD = ""

def get_smtp_config(email):
    """이메일 주소 도메인을 분석해 알맞은 SMTP 서버 정보와 포트, SSL 여부를 반환"""
    email_lower = email.strip().lower()
    if "@naver.com" in email_lower:
        return "smtp.naver.com", 465, True  # 네이버는 SSL 465가 정석
    elif "@gmail.com" in email_lower:
        return "smtp.gmail.com", 587, False  # 지메일은 TLS 587
    elif "@daum.net" in email_lower or "@hanmail.net" in email_lower:
        return "smtp.daum.net", 465, True  # 다음/한메일은 SSL 465
    else:
        # 기타 기본값은 Gmail 규격으로 적용
        return "smtp.gmail.com", 587, False

def _execute_send_email(smtp_user, smtp_password, to_email, subject, html_body):
    """특정 SMTP 계정 정보로 메일 발송 처리하는 내부 함수 (포트 및 SSL/TLS 자동 매칭)"""
    smtp_server, smtp_port, use_ssl = get_smtp_config(smtp_user)
    msg = MIMEMultipart()
    msg['From'] = f"Dynamic Stock Backtester <{smtp_user}>"
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))
    
    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(smtp_user, smtp_password)
    else:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        
    server.sendmail(smtp_user, to_email, msg.as_string())
    server.quit()

def dispatch_email(to_email, subject, html_body, demo_fallback_value):
    """활성화된 모든 SMTP 계정(구글 -> 네이버 순)을 차례로 시도하여 발송 완료 (하나라도 성공 시 성공 리포트)"""
    senders = []
    if GMAIL_USER.strip() and GMAIL_PASSWORD.strip():
        senders.append((GMAIL_USER, GMAIL_PASSWORD))
    if NAVER_USER.strip() and NAVER_PASSWORD.strip():
        senders.append((NAVER_USER, NAVER_PASSWORD))
        
    # 등록된 발송 계정이 전혀 없는 경우 데모 모드로 폴백
    if not senders:
        return False, f"[데모 모드] 이메일 계정이 설정되지 않았습니다. 임시 인증번호는 {demo_fallback_value} 입니다."
        
    last_error = ""
    for user, password in senders:
        try:
            _execute_send_email(user, password, to_email, subject, html_body)
            return True, f"{to_email} 주소로 이메일 안내가 발송되었습니다!"
        except Exception as e:
            last_error = f"계정 {user} 발송 실패: {e}"
            # 이 계정이 실패하면 루프를 돌아 다음 예비 계정으로 즉시 재시도
            continue
            
    # 모든 활성 계정이 발송에 실패한 경우
    return False, f"등록된 모든 발송 메일 계정의 시도가 실패했습니다. 마지막 오류: {last_error}"

def init_db():
    """데이터베이스 초기화 및 테이블 생성, 필요한 컬럼 마이그레이션"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 이메일 컬럼(email)이 존재하는지 확인하고 없으면 자동 생성 (마이그레이션)
    cursor.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'email' not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
        
    conn.commit()
    conn.close()

def hash_password(password):
    """비밀번호에 솔트를 추가하여 SHA-256 해시값 생성"""
    salted = password + PASSWORD_SALT
    return hashlib.sha256(salted.encode('utf-8')).hexdigest()

def send_verification_email(to_email, code):
    """인증 메일 발송 (듀얼 SMTP 폴백 엔진 적용)"""
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0F172A; color: #F8FAFC; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background-color: #1E293B; border-radius: 12px; padding: 30px; border: 1px solid #334155;">
            <h2 style="color: #FF4B4B; text-align: center;">📈 Dynamic Stock Backtester</h2>
            <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
            <p>안녕하세요. 서비스 가입을 진행해 주셔서 감사합니다.</p>
            <p>가입 인증을 완료하기 위해 아래 6자리 인증 코드를 사이트 화면에 입력해 주세요.</p>
            <div style="background-color: #0F172A; border: 1px solid #FF4B4B; color: #FF4B4B; font-size: 24px; font-weight: 700; padding: 15px; border-radius: 8px; text-align: center; letter-spacing: 5px; margin: 25px 0;">
                {code}
            </div>
            <p style="font-size: 12px; color: #94A3B8; text-align: center; margin-top: 30px;">본 메일은 시스템 발신 전용 메일입니다.</p>
        </div>
    </body>
    </html>
    """
    return dispatch_email(to_email, "[Dynamic Stock Backtester] 회원가입 이메일 인증번호", html_body, code)

def register_user(username, password, email):
    """신규 회원가입 처리 (이메일 추가)"""
    init_db()  # DB 초기화 보장
    
    username = username.strip()
    password = password.strip()
    email = email.strip()
    
    if not username or not password or not email:
        return False, "아이디, 비밀번호, 이메일을 모두 입력해 주세요."
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 아이디 중복 여부 확인
        cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return False, "이미 존재하는 아이디입니다."
        
        # 비밀번호 암호화 후 가입 처리 (이메일 컬럼 포함)
        hashed_pwd = hash_password(password)
        cursor.execute("INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)", (username, hashed_pwd, email))
        conn.commit()
        return True, "회원가입이 완료되었습니다! 로그인해 주세요."
    except Exception as e:
        return False, f"오류가 발생했습니다: {e}"
    finally:
        conn.close()

def verify_user(username, password):
    """로그인 검증 (아이디/비밀번호 확인)"""
    init_db()  # DB 초기화 보장
    
    username = username.strip()
    password = password.strip()
    
    if not username or not password:
        return False
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        hashed_pwd = hash_password(password)
        cursor.execute("SELECT username FROM users WHERE username = ? AND password_hash = ?", (username, hashed_pwd))
        user = cursor.fetchone()
        return user is not None
    except Exception as e:
        return False
    finally:
        conn.close()

def get_all_users():
    """관리자용: 가입된 모든 유저 목록 조회"""
    init_db()  # DB 초기화 보장
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username, email, created_at FROM users ORDER BY created_at DESC")
        return cursor.fetchall()
    except Exception:
        return []
    finally:
        conn.close()

def find_id_by_email(email):
    """이메일로 가입된 아이디 찾기"""
    init_db()
    email = email.strip()
    if not email:
        return None
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username FROM users WHERE email = ?", (email,))
        rows = cursor.fetchall()
        if rows:
            return [row[0] for row in rows]
        return None
    except Exception:
        return None
    finally:
        conn.close()

def reset_to_temp_password(username, email, temp_password):
    """비밀번호 재설정: 아이디와 이메일이 일치하면 임시 비밀번호 해시로 업데이트"""
    init_db()
    username = username.strip()
    email = email.strip()
    
    if not username or not email or not temp_password:
        return False, "정보가 올바르지 않습니다."
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT username FROM users WHERE username = ? AND email = ?", (username, email))
        if not cursor.fetchone():
            return False, "입력하신 아이디와 이메일 정보가 일치하는 회원이 없습니다."
        
        hashed_pwd = hash_password(temp_password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE username = ? AND email = ?", (hashed_pwd, username, email))
        conn.commit()
        return True, "임시 비밀번호로 재설정이 완료되었습니다."
    except Exception as e:
        return False, f"오류가 발생했습니다: {e}"
    finally:
        conn.close()

def send_account_info_email(to_email, subject, content_title, content_desc, value_to_highlight):
    """사용자 계정 정보 안내 메일 발송 (듀얼 SMTP 폴백 엔진 적용)"""
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #0F172A; color: #F8FAFC; padding: 20px;">
        <div style="max-width: 500px; margin: 0 auto; background-color: #1E293B; border-radius: 12px; padding: 30px; border: 1px solid #334155;">
            <h2 style="color: #FF4B4B; text-align: center;">📈 Dynamic Stock Backtester</h2>
            <hr style="border: 0; border-top: 1px solid #334155; margin: 20px 0;">
            <p>안녕하세요. 요청하신 계정 찾기 서비스 안내 메일입니다.</p>
            <p>{content_title}</p>
            <div style="background-color: #0F172A; border: 1px solid #FF4B4B; color: #FF4B4B; font-size: 20px; font-weight: 700; padding: 15px; border-radius: 8px; text-align: center; margin: 25px 0;">
                {value_to_highlight}
            </div>
            <p>{content_desc}</p>
            <p style="font-size: 12px; color: #94A3B8; text-align: center; margin-top: 30px;">본 메일은 시스템 발신 전용 메일입니다.</p>
        </div>
    </body>
    </html>
    """
    return dispatch_email(to_email, f"계정 정보 안내 - {subject}", html_body, value_to_highlight)

def delete_user(username):
    """관리자용: 특정 사용자 계정 삭제(강제 탈퇴) - 공백/대소문자 완벽 무시 매칭"""
    init_db()
    username = username.strip()
    if not username:
        return False, "아이디가 올바르지 않습니다."
    
    # admin 계정은 본인이므로 삭제 방지 보안 처리
    if username.lower() == "admin":
        return False, "관리자(admin) 계정은 삭제할 수 없습니다."
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # 데이터베이스 내부의 아이디 앞뒤 공백(TRIM)과 대소문자를 모두 지우고 완벽하게 확인
        cursor.execute("SELECT username FROM users WHERE TRIM(username) = TRIM(?) COLLATE NOCASE", (username,))
        if not cursor.fetchone():
            return False, "존재하지 않는 회원입니다."
            
        cursor.execute("DELETE FROM users WHERE TRIM(username) = TRIM(?) COLLATE NOCASE", (username,))
        conn.commit()
        return True, f"회원 '{username}' 계정이 성공적으로 탈퇴 처리되었습니다."
    except Exception as e:
        return False, f"오류가 발생했습니다: {e}"
    finally:
        conn.close()
