import sqlite3
import hashlib
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import streamlit as st
from datetime import datetime, timedelta
import secrets
import re

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

# ☁️ Supabase Cloud DB 하이브리드 연동
try:
    from supabase import create_client, Client
    SUPABASE_URL = st.secrets.get("SUPABASE_URL") or st.secrets.get("supabase_url") or ""
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or st.secrets.get("supabase_key") or ""
    if SUPABASE_URL.strip() and SUPABASE_KEY.strip():
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        USE_SUPABASE = True
    else:
        USE_SUPABASE = False
except Exception:
    USE_SUPABASE = False

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
    
    # 타임아웃을 반드시 지정: 미지정 시 네트워크/포트 차단 상황에서 무한 대기(앱 전체 무한로딩)에 빠짐
    SMTP_TIMEOUT_SECONDS = 10

    if use_ssl:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=SMTP_TIMEOUT_SECONDS)
    else:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=SMTP_TIMEOUT_SECONDS)

    try:
        if not use_ssl:
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, to_email, msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass

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

_DB_INIT_DONE = False  # 매 rerun마다 파일 I/O를 반복하지 않도록 프로세스 내 1회만 초기화

def init_db():
    """데이터베이스 초기화 및 테이블 생성, 필요한 컬럼 마이그레이션 (SQLite용 예비 엔진)"""
    global _DB_INIT_DONE
    if USE_SUPABASE:
        try:
            hashed_admin = hash_password("kosign037!")
            supabase_client.table("users").upsert({
                "username": "admin",
                "password_hash": hashed_admin,
                "email": "joung41555@gmail.com"
            }).execute()
        except Exception:
            pass
        return  # Supabase 모드 사용 시 SQLite 초기화 건너뜀
    if _DB_INIT_DONE:
        return

    # 🔧 여기서 예외가 나면 예전엔 앱 전체가 매 rerun마다 크래시 → 무한 재시작 루프로 보였음.
    # 실패해도 앱은 계속 뜨게 하고, 화면에 원인을 보여주도록 변경.
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 회원 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 세션 자동 로그인 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL
            )
        """)

        # 실시간 보유 자산 영구 보관 테이블 생성 (계정별 고유 자산)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_portfolios (
                username TEXT,
                ticker TEXT,
                buy_price REAL,
                shares REAL,
                PRIMARY KEY (username, ticker)
            )
        """)

        # 이메일 컬럼(email)이 존재하는지 확인하고 없으면 자동 생성 (마이그레이션)
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'email' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")

        # admin 계정 로컬 생성 (비밀번호 강제 동기화)
        hashed_admin = hash_password("kosign037!")
        cursor.execute("INSERT OR REPLACE INTO users (username, password_hash, email) VALUES ('admin', ?, 'joung41555@gmail.com')", (hashed_admin,))

        conn.commit()
        conn.close()
        _DB_INIT_DONE = True
    except Exception as e:
        try:
            st.error(f"⚠️ 로컬 DB 초기화 실패 (DB_PATH: {DB_PATH}): {e}")
        except Exception:
            pass
        # 초기화 실패 시에도 앱이 죽지 않도록 여기서 예외를 삼킴

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


def check_username_exists(username):
    """아이디 중복 여부를 대소문자 무관하게 검사 (존재하면 True, 없으면 False)"""
    username = username.strip()
    if not username:
        return True
    if username.lower() == "admin":
        return True
        
    if USE_SUPABASE:
        try:
            res = supabase_client.table("users").select("username").ilike("username", username).execute()
            return len(res.data) > 0
        except Exception:
            return True
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT username FROM users WHERE LOWER(username) = LOWER(?)", (username,))
            return cursor.fetchone() is not None
        except Exception:
            return True
        finally:
            conn.close()

def check_email_exists(email):
    """이메일 중복 여부를 대소문자 무관하게 검사 (존재하면 True, 없으면 False)"""
    email = email.strip()
    if not email:
        return True
        
    if USE_SUPABASE:
        try:
            res = supabase_client.table("users").select("email").ilike("email", email).execute()
            return len(res.data) > 0
        except Exception:
            return True
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT email FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            return cursor.fetchone() is not None
        except Exception:
            return True
        finally:
            conn.close()

