import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import auth  # 사용자 정의 인증 모듈 임포트
import random
import string

# 페이지 설정
st.set_page_config(
    page_title="Dynamic Stock Backtester",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
    
# 이메일 인증용 세션 상태 추가
if 'code_sent' not in st.session_state:
    st.session_state['code_sent'] = False
if 'generated_code' not in st.session_state:
    st.session_state['generated_code'] = ""
if 'email_verified' not in st.session_state:
    st.session_state['email_verified'] = False

# 무차별 대입 해킹 방어용 로그인 락 상태 추가
if 'login_attempts' not in st.session_state:
    st.session_state['login_attempts'] = 0
if 'lock_until' not in st.session_state:
    st.session_state['lock_until'] = None

# 새로고침 발생 시 URL 파라미터(session_key)를 확인하여 자동 로그인 복원
if not st.session_state['logged_in']:
    session_key = st.query_params.get("session_key", "")
    if session_key:
        verified_username = auth.verify_session_token(session_key)
        if verified_username:
            st.session_state['logged_in'] = True
            st.session_state['username'] = verified_username

# 커스텀 CSS로 디자인 개선 (유려한 글꼴, 그라데이션 및 카드 스타일, 헤더 감추기)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* 우측 상단 배포 버튼, 메뉴 버튼 및 푸터 영역만 숨기고 사이드바 열기 버튼은 보존 */
    [data-testid="stAppDeployButton"], 
    [data-testid="stHeaderActionElements"], 
    #MainMenu {
        visibility: hidden;
        display: none !important;
    }
    footer {
        visibility: hidden;
    }
    /* 우측 하단 Manage App 버튼 숨기기 */
    .viewerBadge {
        display: none !important;
    }
    
    /* 사이드바 열기 화살표 버튼을 화면 좌측 상단에 완전 고정(Fixed) */
    [data-testid="collapsedControl"] {
        position: fixed !important;
        top: 12px !important;
        left: 12px !important;
        z-index: 999999 !important;
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
        padding: 4px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
    }
    
    .main-title {
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    
    .sub-title {
        font-size: 1.1rem;
        color: #888888;
        margin-bottom: 2rem;
        text-align: center;
    }
    
    .metric-card {
        background-color: #1E293B;
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 600;
        color: #F8FAFC;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* 미니 주가 카드 스타일 */
    .spark-card {
        background-color: #1E293B;
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid #334155;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        margin-bottom: 0.5rem;
    }
    </style>
""", unsafe_allow_html=True)

# ----------------- 데이터 로딩 및 캐싱 -----------------
@st.cache_data(ttl=3600)  # 1시간 캐싱
def load_stock_data(ticker, start_date, end_date):
    try:
        data = yf.download(ticker, start=start_date, end=end_date)
        if data.empty:
            return None
        # yfinance MultiIndex 컬럼 수정
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        # 수정 종가(Adj Close) 반영
        if 'Adj Close' in data.columns:
            data['Close'] = data['Adj Close']
            
        return data
    except Exception as e:
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
        return None

# 최근 30일 미니 스파크라인용 데이터 수집 캐싱
@st.cache_data(ttl=1800) # 30분 캐싱
def load_sparkline_data(ticker):
    try:
        data = yf.download(ticker, period="30d", interval="1d")
        if data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
            
        if 'Adj Close' in data.columns:
            data['Close'] = data['Adj Close']
            
        return data
    except Exception:
        return None

# ----------------- 미니 스파크라인 그래프 생성 -----------------
def draw_sparkline(df, is_positive):
    prices = df['Close'].values.flatten()
    dates = df.index
    
    fig = go.Figure(go.Scatter(
        x=dates, 
        y=prices, 
        line=dict(color='#10B981' if is_positive else '#EF4444', width=2), 
        mode='lines',
        hoverinfo='skip'
    ))
    
    fig.update_layout(
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=5, b=5),
        height=60,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        dragmode=False
    )
    return fig

# ----------------- 백테스트 엔진 (슬리피지 & 세금 정밀 추가) -----------------
def run_backtest(df, short_window, long_window, initial_capital, commission_pct=0.001, slippage_pct=0.001, tax_pct=0.0018):
    data = df.copy()
    
    # 이동평균선 계산
    data['Short_SMA'] = data['Close'].rolling(window=short_window).mean()
    data['Long_SMA'] = data['Close'].rolling(window=long_window).mean()
    
    # 거래 시그널 생성
    data['Signal'] = np.where(data['Short_SMA'] > data['Long_SMA'], 1, 0)
    
    # 포지션 (전일 시그널 기준 다음 날 체결)
    data['Position'] = data['Signal'].shift(1).fillna(0)
    data['Action'] = data['Position'].diff().fillna(0)
    data['Daily_Return'] = data['Close'].pct_change().fillna(0)
    
    portfolio_values = []
    cash = initial_capital
    shares = 0.0
    current_position = 0  # 0: 현금, 1: 주식
    
    prices = data['Close'].values
    positions = data['Position'].values
    actions = data['Action'].values
    
    # 정밀 복리 계산 (수수료, 세금 및 슬리피지 고려)
    for i in range(len(data)):
        current_price = prices[i]
        act = actions[i]
        
        # 1) 매수 체결
        if act == 1 and cash > 0:
            # 슬리피지 반영
            execution_price = current_price * (1 + slippage_pct)
            
            # 수수료 차감 후 매수 가능한 주식 수
            buy_capital = cash * (1 - commission_pct)
            shares = buy_capital / execution_price
            cash = 0.0
            current_position = 1
        
        # 2) 매도 체결
        elif act == -1 and shares > 0:
            # 슬리피지 반영
            execution_price = current_price * (1 - slippage_pct)
            
            # 주식 매도 후 수수료 및 거래세 차감
            sell_value = shares * execution_price
            cash = sell_value * (1 - commission_pct - tax_pct)
            shares = 0.0
            current_position = 0
            
        # 3) 평가 자산 산정
        if current_position == 1:
            total_value = shares * current_price
        else:
            total_value = cash
            
        portfolio_values.append(total_value)
        
    data['Portfolio_Value'] = portfolio_values
    
    # 단순 Buy & Hold 자산 가치 계산
    data['Buy_Hold_CumReturn'] = (1 + data['Daily_Return']).cumprod()
    data['Buy_Hold_Value'] = initial_capital * data['Buy_Hold_CumReturn']
    
    return data

# ----------------- 성과 지표 계산 -----------------
def calculate_metrics(data, initial_capital, benchmark_data=None):
    final_val = data['Portfolio_Value'].iloc[-1]
    bh_final_val = data['Buy_Hold_Value'].iloc[-1]
    
    total_days = len(data)
    years = total_days / 252.0 if total_days > 0 else 1.0
    
    # 전략 성과
    total_return = (final_val - initial_capital) / initial_capital * 100
    cagr = ((final_val / initial_capital) ** (1 / years) - 1) * 100 if years > 0 and final_val > 0 else 0
    peak = data['Portfolio_Value'].cummax()
    mdd = ((data['Portfolio_Value'] - peak) / peak).min() * 100
    
    # Buy & Hold 성과
    bh_return = (bh_final_val - initial_capital) / initial_capital * 100
    bh_cagr = ((bh_final_val / initial_capital) ** (1 / years) - 1) * 100 if years > 0 and bh_final_val > 0 else 0
    bh_peak = data['Buy_Hold_Value'].cummax()
    bh_mdd = ((data['Buy_Hold_Value'] - bh_peak) / bh_peak).min() * 100
    
    # 벤치마크 성과
    bench_metrics = None
    if benchmark_data is not None:
        bench_final_val = benchmark_data['Benchmark_Value'].iloc[-1]
        bench_return = (bench_final_val - initial_capital) / initial_capital * 100
        bench_cagr = ((bench_final_val / initial_capital) ** (1 / years) - 1) * 100 if years > 0 and bench_final_val > 0 else 0
        bench_peak = benchmark_data['Benchmark_Value'].cummax()
        bench_mdd = ((benchmark_data['Benchmark_Value'] - bench_peak) / bench_peak).min() * 100
        bench_metrics = {
            "return": bench_return,
            "cagr": bench_cagr,
            "mdd": bench_mdd
        }
        
    trade_count = int(data['Action'].abs().sum())
    
    return {
        "final_value": final_val,
        "total_return": total_return,
        "cagr": cagr,
        "mdd": mdd,
        "bh_final_value": bh_final_val,
        "bh_return": bh_return,
        "bh_cagr": bh_cagr,
        "bh_mdd": bh_mdd,
        "bench_metrics": bench_metrics,
        "trade_count": trade_count
    }

# ----------------- 로그인 전 전용: 실시간 주가 순환 컴포넌트 (st.fragment) -----------------
@st.fragment(run_every=10)
def render_live_dashboard():
    if 'dash_index' not in st.session_state:
        st.session_state['dash_index'] = 0
        
    dashboard_stocks_groups = [
        # 그룹 1: 미 기술 자이언트 (M7 일부)
        [
            {"name": "Apple (AAPL)", "ticker": "AAPL", "currency": "$"},
            {"name": "Nvidia (NVDA)", "ticker": "NVDA", "currency": "$"},
            {"name": "Microsoft (MSFT)", "ticker": "MSFT", "currency": "$"}
        ],
        # 그룹 2: 반도체 & 메모리 핵심 기업
        [
            {"name": "삼성전자 (005930.KS)", "ticker": "005930.KS", "currency": "₩"},
            {"name": "SK하이닉스 (000660.KS)", "ticker": "000660.KS", "currency": "₩"},
            {"name": "TSMC (TSM)", "ticker": "TSM", "currency": "$"}
        ],
        # 그룹 3: 차세대 플랫폼 및 전기차
        [
            {"name": "Tesla (TSLA)", "ticker": "TSLA", "currency": "$"},
            {"name": "Alphabet (GOOGL)", "ticker": "GOOGL", "currency": "$"},
            {"name": "Meta (META)", "ticker": "META", "currency": "$"}
        ]
    ]
    
    current_group = dashboard_stocks_groups[st.session_state['dash_index']]
    
    col_a, col_b, col_c = st.columns(3)
    cols = [col_a, col_b, col_c]
    
    for i, stock in enumerate(current_group):
        col = cols[i]
        stock_data = load_sparkline_data(stock['ticker'])
        
        if stock_data is not None and len(stock_data) >= 2:
            close_prices = stock_data['Close'].values.flatten()
            curr_price = float(close_prices[-1])
            prev_price = float(close_prices[-2])
            
            change_val = curr_price - prev_price
            change_pct = (change_val / prev_price) * 100
            is_positive = change_val >= 0
            color_hex = "#10B981" if is_positive else "#EF4444"
            sign = "+" if is_positive else ""
            arrow = "▲" if is_positive else "▼"
            
            col.markdown(f"""
                <div class="spark-card">
                    <div style="font-size: 0.85rem; color: #94A3B8; font-weight: 600; text-transform: uppercase;">{stock['name']}</div>
                    <div style="display: flex; align-items: baseline; justify-content: space-between; margin-top: 0.4rem; margin-bottom: 0.2rem;">
                        <span style="font-size: 1.6rem; font-weight: 700; color: #F8FAFC;">{stock['currency']}{curr_price:,.2f}</span>
                        <span style="font-size: 0.9rem; font-weight: 600; color: {color_hex};">
                            {arrow} {sign}{change_pct:.2f}%
                        </span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            fig = draw_sparkline(stock_data, is_positive)
            col.plotly_chart(
                fig, 
                use_container_width=True, 
                config={'displayModeBar': False}, 
                key=f"spark_{stock['ticker']}_{st.session_state['dash_index']}"
            )
        else:
            col.info(f"{stock['name']} 데이터를 불러올 수 없습니다.")
            
    st.session_state['dash_index'] = (st.session_state['dash_index'] + 1) % len(dashboard_stocks_groups)


# =======================================================
#                      로그인 / 회원가입 제어
# =======================================================
if not st.session_state['logged_in']:
    # 타이틀 영역
    st.markdown('<div class="main-title">📊 Dynamic Stock Backtester</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">SMA(이동평균선) 골든/데드 크로스 전략으로 과거 데이터를 분석하고 투자 성과를 검증하세요.</div>', unsafe_allow_html=True)

    # 1) 로그인 페이지 상단 실시간 주가 대시보드
    st.markdown("<h4 style='text-align: center; color: #94A3B8; margin-bottom: 1.5rem;'>📈 주요 시장지표 & 대표주 실시간 현황</h4>", unsafe_allow_html=True)
    render_live_dashboard()

    st.markdown("<br>", unsafe_allow_html=True)

    # 2) 로그인 / 회원가입 입력 영역
    _, center_col, _ = st.columns([1, 1.8, 1])
    
    with center_col:
        with st.container(border=True):
            tab_login, tab_register = st.tabs(["🔐 로그인", "📝 회원가입"])
            
            # 로그인 탭 (무차별 대입 공격 차단 및 아이디 저장 포함)
            with tab_login:
                st.markdown("<br>", unsafe_allow_html=True)
                
                # 2-1) 무차별 대입 잠금 상태 연동 계산
                is_locked = False
                remaining_seconds = 0
                if st.session_state['lock_until'] is not None:
                    if datetime.now() < st.session_state['lock_until']:
                        is_locked = True
                        remaining_seconds = int((st.session_state['lock_until'] - datetime.now()).total_seconds())
                    else:
                        st.session_state['lock_until'] = None
                        st.session_state['login_attempts'] = 0
                
                # 저장된 아이디가 URL 매개변수에 존재하면 불러옴 (Remember ID)
                saved_user_val = st.query_params.get("user", "")
                
                login_username = st.text_input("아이디", value=saved_user_val, key="login_user")
                login_password = st.text_input("비밀번호", type="password", key="login_pass")
                
                # 아이디 저장 체크박스
                remember_me = st.checkbox("아이디 저장", value=(saved_user_val != ""), key="remember_me_check")
                
                # 잠금 상태일 때 경고 노출
                if is_locked:
                    st.error(f"⚠️ 연속 로그인 실패로 로그인이 차단되었습니다. {remaining_seconds}초 후 다시 시도하세요.")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("로그인", use_container_width=True, type="primary", disabled=is_locked):
                    if auth.verify_user(login_username, login_password):
                        # 로그인 성공 시 1. DB 세션 생성 및 토큰 발급 (F5 새로고침 유지)
                        token = auth.create_session(login_username)
                        if token:
                            st.query_params["session_key"] = token
                            
                        # 로그인 성공 시 세션 카운터 리셋 및 아이디 저장 처리
                        st.session_state['login_attempts'] = 0
                        st.session_state['lock_until'] = None
                        
                        if remember_me:
                            st.query_params["user"] = login_username.strip()
                        else:
                            st.query_params.pop("user", None)
                            
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = login_username
                        st.success("로그인에 성공했습니다! 페이지를 로드 중...")
                        st.rerun()
                    else:
                        st.session_state['login_attempts'] += 1
                        if st.session_state['login_attempts'] >= 5:
                            st.session_state['lock_until'] = datetime.now() + timedelta(seconds=30)
                            st.error("⚠️ 연속 5회 로그인 실패로 30초간 로그인이 차단됩니다.")
                            st.rerun()
                        else:
                            st.error(f"아이디 또는 비밀번호가 올바르지 않습니다. (로그인 실패 횟수: {st.session_state['login_attempts']}/5)")
                        
                # ----------------- 🔑 아이디 / 비밀번호 찾기 -----------------
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("🔍 아이디 / 비밀번호를 잊으셨나요?"):
                    find_mode = st.radio("찾을 정보 선택", ["아이디 찾기", "비밀번호 재설정"], horizontal=True)
                    
                    if find_mode == "아이디 찾기":
                        find_email = st.text_input("가입 시 등록한 이메일 주소", key="find_email_id")
                        if st.button("✉️ 아이디 찾기 메일 발송", use_container_width=True):
                            if not find_email.strip():
                                st.error("이메일 주소를 입력해 주세요.")
                            else:
                                ids = auth.find_id_by_email(find_email)
                                if ids:
                                    id_list_str = ", ".join(ids)
                                    success, msg = auth.send_account_info_email(
                                        to_email=find_email,
                                        subject="아이디 찾기 결과 안내",
                                        content_title="가입하신 이메일로 등록된 아이디 목록은 다음과 같습니다.",
                                        content_desc="이 비밀번호나 아이디로 로그인을 진행해 주세요.",
                                        value_to_highlight=id_list_str
                                    )
                                    if success:
                                        st.success(msg)
                                    else:
                                        st.info(msg)
                                else:
                                    st.error("해당 이메일로 가입된 아이디가 존재하지 않습니다.")
                                    
                    elif find_mode == "비밀번호 재설정":
                        find_user = st.text_input("아이디 입력", key="find_user_pw")
                        find_email = st.text_input("가입 시 등록한 이메일 주소", key="find_email_pw")
                        if st.button("✉️ 임시 비밀번호 발송", use_container_width=True):
                            if not find_user.strip() or not find_email.strip():
                                st.error("아이디와 이메일 주소를 모두 입력해 주세요.")
                            else:
                                temp_char_pool = string.ascii_letters + string.digits
                                temp_pwd = "".join(random.choices(temp_char_pool, k=8))
                                
                                success_db, msg_db = auth.reset_to_temp_password(find_user, find_email, temp_pwd)
                                if success_db:
                                    success_mail, msg_mail = auth.send_account_info_email(
                                        to_email=find_email,
                                        subject="임시 비밀번호 안내",
                                        content_title=f"계정 ({find_user})의 임시 비밀번호가 발급되었습니다.",
                                        content_desc="로그인 후 개인 보안을 위해 비밀번호를 반드시 변경하시는 것을 권장합니다.",
                                        value_to_highlight=temp_pwd
                                    )
                                    if success_mail:
                                        st.success(msg_mail)
                                    else:
                                        st.info(msg_mail)
                                else:
                                    st.error(msg_db)
                        
            # 회원가입 탭 (강한 유효성 필터 및 이메일 인증)
            with tab_register:
                st.markdown("<br>", unsafe_allow_html=True)
                reg_username = st.text_input("새로운 아이디", key="reg_user")
                st.caption("ℹ️ 아이디는 3~15자의 영문자, 숫자, 언더바(_)만 입력할 수 있습니다.")
                
                reg_password = st.text_input("새로운 비밀번호", type="password", key="reg_pass")
                st.caption("ℹ️ 비밀번호는 최소 8자 이상이며 영문자, 숫자, 특수문자를 혼합해야 합니다.")
                
                reg_password_confirm = st.text_input("비밀번호 확인", type="password", key="reg_pass_conf")
                
                reg_email = st.text_input("이메일 주소", key="reg_email")
                
                # 인증 번호 전송 버튼
                col_send, col_status = st.columns([1.5, 2])
                with col_send:
                    send_btn = st.button("✉️ 인증 코드 전송", use_container_width=True)
                
                if send_btn:
                    if not reg_email.strip():
                        st.error("이메일 주소를 입력해 주세요.")
                    else:
                        code = f"{random.randint(100000, 999999)}"
                        st.session_state['generated_code'] = code
                        st.session_state['code_sent'] = True
                        st.session_state['email_verified'] = False
                        
                        success, msg = auth.send_verification_email(reg_email, code)
                        if success:
                            st.success(msg)
                        else:
                            st.info(msg)
                            
                # 메일 발송 시 인증 코드 입력란 노출
                if st.session_state['code_sent'] and not st.session_state['email_verified']:
                    user_code = st.text_input("6자리 인증번호 입력", key="verification_code")
                    
                    if st.button("인증 코드 확인", use_container_width=True):
                        if user_code.strip() == st.session_state['generated_code']:
                            st.session_state['email_verified'] = True
                            st.success("이메일 인증 성공! 가입을 진행하실 수 있습니다.")
                        else:
                            st.error("인증번호가 불일치합니다. 다시 입력해 주세요.")
                            
                if st.session_state['email_verified']:
                    st.markdown("<p style='color: #10B981; font-weight: 600; font-size: 0.9rem;'>✓ 이메일 인증 완료</p>", unsafe_allow_html=True)
                    
                st.markdown("<br>", unsafe_allow_html=True)
                
                # 최종 가입 제출 버튼 (강력한 유효성 필터 적용)
                if st.button("회원가입 완료", use_container_width=True, type="primary"):
                    # 1) 공란 검사
                    if not reg_username.strip() or not reg_password.strip() or not reg_email.strip():
                        st.error("모든 항목을 올바르게 입력해 주세요.")
                    # 2) 아이디 패턴 검사
                    elif not auth.is_valid_username(reg_username):
                        st.error("아이디는 3~15자의 영문자, 숫자, 언더스코어(_)만 허용됩니다. 특수문자나 한글, 띄어쓰기는 포함할 수 없습니다.")
                    # 3) 비밀번호 강도 검사
                    elif not auth.is_strong_password(reg_password)[0]:
                        st.error(auth.is_strong_password(reg_password)[1])
                    # 4) 비밀번호 일치 확인
                    elif reg_password != reg_password_confirm:
                        st.error("비밀번호와 비밀번호 확인이 서로 일치하지 않습니다.")
                    # 5) 이메일 인증 완료 확인
                    elif not st.session_state['email_verified']:
                        st.error("이메일 인증을 먼저 완료해 주세요.")
                    # 6) 가입 처리
                    else:
                        success, msg = auth.register_user(reg_username, reg_password, reg_email)
                        if success:
                            st.success(msg)
                            st.session_state['code_sent'] = False
                            st.session_state['generated_code'] = ""
                            st.session_state['email_verified'] = False
                        else:
                            st.error(msg)

# =======================================================
#                      메인 애플리케이션 화면
# =======================================================
else:
    # 사이드바 설정 영역
    st.sidebar.header("⚙️ 백테스트 설정")
    
    st.sidebar.markdown(f"👤 **{st.session_state['username']}**님 환영합니다!")
    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        # DB 세션 파괴 및 파라미터 삭제 (F5 새로고침 방지 초기화)
        current_token = st.query_params.get("session_key", "")
        if current_token:
            auth.destroy_session(current_token)
            st.query_params.pop("session_key", None)
            
        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.rerun()
        
    st.sidebar.markdown("---")

    # 관리자 식별 및 대시보드 모드 전환
    is_admin = st.session_state['username'].lower() == "admin"
    if is_admin:
        st.sidebar.subheader("⚙️ 관리자 전용 메뉴")
        admin_mode = st.sidebar.radio(
            "화면 모드 선택",
            ["📈 백테스터 실행", "👥 가입 회원 관리"]
        )
        st.sidebar.markdown("---")
    else:
        admin_mode = "📈 백테스터 실행"

    # =======================================================
    #                      관리자 전용 대시보드 화면
    # =======================================================
    if is_admin and admin_mode == "👥 가입 회원 관리":
        st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">👥 가입 회원 관리 대시보드</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">서비스에 등록된 사용자들의 현황을 조회하고 엑셀 파일로 출력합니다.</p>', unsafe_allow_html=True)
        
        users_raw = auth.get_all_users()
        df_users = pd.DataFrame(users_raw, columns=["사용자 ID", "이메일 주소", "가입 일시"])
        
        # admin 계정이 회원 가입 상세현황 표의 제일 위에 배치되도록 강제 정렬
        df_admin = df_users[df_users["사용자 ID"].str.lower() == "admin"]
        df_others = df_users[df_users["사용자 ID"].str.lower() != "admin"]
        df_users = pd.concat([df_admin, df_others]).reset_index(drop=True)
        
        col_m1, col_m2 = st.columns([1, 3])
        with col_m1:
            st.markdown(
                f"""<div class="metric-card">
                    <div class="metric-label">총 가입 회원 수</div>
                    <div class="metric-value" style="color: #3B82F6;">{len(df_users)} 명</div>
                </div>""", 
                unsafe_allow_html=True
            )
            
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("### 📋 회원 가입 상세 현황")
        st.dataframe(
            df_users, 
            use_container_width=True,
            column_config={
                "사용자 ID": st.column_config.TextColumn(width="medium"),
                "이메일 주소": st.column_config.TextColumn(width="large"),
                "가입 일시": st.column_config.DatetimeColumn(width="medium", format="YYYY-MM-DD HH:mm:ss")
            }
        )
        
        csv_data = df_users.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 회원 목록 CSV 다운로드 (Excel 호환)",
            data=csv_data,
            file_name=f"registered_users_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        # ----------------- ❌ 회원 강제 탈퇴 처리 기능 추가 -----------------
        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.markdown("### ❌ 가입 회원 강제 탈퇴 처리")
        
        # admin을 제외한 일반 회원 목록 필터링
        delete_candidates = [user[0] for user in users_raw if user[0].lower() != "admin"]
        
        if delete_candidates:
            user_to_delete = st.selectbox("탈퇴 처리할 회원 ID 선택", delete_candidates)
            confirm_delete = st.checkbox(
                f"위 회원({user_to_delete})을 정말 강제 탈퇴 처리하는 것에 동의합니다. (데이터 영구 복구 불가)", 
                value=False,
                key="confirm_delete_checkbox"
            )
            
            if st.button("🚨 회원 강제 탈퇴 실행", type="primary", disabled=not confirm_delete, use_container_width=True):
                success, msg = auth.delete_user(user_to_delete)
                if success:
                    st.success(msg)
                    st.rerun()
                else:
                    st.error(msg)
        else:
            st.info("현재 관리자 계정 외에 가입된 일반 회원 계정이 존재하지 않습니다.")

    # =======================================================
    #                      기존 백테스터 화면
    # =======================================================
    else:
        st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">📊 Dynamic Stock Backtester</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">수정 종가(Adjusted Close)와 정밀한 슬리피지/세금을 반영한 실전용 백테스터</p>', unsafe_allow_html=True)

        # 1. 티커 및 기간 설정
        st.sidebar.subheader("1. 대상 종목 & 기간")
        ticker_input = st.sidebar.text_input("주식 티커 입력 (yfinance 규격)", value="AAPL")
        st.sidebar.caption("💡 팁: 나스닥은 'AAPL', 'TSLA' 등 / 코스피는 '005930.KS', 코스닥은 '091990.KQ'")

        today = datetime.today()
        default_start = today - timedelta(days=365 * 3)
        start_date = st.sidebar.date_input("시작일", default_start)
        end_date = st.sidebar.date_input("종료일", today)

        # 2. 투자 조건 설정
        st.sidebar.subheader("2. 실전 투자 조건")
        initial_capital = st.sidebar.number_input("초기 투자금 ($ 또는 ₩)", min_value=1000, value=10000, step=1000)
        commission_pct = st.sidebar.slider("증권사 수수료 (%)", min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100.0
        slippage_pct = st.sidebar.slider("슬리피지 (Slippage, %)", min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100.0
        tax_pct = st.sidebar.slider("거래세 (Tax, %)", min_value=0.0, max_value=1.0, value=0.18, step=0.02) / 100.0

        # 3. 벤치마크 지수 설정
        st.sidebar.subheader("3. 비교 벤치마크 지수")
        benchmark_option = st.sidebar.selectbox(
            "비교 대상 시장 지수", 
            ["선택 안 함", "S&P 500 (^GSPC)", "Nasdaq 100 (QQQ)", "KOSPI (^KS11)", "KOSDAQ (^KQ11)"]
        )

        # 4. SMA 변수 설정
        st.sidebar.subheader("4. 이동평균선(SMA) 설정")
        short_window = st.sidebar.number_input("단기 이평선 기간 (일)", min_value=2, max_value=100, value=20)
        long_window = st.sidebar.number_input("장기 이평선 기간 (일)", min_value=5, max_value=300, value=50)

        # 이평선 크기 유효성 검사
        if short_window >= long_window:
            st.sidebar.error("단기 이평선 기간은 장기 이평선 기간보다 작아야 합니다!")

        # 실행 버튼
        run_button = st.sidebar.button("⚡ 백테스트 실행", use_container_width=True)

        # ----------------- 실행 및 결과 출력 -----------------
        if run_button or 'backtest_run' not in st.session_state:
            st.session_state['backtest_run'] = True
            
            if short_window >= long_window:
                st.error("설정을 확인해 주세요: 단기 이평선은 장기 이평선보다 작아야 합니다.")
            else:
                with st.spinner("주가 데이터를 가져오고 백테스트를 진행 중입니다..."):
                    df = load_stock_data(ticker_input, start_date, end_date)
                    
                    if df is None or len(df) < long_window:
                        st.error("데이터를 불러오지 못했거나 백테스트를 위한 충분한 역사적 데이터가 없습니다.")
                    else:
                        # 벤치마크 데이터 로딩 및 계산
                        benchmark_df = None
                        if benchmark_option != "선택 안 함":
                            bench_ticker = benchmark_option.split("(")[-1].replace(")", "")
                            bench_raw = load_stock_data(bench_ticker, start_date, end_date)
                            if bench_raw is not None and not bench_raw.empty:
                                benchmark_df = pd.DataFrame(index=df.index)
                                benchmark_df = benchmark_df.join(bench_raw['Close'], how='left').ffill().bfill()
                                benchmark_df['Daily_Return'] = benchmark_df['Close'].pct_change().fillna(0)
                                benchmark_df['Benchmark_CumReturn'] = (1 + benchmark_df['Daily_Return']).cumprod()
                                benchmark_df['Benchmark_Value'] = initial_capital * benchmark_df['Benchmark_CumReturn']

                        # 백테스트 수행
                        results = run_backtest(df, short_window, long_window, initial_capital, commission_pct, slippage_pct, tax_pct)
                        metrics = calculate_metrics(results, initial_capital, benchmark_df)
                        
                        # 결과 지표 대시보드
                        st.markdown("### 🏆 백테스트 성과 지표 비교")
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.markdown(
                                f"""<div class="metric-card">
                                    <div class="metric-label">최종 포트폴리오 가치</div>
                                    <div class="metric-value">{metrics['final_value']:,.2f}</div>
                                    <div style="color: {'#10B981' if metrics['total_return'] >= 0 else '#EF4444'}; font-weight: 600;">
                                        {'+' if metrics['total_return'] >= 0 else ''}{metrics['total_return']:.2f}%
                                    </div>
                                </div>""", 
                                unsafe_allow_html=True
                            )
                        
                        bench_cagr_str = ""
                        bench_mdd_str = ""
                        if metrics['bench_metrics'] is not None:
                            bench_cagr_str = f" / 벤치마크: {metrics['bench_metrics']['cagr']:.2f}%"
                            bench_mdd_str = f" / 벤치마크: {metrics['bench_metrics']['mdd']:.2f}%"
                        
                        with col2:
                            st.markdown(
                                f"""<div class="metric-card">
                                    <div class="metric-label">연평균 수익률 (CAGR)</div>
                                    <div class="metric-value">{metrics['cagr']:.2f}%</div>
                                    <div style="color: #94A3B8; font-size: 0.85rem;">
                                        시장 평균(B&H): {metrics['bh_cagr']:.2f}%{bench_cagr_str}
                                    </div>
                                </div>""", 
                                unsafe_allow_html=True
                            )
                            
                        with col3:
                            st.markdown(
                                f"""<div class="metric-card">
                                    <div class="metric-label">최대 낙폭 (MDD)</div>
                                    <div class="metric-value" style="color: #EF4444;">{metrics['mdd']:.2f}%</div>
                                    <div style="color: #94A3B8; font-size: 0.85rem;">
                                        시장 평균(B&H): {metrics['bh_mdd']:.2f}%{bench_mdd_str}
                                    </div>
                                </div>""", 
                                unsafe_allow_html=True
                            )
                            
                        with col4:
                            st.markdown(
                                f"""<div class="metric-card">
                                    <div class="metric-label">총 매매 횟수</div>
                                    <div class="metric-value" style="color: #3B82F6;">{metrics['trade_count']} 회</div>
                                    <div style="color: #94A3B8; font-size: 0.85rem;">
                                        슬리피지: {slippage_pct*100:.2f}% / 세금: {tax_pct*100:.2f}%
                                    </div>
                                </div>""", 
                                unsafe_allow_html=True
                            )
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        # Plotly 시각화 구성
                        st.markdown("### 📈 인터랙티브 차트 분석")
                        
                        fig = make_subplots(
                            rows=2, cols=1, 
                            shared_xaxes=True, 
                            vertical_spacing=0.08,
                            row_heights=[0.6, 0.4]
                        )
                        
                        # 1. 주가 데이터 추가
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Close'], name='Close Price', line=dict(color='#636EFA', width=1.5)),
                            row=1, col=1
                        )
                        
                        # 2. 이평선 추가
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Short_SMA'], name=f'{short_window} SMA', line=dict(color='#00CC96', width=1, dash='dash')),
                            row=1, col=1
                        )
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Long_SMA'], name=f'{long_window} SMA', line=dict(color='#EF553B', width=1, dash='dash')),
                            row=1, col=1
                        )
                        
                        # 3. 매매 시그널 마커 추가
                        buys = results[results['Action'] == 1]
                        sells = results[results['Action'] == -1]
                        
                        fig.add_trace(
                            go.Scatter(
                                x=buys.index, y=buys['Close'], name='Buy Signal', 
                                mode='markers', marker=dict(symbol='triangle-up', size=11, color='#10B981', line=dict(width=1, color='black'))
                            ),
                            row=1, col=1
                        )
                        fig.add_trace(
                            go.Scatter(
                                x=sells.index, y=sells['Close'], name='Sell Signal', 
                                mode='markers', marker=dict(symbol='triangle-down', size=11, color='#EF4444', line=dict(width=1, color='black'))
                            ),
                            row=1, col=1
                        )
                        
                        # 4. 누적 포트폴리오 가치 추가
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Portfolio_Value'], name='SMA Strategy', line=dict(color='#F1C40F', width=2)),
                            row=2, col=1
                        )
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Buy_Hold_Value'], name='Buy & Hold', line=dict(color='#7F8C8D', width=1.5, dash='dot')),
                            row=2, col=1
                        )
                        
                        # 벤치마크 가치 곡선 오버레이
                        if benchmark_df is not None:
                            fig.add_trace(
                                go.Scatter(x=benchmark_df.index, y=benchmark_df['Benchmark_Value'], name=benchmark_option, line=dict(color='#9B59B6', width=1.5, dash='dashdot')),
                                row=2, col=1
                            )
                        
                        # 차트 레이아웃 스타일 설정
                        fig.update_layout(
                            height=700,
                            hovermode='x unified',
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                            template="plotly_dark",
                            plot_bgcolor='rgba(15, 23, 42, 0.5)',
                            paper_bgcolor='rgba(15, 23, 42, 0.5)',
                            margin=dict(l=20, r=20, t=50, b=20)
                        )
                        
                        fig.update_yaxes(title_text="주가 ($/₩)", row=1, col=1)
                        fig.update_yaxes(title_text="포트폴리오 가치", row=2, col=1)
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 상세 거래 내역 데이터 테이블 제공
                        with st.expander("📝 상세 거래 로그 및 역사적 데이터 보기"):
                            trade_log = results[results['Action'] != 0][['Close', 'Short_SMA', 'Long_SMA', 'Action', 'Portfolio_Value']]
                            trade_log['Action'] = trade_log['Action'].map({1: '매수 (BUY)', -1: '매도 (SELL)'})
                            trade_log.rename(columns={
                                'Close': '종가', 
                                'Action': '매매행동', 
                                'Portfolio_Value': '평가금액'
                            }, inplace=True)
                            st.dataframe(trade_log.style.format({
                                '종가': '{:,.2f}',
                                'Short_SMA': '{:,.2f}',
                                'Long_SMA': '{:,.2f}',
                                '평가금액': '{:,.2f}'
                            }), use_container_width=True)
