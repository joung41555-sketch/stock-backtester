import sqlite3
import hashlib
import os

# SQLite DB 경로 설정 (프로젝트 루트에 저장)
DB_PATH = "users.db"
# 보안 강화를 위한 솔트(Salt) 값 설정
PASSWORD_SALT = "antigravity-secure-salt-2026!#"

def init_db():
    """데이터베이스 초기화 및 테이블 생성"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def hash_password(password):
    """비밀번호에 솔트를 추가하여 SHA-256 해시값 생성"""
    salted = password + PASSWORD_SALT
    return hashlib.sha256(salted.encode('utf-8')).hexdigest()

def register_user(username, password):
    """신규 회원가입 처리"""
    init_db()  # DB 초기화 보장
    
    # 공백이나 유효하지 않은 입력 검증
    if not username.strip() or not password.strip():
        return False, "아이디와 비밀번호를 모두 입력해 주세요."
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 아이디 중복 여부 확인
        cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            return False, "이미 존재하는 아이디입니다."
        
        # 비밀번호 암호화 후 가입 처리
        hashed_pwd = hash_password(password)
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_pwd))
        conn.commit()
        return True, "회원가입이 완료되었습니다! 로그인해 주세요."
    except Exception as e:
        return False, f"오류가 발생했습니다: {e}"
    finally:
        conn.close()

def verify_user(username, password):
    """로그인 검증 (아이디/비밀번호 확인)"""
    init_db()  # DB 초기화 보장
    
    if not username.strip() or not password.strip():
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