def register_user(username, password, email):
    """신규 회원가입 처리 (이메일 추가, Supabase/SQLite 하이브리드 지원)"""
    username = username.strip()
    password = password.strip()
    email = email.strip()
    
    if not username or not password or not email:
        return False, "아이디, 비밀번호, 이메일을 모두 입력해 주세요."
        
    if username.lower() == "admin":
        return False, "관리자 아이디('admin')로는 추가 회원가입이 불가능합니다."
        
    hashed_pwd = hash_password(password)

    if USE_SUPABASE:
        try:
            # 1. ID 중복 확인 (대소문자 무관)
            res = supabase_client.table("users").select("username").ilike("username", username).execute()
            if res.data:
                return False, "이미 존재하는 아이디입니다."
            
            # 2. 이메일 중복 확인 (대소문자 무관)
            res_email = supabase_client.table("users").select("email").ilike("email", email).execute()
            if res_email.data:
                return False, "이미 등록된 이메일 주소입니다."
            
            # 신규 삽입
            supabase_client.table("users").insert({
                "username": username,
                "password_hash": hashed_pwd,
                "email": email
            }).execute()
            return True, "회원가입이 완료되었습니다! 로그인해 주세요."
        except Exception as e:
            return False, f"클라우드 DB 오류: {e}"
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            # 1. ID 중복 확인 (대소문자 무관)
            cursor.execute("SELECT username FROM users WHERE LOWER(username) = LOWER(?)", (username,))
            if cursor.fetchone():
                return False, "이미 존재하는 아이디입니다."
            
            # 2. 이메일 중복 확인 (대소문자 무관)
            cursor.execute("SELECT email FROM users WHERE LOWER(email) = LOWER(?)", (email,))
            if cursor.fetchone():
                return False, "이미 등록된 이메일 주소입니다."
            
            cursor.execute("INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)", (username, hashed_pwd, email))
            conn.commit()
            return True, "회원가입이 완료되었습니다! 로그인해 주세요."
        except Exception as e:
            return False, f"로컬 DB 오류: {e}"
        finally:
            conn.close()

def verify_user(username, password):
    """로그인 검증 (아이디/비밀번호 확인, Supabase/SQLite 하이브리드 지원)"""
    username = username.strip()
    password = password.strip()
    
    if not username or not password:
        return False
        
    hashed_pwd = hash_password(password)

    if USE_SUPABASE:
        try:
            res = supabase_client.table("users").select("username").eq("username", username).eq("password_hash", hashed_pwd).execute()
            return len(res.data) > 0
        except Exception:
            return False
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT username FROM users WHERE username = ? AND password_hash = ?", (username, hashed_pwd))
            user = cursor.fetchone()
            return user is not None
        except Exception:
            return False
        finally:
            conn.close()

def get_all_users():
    """관리자용: 가입된 모든 유저 목록 조회 (Supabase/SQLite 하이브리드 지원)"""
    if USE_SUPABASE:
        try:
            res = supabase_client.table("users").select("username, email, created_at").order("created_at", desc=True).execute()
            return [(item["username"], item["email"], item["created_at"]) for item in res.data]
        except Exception:
            return []
    else:
        init_db()
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
    """이메일로 가입된 아이디 찾기 (Supabase/SQLite 하이브리드 지원)"""
    email = email.strip()
    if not email:
        return None
    
    if USE_SUPABASE:
        try:
            res = supabase_client.table("users").select("username").eq("email", email).execute()
            if res.data:
                return [item["username"] for item in res.data]
            return None
        except Exception:
            return None
    else:
        init_db()
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
    """비밀번호 재설정 (Supabase/SQLite 하이브리드 지원)"""
    username = username.strip()
    email = email.strip()
    
    if not username or not email or not temp_password:
        return False, "정보가 올바르지 않습니다."
        
    hashed_pwd = hash_password(temp_password)

    if USE_SUPABASE:
        try:
            res = supabase_client.table("users").select("username").eq("username", username).eq("email", email).execute()
            if not res.data:
                return False, "입력하신 아이디와 이메일 정보가 일치하는 회원이 없습니다."
            
            supabase_client.table("users").update({"password_hash": hashed_pwd}).eq("username", username).eq("email", email).execute()
            return True, "임시 비밀번호로 재설정이 완료되었습니다."
        except Exception as e:
            return False, f"클라우드 DB 오류: {e}"
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT username FROM users WHERE username = ? AND email = ?", (username, email))
            if not cursor.fetchone():
                return False, "입력하신 아이디와 이메일 정보가 일치하는 회원이 없습니다."
            
            cursor.execute("UPDATE users SET password_hash = ? WHERE username = ? AND email = ?", (hashed_pwd, username, email))
            conn.commit()
            return True, "임시 비밀번호로 재설정이 완료되었습니다."
        except Exception as e:
            return False, f"로컬 DB 오류: {e}"
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
    """관리자용: 특정 사용자 계정 삭제 (Supabase/SQLite 하이브리드 지원)"""
    username = username.strip()
    if not username:
        return False, "아이디가 올바르지 않습니다."
    
    if username.lower() == "admin":
        return False, "관리자(admin) 계정은 삭제할 수 없습니다."
        
    if USE_SUPABASE:
        try:
            # 대소문자 무관하게 계정 조회
            res = supabase_client.table("users").select("username").ilike("username", username).execute()
            if not res.data:
                return False, "존재하지 않는 회원입니다."
            
            target_user = res.data[0]["username"]
            supabase_client.table("users").delete().eq("username", target_user).execute()
            supabase_client.table("sessions").delete().eq("username", target_user).execute()
            supabase_client.table("user_portfolios").delete().eq("username", target_user).execute()
            return True, f"회원 '{username}' 계정이 성공적으로 탈퇴 처리되었습니다."
        except Exception as e:
            return False, f"클라우드 DB 오류: {e}"
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT username FROM users WHERE TRIM(username) = TRIM(?) COLLATE NOCASE", (username,))
            if not cursor.fetchone():
                return False, "존재하지 않는 회원입니다."
                
            cursor.execute("DELETE FROM users WHERE TRIM(username) = TRIM(?) COLLATE NOCASE", (username,))
            cursor.execute("DELETE FROM sessions WHERE username = ? COLLATE NOCASE", (username,))
            cursor.execute("DELETE FROM user_portfolios WHERE username = ? COLLATE NOCASE", (username,))
            conn.commit()
            return True, f"회원 '{username}' 계정이 성공적으로 탈퇴 처리되었습니다."
        except Exception as e:
            return False, f"로컬 DB 오류: {e}"
        finally:
            conn.close()

def is_valid_username(username):
    """아이디 유효성 검사: 3~15자의 영문, 숫자, 언더바(_)만 허용"""
    username = username.strip()
    if not (3 <= len(username) <= 15):
        return False
    pattern = r"^[a-zA-Z0-9_]+$"
    return bool(re.match(pattern, username))

def is_strong_password(password):
    """비밀번호 안전성 검사: 최소 8자 이상, 영문/숫자/특수문자 필수 포함"""
    if len(password) < 8:
        return False, "비밀번호는 최소 8자 이상이어야 합니다."
        
    has_letter = any(c.isalpha() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_special = any(c in "!@#$%^&*()_+-=" for c in password)
    
    if not has_letter:
        return False, "비밀번호에 영문자가 최소 1개 이상 포함되어야 합니다."
    if not has_digit:
        return False, "비밀번호에 숫자가 최소 1개 이상 포함되어야 합니다."
    if not has_special:
        return False, "비밀번호에 특수문자(!@#$%^&*()_+-=)가 최소 1개 이상 포함되어야 합니다."
        
    return True, "안전한 비밀번호입니다."

def create_session(username):
    """새로운 세션 생성 및 DB 저장 (유효 기간: 2일, Supabase/SQLite 하이브리드)"""
    username = username.strip()
    token = secrets.token_hex(16)  # 32자리 헥사 스트링 생성
    
    if USE_SUPABASE:
        expires_at = (datetime.now() + timedelta(days=2)).isoformat()
        try:
            supabase_client.table("sessions").insert({
                "token": token,
                "username": username,
                "expires_at": expires_at
            }).execute()
            return token
        except Exception:
            return None
    else:
        init_db()
        expires_at = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO sessions (token, username, expires_at) VALUES (?, ?, ?)", (token, username, expires_at))
            conn.commit()
            return token
        except Exception:
            return None
        finally:
            conn.close()

def verify_session_token(token):
    """세션 토큰 유효성 검사 (Supabase/SQLite 하이브리드 지원)"""
    token = token.strip()
    if not token:
        return None
        
    if USE_SUPABASE:
        try:
            res = supabase_client.table("sessions").select("username, expires_at").eq("token", token).execute()
            if res.data:
                username = res.data[0]["username"]
                expires_at_str = res.data[0]["expires_at"]
                
                try:
                    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                except ValueError:
                    expires_at = datetime.strptime(expires_at_str[:19], '%Y-%m-%d %H:%M:%S')
                    
                if expires_at.tzinfo is not None:
                    expires_at = expires_at.replace(tzinfo=None)
                    
                if datetime.now() < expires_at:
                    return username
                else:
                    supabase_client.table("sessions").delete().eq("token", token).execute()
            return None
        except Exception:
            return None
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT username, expires_at FROM sessions WHERE token = ?", (token,))
            row = cursor.fetchone()
            if row:
                username, expires_at_str = row
                expires_at = datetime.strptime(expires_at_str, '%Y-%m-%d %H:%M:%S')
                if datetime.now() < expires_at:
                    return username
                else:
                    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
                    conn.commit()
            return None
        except Exception:
            return None
        finally:
            conn.close()

def destroy_session(token):
    """세션 무효화 (DB에서 삭제, Supabase/SQLite 하이브리드 지원)"""
    token = token.strip()
    if not token:
        return
        
    if USE_SUPABASE:
        try:
            supabase_client.table("sessions").delete().eq("token", token).execute()
        except Exception:
            pass
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

def get_user_portfolio(username):
    """유저가 기존에 저장한 실보유 자산 포트폴리오 목록 조회 (Supabase/SQLite 하이브리드 지원)"""
    username = username.strip()
    if not username:
        return None
        
    if USE_SUPABASE:
        try:
            res = supabase_client.table("user_portfolios").select("ticker, buy_price, shares").eq("username", username).execute()
            if not res.data:
                return None
            return [{"티커": item["ticker"], "매수 평단가": item["buy_price"], "보유 수량": item["shares"]} for item in res.data]
        except Exception:
            return None
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT ticker, buy_price, shares FROM user_portfolios WHERE username = ?", (username,))
            rows = cursor.fetchall()
            if not rows:
                return None
            return [{"티커": r[0], "매수 평단가": r[1], "보유 수량": r[2]} for r in rows]
        except Exception:
            return None
        finally:
            conn.close()

def overwrite_user_portfolio(username, df):
    """유저의 최신 포트폴리오 상태로 DB에 일괄 덮어쓰기 업데이트 (Supabase/SQLite 하이브리드 지원)"""
    username = username.strip()
    if not username or df is None:
        return
        
    if USE_SUPABASE:
        try:
            # 1. 기존 데이터 일괄 삭제
            supabase_client.table("user_portfolios").delete().eq("username", username).execute()
            
            # 2. 새 데이터 일괄 빌드 후 삽입
            insert_data = []
            for _, row in df.iterrows():
                ticker = str(row.get("티커", "")).strip().upper()
                if not ticker:
                     continue
                try:
                    buy_price = float(row.get("매수 평단가", 0.0))
                    shares = float(row.get("보유 수량", 0.0))
                except (ValueError, TypeError):
                    continue
                    
                insert_data.append({
                    "username": username,
                    "ticker": ticker,
                    "buy_price": buy_price,
                    "shares": shares
                })
            if insert_data:
                supabase_client.table("user_portfolios").insert(insert_data).execute()
        except Exception:
            pass
    else:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            # 기존 저장 데이터 삭제
            cursor.execute("DELETE FROM user_portfolios WHERE username = ?", (username,))
            
            # 새 편집본 행 순회 및 저장
            for _, row in df.iterrows():
                ticker = str(row.get("티커", "")).strip().upper()
                if not ticker:
                     continue
                try:
                    buy_price = float(row.get("매수 평단가", 0.0))
                    shares = float(row.get("보유 수량", 0.0))
                except (ValueError, TypeError):
                    continue
                    
                cursor.execute(
                    "INSERT OR REPLACE INTO user_portfolios (username, ticker, buy_price, shares) VALUES (?, ?, ?, ?)",
                    (username, ticker, buy_price, shares)
                )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

# 모듈 로드 시점에 데이터베이스 및 admin 자동 프리셋을 1회 강제 실행
try:
    init_db()
except Exception:
    pass
