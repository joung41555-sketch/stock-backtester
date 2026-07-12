import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import auth  # 사용자 정의 인증 모듈 임포트
import portfolio_engine  # MPT 포트폴리오 엔진 임포트
import ticker_search  # 실시간 티커 검색 자동완성 모듈 임포트
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

# 포트폴리오 자산 구성 멀티 어펜드용 세션 상태 신설
if 'portfolio_tickers' not in st.session_state:
    st.session_state['portfolio_tickers'] = "AAPL, NVDA, TSLA, MSFT"

# 새로고침 발생 시 URL 파라미터(session_key)를 확인하여 자동 로그인 복원
if not st.session_state['logged_in']:
    session_key = st.query_params.get("session_key", "")
    if session_key:
        verified_username = auth.verify_session_token(session_key)
        if verified_username:
            st.session_state['logged_in'] = True
            st.session_state['username'] = verified_username
            # DB에서 포트폴리오를 로드하여 세션 프레임 복원
            db_port = auth.get_user_portfolio(verified_username)
            if db_port:
                st.session_state['my_portfolio_data'] = pd.DataFrame(db_port)

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
    
    /* 포트폴리오 최적화 카드 */
    .opt-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border-radius: 12px;
        padding: 1.5rem;
        border: 1px solid #FF4B4B;
        margin-bottom: 1rem;
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

# ----------------- 🛠️ 실시간 데이터 에디터 유실 종결 콜백 -----------------
def sync_editor_data():
    """st.data_editor의 임시 변경 상태를 세션 상태에 즉시 동기화 보존"""
    if 'portfolio_editor' in st.session_state:
        edits = st.session_state.portfolio_editor
        df = st.session_state['my_portfolio_data'].copy()
        
        # 1. 수정한 셀(edited_rows) 반영
        for idx, changes in edits.get('edited_rows', {}).items():
            for col, val in changes.items():
                df.at[idx, col] = val
                
        # 2. 추가된 행(added_rows) 반영
        added_rows = edits.get('added_rows', [])
        if added_rows:
            df_added = pd.DataFrame(added_rows)
            df = pd.concat([df, df_added], ignore_index=True)
            
        # 3. 삭제된 행(deleted_rows) 반영
        deleted_indices = edits.get('deleted_rows', [])
        if deleted_indices:
            df = df.drop(index=deleted_indices).reset_index(drop=True)
            
        st.session_state['my_portfolio_data'] = df
        
        # SQLite DB에 최신 보유 자산 실시간 영구 동기화
        if st.session_state.get('username'):
            auth.overwrite_user_portfolio(st.session_state['username'], df)


# =======================================================
#                      로그인 / 회원가입 제어
# =======================================================
if not st.session_state['logged_in']:
    st.markdown('<div class="main-title">📊 Dynamic Stock Backtester</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">SMA(이동평균선) 골든/데드 크로스 전략으로 과거 데이터를 분석하고 투자 성과를 검증하세요.</div>', unsafe_allow_html=True)

    st.markdown("<h4 style='text-align: center; color: #94A3B8; margin-bottom: 1.5rem;'>📈 주요 시장지표 & 대표주 실시간 현황</h4>", unsafe_allow_html=True)
    render_live_dashboard()

    st.markdown("<br>", unsafe_allow_html=True)

    _, center_col, _ = st.columns([1, 1.8, 1])
    
    with center_col:
        with st.container(border=True):
            tab_login, tab_register = st.tabs(["🔐 로그인", "📝 회원가입"])
            
            with tab_login:
                st.markdown("<br>", unsafe_allow_html=True)
                
                is_locked = False
                remaining_seconds = 0
                if st.session_state['lock_until'] is not None:
                    if datetime.now() < st.session_state['lock_until']:
                        is_locked = True
                        remaining_seconds = int((st.session_state['lock_until'] - datetime.now()).total_seconds())
                    else:
                        st.session_state['lock_until'] = None
                        st.session_state['login_attempts'] = 0
                
                saved_user_val = st.query_params.get("user", "")
                
                login_username = st.text_input("아이디", value=saved_user_val, key="login_user")
                login_password = st.text_input("비밀번호", type="password", key="login_pass")
                
                remember_me = st.checkbox("아이디 저장", value=(saved_user_val != ""), key="remember_me_check")
                
                if is_locked:
                    st.error(f"⚠️ 연속 로그인 실패로 로그인이 차단되었습니다. {remaining_seconds}초 후 다시 시도하세요.")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("로그인", use_container_width=True, type="primary", disabled=is_locked):
                    if auth.verify_user(login_username, login_password):
                        token = auth.create_session(login_username)
                        if token:
                            st.query_params["session_key"] = token
                            
                        st.session_state['login_attempts'] = 0
                        st.session_state['lock_until'] = None
                        
                        if remember_me:
                            st.query_params["user"] = login_username.strip()
                        else:
                            st.query_params.pop("user", None)
                            
                        st.session_state['logged_in'] = True
                        st.session_state['username'] = login_username
                        
                        # DB에서 저장되어 있던 개인 보유 자산 포트폴리오 로딩 복원
                        db_port = auth.get_user_portfolio(login_username)
                        if db_port:
                            st.session_state['my_portfolio_data'] = pd.DataFrame(db_port)
                            
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
                        
            with tab_register:
                st.markdown("<br>", unsafe_allow_html=True)
                reg_username = st.text_input("새로운 아이디", key="reg_user")
                st.caption("ℹ️ 아이디는 3~15자의 영문자, 숫자, 언더바(_)만 입력할 수 있습니다.")
                
                reg_password = st.text_input("새로운 비밀번호", type="password", key="reg_pass")
                st.caption("ℹ️ 비밀번호는 최소 8자 이상이며 영문자, 숫자, 특수문자를 혼합해야 합니다.")
                
                reg_password_confirm = st.text_input("비밀번호 확인", type="password", key="reg_pass_conf")
                
                reg_email = st.text_input("이메일 주소", key="reg_email")
                
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
                
                if st.button("회원가입 완료", use_container_width=True, type="primary"):
                    if not reg_username.strip() or not reg_password.strip() or not reg_email.strip():
                        st.error("모든 항목을 올바르게 입력해 주세요.")
                    elif not auth.is_valid_username(reg_username):
                        st.error("아이디는 3~15자의 영문자, 숫자, 언더스코어(_)만 허용됩니다.")
                    elif not auth.is_strong_password(reg_password)[0]:
                        st.error(auth.is_strong_password(reg_password)[1])
                    elif reg_password != reg_password_confirm:
                        st.error("비밀번호와 비밀번호 확인이 서로 일치하지 않습니다.")
                    elif not st.session_state['email_verified']:
                        st.error("이메일 인증을 먼저 완료해 주세요.")
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
    st.sidebar.header("⚙️ 설정 및 메뉴")
    st.sidebar.markdown(f"👤 **{st.session_state['username']}**님 환영합니다!")
    
    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        current_token = st.query_params.get("session_key", "")
        if current_token:
            auth.destroy_session(current_token)
            st.query_params.pop("session_key", None)
            
        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.rerun()
        
    st.sidebar.markdown("---")

    is_admin = st.session_state['username'].lower() == "admin"
    if is_admin:
        st.sidebar.subheader("⚙️ 관리자 전용 메뉴")
        admin_mode = st.sidebar.radio(
            "화면 모드 선택",
            ["📈 백테스터 실행", "💼 포트폴리오 분석", "📊 현재 포트폴리오 진단", "👥 가입 회원 관리"]
        )
        st.sidebar.markdown("---")
    else:
        st.sidebar.subheader("📂 메뉴 선택")
        admin_mode = st.sidebar.radio(
            "화면 모드 선택",
            ["📈 백테스터 실행", "💼 포트폴리오 분석", "📊 현재 포트폴리오 진단"]
        )
        st.sidebar.markdown("---")

    # =======================================================
    #                🔑 실시간 티커 사전 위젯 (공용)
    # =======================================================
    if admin_mode in ["📈 백테스터 실행", "💼 포트폴리오 분석", "📊 현재 포트폴리오 진단"]:
        with st.sidebar.expander("🔍 실시간 티커 검색기 (자동완성)", expanded=False):
            search_query = st.text_input("주식명 또는 철자 입력", value="", placeholder="예: AAPL, 삼성, NV")
            search_results = ticker_search.search_yahoo_tickers(search_query)
            
            selected_search_item = st.selectbox("검색 결과 (티커 복사용)", search_results)
            if selected_search_item:
                pure_symbol = selected_search_item.split(" ")[0]
                st.code(pure_symbol, language="text")
                st.caption("위의 박스 안 티커명을 더블클릭하거나 복사(Ctrl+C)하여 입력창에 붙여 넣으세요.")
                
                if admin_mode == "💼 포트폴리오 분석":
                    if st.button("➕ 포트폴리오에 즉시 추가"):
                        current_list = [t.strip().upper() for t in st.session_state['portfolio_tickers'].split(",") if t.strip()]
                        if pure_symbol not in current_list:
                            current_list.append(pure_symbol)
                            st.session_state['portfolio_tickers'] = ", ".join(current_list)
                            st.success(f"{pure_symbol}이(가) 포트폴리오 쉼표 목록에 추가되었습니다!")
                            st.rerun()

    # =======================================================
    #                      관리자 전용 대시보드 화면
    # =======================================================
    if is_admin and admin_mode == "👥 가입 회원 관리":
        st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">👥 가입 회원 관리 대시보드</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">서비스에 등록된 사용자들의 현황을 조회하고 엑셀 파일로 출력합니다.</p>', unsafe_allow_html=True)
        
        users_raw = auth.get_all_users()
        df_users = pd.DataFrame(users_raw, columns=["사용자 ID", "이메일 주소", "가입 일시"])
        
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
        st.dataframe(df_users, use_container_width=True)
        
        csv_data = df_users.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 회원 목록 CSV 다운로드 (Excel 호환)",
            data=csv_data,
            file_name=f"registered_users_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        st.markdown("<br><hr>", unsafe_allow_html=True)
        st.markdown("### ❌ 가입 회원 강제 탈퇴 처리")
        
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
    #                  💼 포트폴리오 분석 및 최적화
    # =======================================================
    elif admin_mode == "💼 포트폴리오 분석":
        st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">💼 Portfolio Visualizer 분석 엔진</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">자동 주기 리밸런싱, 매월 추가 적립 및 소르티노 지수와 상관관계 분석 보고서</p>', unsafe_allow_html=True)
        
        st.sidebar.subheader("1. 포트폴리오 구성 종목")
        tickers_input = st.sidebar.text_input("종목 티커 입력 (쉼표 구분)", value=st.session_state['portfolio_tickers'])
        st.session_state['portfolio_tickers'] = tickers_input
        parsed_tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
        
        today = datetime.today()
        default_start = today - timedelta(days=365 * 3)
        start_date = st.sidebar.date_input("분석 시작일", default_start)
        end_date = st.sidebar.date_input("분석 종료일", today)
        
        st.sidebar.subheader("2. 초기 자본 및 자금 흐름")
        initial_capital = st.sidebar.number_input("초기 투자 금액", min_value=1000, value=10000, step=1000)
        contribution_amount = st.sidebar.number_input("매월 추가 납입액 (적립금)", min_value=0, value=0, step=100)
        
        rebalance_period = st.sidebar.selectbox(
            "자산 비중 리밸런싱 주기 (Rebalancing)",
            ["None", "Monthly", "Quarterly", "Annually"]
        )
        
        st.sidebar.subheader("3. 자산별 투자 비중 설정")
        weights = []
        for ticker in parsed_tickers:
            w_val = st.sidebar.number_input(
                f"{ticker} 비중 (%)", 
                min_value=0.0, 
                max_value=100.0, 
                value=float(100.0 / len(parsed_tickers)) if len(parsed_tickers) > 0 else 0.0, 
                step=0.01, 
                format="%.2f"
            )
            weights.append(w_val)
            
        sum_weights = sum(weights)
        st.sidebar.markdown(f"**현재 비중 총합:** `{sum_weights:.2f}%` (반드시 **100%** 여야 함)")
        
        w_validation = (abs(sum_weights - 100.0) < 0.01)
        if not w_validation:
            st.sidebar.warning("⚠️ 모든 자산 비중의 총합이 정확하게 100.00%가 되도록 조정해 주세요.")
            
        run_port = st.sidebar.button("📊 포트폴리오 분석 실행", use_container_width=True, disabled=not w_validation)
        
        if run_port or 'port_run' not in st.session_state:
            st.session_state['port_run'] = True
            
            with st.spinner("다중 자산 주가 데이터를 분석하고 Portfolio Visualizer 엔진 시뮬레이션 수행 중..."):
                df_port = portfolio_engine.get_portfolio_data(parsed_tickers, start_date, end_date)
                
                if df_port is None or len(df_port) < 10:
                    st.error("충분한 주가 데이터를 확보하지 못했습니다. 입력하신 종목의 티커 및 수집 기간을 다시 확인하세요.")
                else:
                    # 1) 포트폴리오 결합 백테스트 (리밸런싱 & 적립식 포함)
                    port_weights = [w / 100.0 for w in weights]
                    res = portfolio_engine.backtest_portfolio(
                        df_port, port_weights, initial_capital, rebalance_period, contribution_amount
                    )
                    
                    # 2) MPT 포트폴리오 최적화 연산
                    opt_res = portfolio_engine.optimize_portfolio(df_port)
                    
                    # 요약 지표 카드 렌더링
                    st.markdown("### 🏆 포트폴리오 종합 성과 요약")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.markdown(
                            f"""<div class="metric-card">
                                <div class="metric-label">최종 포트폴리오 가치</div>
                                <div class="metric-value">{res['final_value']:,.2f}</div>
                                <div style="color: #94A3B8; font-size: 0.85rem;">
                                    총 투자 원금: {res['total_invested']:,.2f}
                                </div>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                    with col2:
                        st.markdown(
                            f"""<div class="metric-card">
                                <div class="metric-label">연평균 복리 수익률 (CAGR)</div>
                                <div class="metric-value">{res['cagr']:.2f}%</div>
                                <div style="color: {'#10B981' if res['total_return'] >= 0 else '#EF4444'}; font-weight: 600; font-size: 0.85rem;">
                                    총 수익률: {'+' if res['total_return'] >= 0 else ''}{res['total_return']:.2f}%
                                </div>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                    with col3:
                        st.markdown(
                            f"""<div class="metric-card">
                                <div class="metric-label">연도별 리스크 (변동성)</div>
                                <div class="metric-value" style="color: #AB63FA;">{res['std_dev']:.2f}%</div>
                                <div style="color: #94A3B8; font-size: 0.85rem;">
                                    포트폴리오 표준편차
                                </div>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                    with col4:
                        st.markdown(
                            f"""<div class="metric-card">
                                <div class="metric-label">최대 낙폭 (Max. Drawdown)</div>
                                <div class="metric-value" style="color: #EF4444;">{res['mdd']:.2f}%</div>
                                <div style="color: #94A3B8; font-size: 0.85rem;">
                                    고점 대비 최대 하락폭
                                </div>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                        
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # 2행 성과 리포트
                    col5, col6, col7, col8 = st.columns(4)
                    with col5:
                        st.markdown(
                            f"""<div class="metric-card">
                                <div class="metric-label">샤프 비율 (Sharpe Ratio)</div>
                                <div class="metric-value" style="color: #3B82F6;">{res['sharpe_ratio']:.2f}</div>
                                <div style="color: #94A3B8; font-size: 0.85rem;">
                                    위험 대비 보상 효율성
                                </div>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                    with col6:
                        st.markdown(
                            f"""<div class="metric-card">
                                <div class="metric-label">소르티노 비율 (Sortino Ratio)</div>
                                <div class="metric-value" style="color: #10B981;">{res['sortino_ratio']:.2f}</div>
                                <div style="color: #94A3B8; font-size: 0.85rem;">
                                    하방 위험(하락일) 대비 리턴
                                </div>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                    with col7:
                        st.markdown(
                            f"""<div class="metric-card">
                                <div class="metric-label">최고의 해 성과 (Best Year)</div>
                                <div class="metric-value" style="color: #10B981;">+{res['best_year']:.2f}%</div>
                                <div style="color: #94A3B8; font-size: 0.85rem;">
                                    최고 연도별 수익률
                                </div>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                    with col8:
                        st.markdown(
                            f"""<div class="metric-card">
                                <div class="metric-label">최악의 해 성과 (Worst Year)</div>
                                <div class="metric-value" style="color: #EF4444;">{res['worst_year']:.2f}%</div>
                                <div style="color: #94A3B8; font-size: 0.85rem;">
                                    최저 연도별 수익률
                                </div>
                            </div>""", 
                            unsafe_allow_html=True
                        )
                        
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    # 탭 기반 결과 분리 구성 (기능 대폭 추가)
                    tab_assets, tab_benchmarks, tab_correlation = st.tabs([
                        "📈 자산 성과 곡선 & 비중", 
                        "⚖️ 벤치마크 시장 비교", 
                        "🔗 자산 상관관계 분석"
                    ])
                    
                    with tab_assets:
                        col_chart1, col_chart2 = st.columns([1, 1.8])
                        
                        with col_chart1:
                            st.markdown("##### 🍩 현재 포트폴리오 자산 배분 비중")
                            donut_fig = go.Figure(data=[go.Pie(
                                labels=parsed_tickers,
                                values=weights,
                                hole=.4,
                                marker=dict(colors=['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#19D3F3', '#FF6692'])
                            )])
                            donut_fig.update_layout(
                                template="plotly_dark",
                                height=350,
                                margin=dict(l=10, r=10, t=10, b=10),
                                legend=dict(orientation="h", y=-0.1)
                            )
                            st.plotly_chart(donut_fig, use_container_width=True)
                            
                        with col_chart2:
                            st.markdown("##### 📈 자산별 누적 자산 성장 곡선 (적립금 반영)")
                            line_fig = go.Figure()
                            
                            line_fig.add_trace(go.Scatter(
                                x=res['df'].index,
                                y=res['df']['Portfolio_Value'],
                                name="내 포트폴리오",
                                line=dict(color="#F1C40F", width=3)
                            ))
                            
                            for ticker in parsed_tickers:
                                p_shares = 0.0
                                p_cash = initial_capital
                                p_values = []
                                p_prices = df_port[ticker].values
                                p_dates = df_port.index
                                
                                p_shares = p_cash / p_prices[0]
                                p_cash = 0.0
                                p_values.append(initial_capital)
                                
                                p_prev_date = p_dates[0]
                                for idx in range(1, len(df_port)):
                                    c_date = p_dates[idx]
                                    c_price = p_prices[idx]
                                    
                                    if c_date.month != p_prev_date.month and contribution_amount > 0:
                                        p_shares += (contribution_amount / c_price)
                                        
                                    p_values.append(p_shares * c_price)
                                    p_prev_date = c_date
                                    
                                line_fig.add_trace(go.Scatter(
                                    x=df_port.index,
                                    y=p_values,
                                    name=f"{ticker} (100% 몰빵)",
                                    line=dict(width=1.2, dash="dash")
                                ))
                                
                            line_fig.update_layout(
                                template="plotly_dark",
                                height=350,
                                margin=dict(l=20, r=20, t=10, b=20),
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                            )
                            st.plotly_chart(line_fig, use_container_width=True)
                            
                    with tab_benchmarks:
                        st.markdown("##### ⚖️ 내 포트폴리오 vs 주요 시장 지수 (SPY, QQQ) 정밀 성과 비교")
                        st.write("초기 자본과 자금 흐름(적립금) 조건이 시장 지수에 동일하게 투자되었을 때의 성과 대조 보고서입니다.")
                        
                        # 벤치마크 SPY, QQQ 데이터 다운로드
                        bench_tickers = ["SPY", "QQQ"]
                        df_bench = portfolio_engine.get_portfolio_data(bench_tickers, start_date, end_date)
                        
                        if df_bench is not None and not df_bench.empty:
                            # 벤치마크 백테스트 실행 (100% 비중으로 가상 구성)
                            spy_res = portfolio_engine.backtest_portfolio(
                                pd.DataFrame(df_bench["SPY"]), [1.0], initial_capital, rebalance_period, contribution_amount
                            )
                            qqq_res = portfolio_engine.backtest_portfolio(
                                pd.DataFrame(df_bench["QQQ"]), [1.0], initial_capital, rebalance_period, contribution_amount
                            )
                            
                            # 비교 데이터프레임 빌드
                            comp_data = {
                                "자산명": ["내 포트폴리오", "S&P 500 (SPY)", "Nasdaq 100 (QQQ)"],
                                "최종 가치": [res["final_value"], spy_res["final_value"], qqq_res["final_value"]],
                                "총 수익률": [res["total_return"], spy_res["total_return"], qqq_res["total_return"]],
                                "연평균 수익률 (CAGR)": [res["cagr"], spy_res["cagr"], qqq_res["cagr"]],
                                "연간 변동성": [res["std_dev"], spy_res["std_dev"], qqq_res["std_dev"]],
                                "샤프 비율 (Sharpe)": [res["sharpe_ratio"], spy_res["sharpe_ratio"], qqq_res["sharpe_ratio"]],
                                "소르티노 비율 (Sortino)": [res["sortino_ratio"], spy_res["sortino_ratio"], qqq_res["sortino_ratio"]],
                                "최대 낙폭 (MDD)": [res["mdd"], spy_res["mdd"], qqq_res["mdd"]]
                            }
                            df_comp = pd.DataFrame(comp_data)
                            
                            st.dataframe(
                                df_comp.style.format({
                                    "최종 가치": "{:,.2f}",
                                    "총 수익률": "{:+.2f}%",
                                    "연평균 수익률 (CAGR)": "{:.2f}%",
                                    "연간 변동성": "{:.2f}%",
                                    "샤프 비율 (Sharpe)": "{:.2f}",
                                    "소르티노 비율 (Sortino)": "{:.2f}",
                                    "최대 낙폭 (MDD)": "{:.2f}%"
                                }),
                                use_container_width=True,
                                hide_index=True
                            )
                            
                            # 3자 성과 곡선 렌더링
                            bench_fig = go.Figure()
                            bench_fig.add_trace(go.Scatter(x=res['df'].index, y=res['df']['Portfolio_Value'], name="내 포트폴리오", line=dict(color="#F1C40F", width=3)))
                            bench_fig.add_trace(go.Scatter(x=spy_res['df'].index, y=spy_res['df']['Portfolio_Value'], name="S&P 500 (SPY)", line=dict(color="#FF4B4B", width=1.5, dash="dash")))
                            bench_fig.add_trace(go.Scatter(x=qqq_res['df'].index, y=qqq_res['df']['Portfolio_Value'], name="Nasdaq 100 (QQQ)", line=dict(color="#00CC96", width=1.5, dash="dot")))
                            
                            bench_fig.update_layout(
                                template="plotly_dark",
                                height=350,
                                margin=dict(l=20, r=20, t=10, b=20),
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                            )
                            st.plotly_chart(bench_fig, use_container_width=True)
                        else:
                            st.info("비교 벤치마크 데이터를 로드할 수 없습니다.")
                            
                    with tab_correlation:
                        st.markdown("##### 🔗 구성 자산 간 상관관계 행렬 (Correlation Matrix) 히트맵")
                        st.write("자산들 사이의 상관계수는 -1.0(반대 방향)부터 +1.0(완벽히 같은 방향)까지 나타나며, 상관계수가 낮을수록 포트폴리오 분산 투자 위험 회피 효과가 우수합니다.")
                        
                        corr_df = portfolio_engine.calculate_correlation(df_port)
                        
                        # 히트맵 시각화
                        heatmap_fig = go.Figure(data=go.Heatmap(
                            z=corr_df.values,
                            x=corr_df.columns,
                            y=corr_df.index,
                            colorscale='RdBu_r', # Red-Blue 스케일로 상관도가 높으면 붉은색, 낮으면 파란색 매핑
                            zmin=-1.0,
                            zmax=1.0,
                            text=[[f"{val:.2f}" for val in row] for row in corr_df.values],
                            texttemplate="%{text}",
                            hoverongaps=False
                        ))
                        heatmap_fig.update_layout(
                            template="plotly_dark",
                            height=350,
                            margin=dict(l=40, r=40, t=10, b=40),
                        )
                        st.plotly_chart(heatmap_fig, use_container_width=True)
                        
                    # ----------------- 📊 연도별 수익률 막대 차트 -----------------
                    st.markdown("<br>", unsafe_allow_html=True)
                    st.markdown("### 📊 연도별 수익률 통계 (Annual Returns)")
                    
                    df_yr = pd.DataFrame(res['yearly_returns'])
                    if not df_yr.empty:
                        col_yr1, col_yr2 = st.columns([2, 1])
                        
                        with col_yr1:
                            bar_fig = go.Figure(data=[go.Bar(
                                x=df_yr['Year'],
                                y=df_yr['Return'],
                                marker_color=['#10B981' if r >= 0 else '#EF4444' for r in df_yr['Return']],
                                text=[f"{r:+.1f}%" for r in df_yr['Return']],
                                textposition='auto'
                            )])
                            bar_fig.update_layout(
                                template="plotly_dark",
                                height=300,
                                xaxis_title="연도 (Year)",
                                yaxis_title="연간 수익률 (%)",
                                margin=dict(l=40, r=20, t=10, b=35)
                            )
                            st.plotly_chart(bar_fig, use_container_width=True)
                            
                        with col_yr2:
                            df_yr_styled = df_yr.copy()
                            df_yr_styled['Return'] = df_yr_styled['Return'].map(lambda x: f"{x:+.2f}%")
                            st.dataframe(
                                df_yr_styled.set_index('Year'),
                                use_container_width=True
                            )
                        
                    # 몬테카를로 최적화 포트폴리오 추천 카드 (Sharpe Ratio Optimizer)
                    st.markdown("<br><hr>", unsafe_allow_html=True)
                    st.markdown("### 🧬 효율적 투자선 (Efficient Frontier) 및 최적의 비중 추천")
                    st.markdown("현대 포트폴리오 이론(MPT)에 입각하여 리스크(Volatility) 대비 기대 수익률(Sharpe Ratio)을 최대화하는 최적의 자산 배분 비중을 추천해 드립니다.")
                    
                    col_opt1, col_opt2 = st.columns(2)
                    
                    with col_opt1:
                        st.markdown('<div class="opt-card">', unsafe_allow_html=True)
                        st.markdown("##### 🔥 위험 대비 수익 극대화 (Max Sharpe Ratio)")
                        st.markdown(f"**연평균 기대 수익률:** `{opt_res['max_sharpe']['return']:.2f}%` / **예상 변동성:** `{opt_res['max_sharpe']['volatility']:.2f}%` / **샤프 비율:** `{opt_res['max_sharpe']['sharpe']:.2f}`")
                        st.markdown("**권장 비중 포트폴리오:**")
                        for t, w in opt_res['max_sharpe']['weights'].items():
                            st.write(f"- **{t}**: `{w:.1f}%` 비중")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    with col_opt2:
                        st.markdown('<div class="opt-card" style="border-color: #00CC96;">', unsafe_allow_html=True)
                        st.markdown("##### 🛡️ 포트폴리오 리스크 최소화 (Minimum Volatility)")
                        st.markdown(f"**연평균 기대 수익률:** `{opt_res['min_vol']['return']:.2f}%` / **예상 변동성:** `{opt_res['min_vol']['volatility']:.2f}%` / **샤프 비율:** `{opt_res['min_vol']['sharpe']:.2f}`")
                        st.markdown("**권장 비중 포트폴리오:**")
                        for t, w in opt_res['min_vol']['weights'].items():
                            st.write(f"- **{t}**: `{w:.1f}%` 비중")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                    # 효율적 투자선 산점도
                    st.markdown("##### 📊 2,000개 포트폴리오 비중 시뮬레이션 산점도")
                    sim_data = opt_res['raw_sim']
                    
                    scat_fig = go.Figure()
                    scat_fig.add_trace(go.Scatter(
                        x=sim_data['Volatility'] * 100,
                        y=sim_data['Return'] * 100,
                        mode='markers',
                        marker=dict(
                            size=5,
                            color=sim_data['Sharpe'],
                            colorscale='Viridis',
                            showscale=True,
                            colorbar=dict(title="Sharpe Ratio")
                        ),
                        name="시뮬레이션 포트폴리오"
                    ))
                    
                    scat_fig.add_trace(go.Scatter(
                        x=[opt_res['max_sharpe']['volatility']],
                        y=[opt_res['max_sharpe']['return']],
                        mode='markers',
                        marker=dict(symbol='star', size=15, color='#FF4B4B', line=dict(width=1, color='white')),
                        name="Max Sharpe"
                    ))
                    
                    scat_fig.add_trace(go.Scatter(
                        x=[opt_res['min_vol']['volatility']],
                        y=[opt_res['min_vol']['return']],
                        mode='markers',
                        marker=dict(symbol='diamond', size=12, color='#00CC96', line=dict(width=1, color='white')),
                        name="Min Volatility"
                    ))
                    
                    scat_fig.update_layout(
                        template="plotly_dark",
                        height=450,
                        xaxis_title="리스크 (연간 변동성, %)",
                        yaxis_title="기대 수익률 (%)",
                        margin=dict(l=40, r=20, t=20, b=40)
                    )
                    st.plotly_chart(scat_fig, use_container_width=True)

    # =======================================================
    #            📊 실시간 보유 자산 트래커 & 위험 진단
    # =======================================================
    elif admin_mode == "📊 현재 포트폴리오 진단":
        st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">📊 실시간 보유 자산 트래커</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">내가 현재 실제로 들고 있는 개별 주식들의 평단가와 수량을 입력하여 실시간 평가 손익 및 리스크를 분석합니다.</p>', unsafe_allow_html=True)
        
        st.markdown("### 📝 실시간 보유 주식 정보 입력")
        st.info("💡 아래 테이블을 더블클릭하여 내 주식의 '티커(예: AAPL)', '평단가', '보유 수량'을 수정하거나 아래 행을 추가/삭제하여 나만의 자산을 등록하세요. 왼쪽 사이드바의 [실시간 티커 검색기]를 통해 정확한 티커 알파벳을 복사해 기입하실 수 있습니다.")
        
        # 기본 보유 포트폴리오 테이블 뼈대 (DB 데이터가 존재 시 복원하고, 없을 경우에만 예시 표 노출)
        if 'my_portfolio_data' not in st.session_state:
            db_port = auth.get_user_portfolio(st.session_state['username'])
            if db_port:
                st.session_state['my_portfolio_data'] = pd.DataFrame(db_port)
            else:
                st.session_state['my_portfolio_data'] = pd.DataFrame([
                    {"티커": "AAPL", "매수 평단가": 170.0, "보유 수량": 10.0},
                    {"티커": "NVDA", "매수 평단가": 100.0, "보유 수량": 25.0},
                    {"티커": "TSLA", "매수 평단가": 240.0, "보유 수량": 5.0}
                ])
            
        # 💡 st.data_editor에 on_change 콜백(sync_editor_data)을 직접 적용하여 Rerun 시 숫자 유실 현상 차단
        edited_df = st.data_editor(
            st.session_state['my_portfolio_data'],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "티커": st.column_config.TextColumn("주식 티커 (예: AAPL)", width="medium", required=True),
                "매수 평단가": st.column_config.NumberColumn("매수 평단가 ($ 또는 ₩)", min_value=0.0, format="%.2f", required=True),
                "보유 수량": st.column_config.NumberColumn("보유 주식 수 (주)", min_value=0.0, format="%.2f", required=True)
            },
            key="portfolio_editor",
            on_change=sync_editor_data  # 실시간 상태 보존 콜백 엔진 연동!
        )
        
        # 콜백이 실행되어 세션 값이 바뀐 후 화면 렌더링에 사용할 임시 DF 매핑
        df_for_calc = st.session_state['my_portfolio_data']
        
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            calc_run = st.button("📊 실시간 보유 자산 분석하기", type="primary", use_container_width=True)
            
        if calc_run or 'calc_run_state' not in st.session_state:
            st.session_state['calc_run_state'] = True
            
            df_valid = df_for_calc.dropna(subset=["티커", "매수 평단가", "보유 수량"])
            df_valid = df_valid[df_valid["티커"].str.strip() != ""]
            
            if df_valid.empty:
                st.warning("⚠️ 분석할 보유 자산 정보를 최소 한 종목 이상 입력해 주세요.")
            else:
                with st.spinner("실시간 시장 가격을 야후 파이낸스(yfinance)로부터 수집 중..."):
                    results = []
                    total_buy_value = 0.0
                    total_eval_value = 0.0
                    
                    has_error = False
                    error_ticker = ""
                    
                    for _, row in df_valid.iterrows():
                        ticker = row["티커"].strip().upper()
                        buy_price = float(row["매수 평단가"])
                        shares = float(row["보유 수량"])
                        
                        try:
                            raw_df = yf.download(ticker, period="1d")
                            if raw_df.empty:
                                has_error = True
                                error_ticker = ticker
                                break
                                
                            if isinstance(raw_df.columns, pd.MultiIndex):
                                raw_df.columns = raw_df.columns.get_level_values(0)
                                
                            curr_price = float(raw_df['Close'].iloc[-1])
                        except Exception:
                            has_error = True
                            error_ticker = ticker
                            break
                            
                        buy_val = buy_price * shares
                        eval_val = curr_price * shares
                        profit_val = eval_val - buy_val
                        profit_pct = (profit_val / buy_val) * 100 if buy_val > 0 else 0
                        
                        total_buy_value += buy_val
                        total_eval_value += eval_val
                        
                        results.append({
                            "티커": ticker,
                            "평단가": buy_price,
                            "현재가": curr_price,
                            "보유수량": shares,
                            "매입금액": buy_val,
                            "평가금액": eval_val,
                            "평가손익": profit_val,
                            "수익률": profit_pct
                        })
                        
                    if has_error:
                        st.error(f"티커 '{error_ticker}'의 실시간 시세를 가져오는데 실패했습니다. 올바른 해외/국내 주식 티커인지 다시 확인해 주세요.")
                    else:
                        df_res = pd.DataFrame(results)
                        
                        total_profit = total_eval_value - total_buy_value
                        total_profit_pct = (total_profit / total_buy_value) * 100 if total_buy_value > 0 else 0
                        
                        st.markdown("### 🏆 실시간 보유 자산 총계 요약")
                        c_m1, c_m2, c_m3, c_m4 = st.columns(4)
                        
                        with c_m1:
                            st.markdown(
                                f"""<div class="metric-card">
                                    <div class="metric-label">총 매입 자산 (원금)</div>
                                    <div class="metric-value">{total_buy_value:,.2f}</div>
                                </div>""", 
                                unsafe_allow_html=True
                            )
                        with c_m2:
                            st.markdown(
                                f"""<div class="metric-card">
                                    <div class="metric-label">총 평가 자산 (현재가)</div>
                                    <div class="metric-value" style="color: #3B82F6;">{total_eval_value:,.2f}</div>
                                </div>""", 
                                unsafe_allow_html=True
                            )
                        with c_m3:
                            st.markdown(
                                f"""<div class="metric-card">
                                    <div class="metric-label">총 평가 손익</div>
                                    <div class="metric-value" style="color: {'#10B981' if total_profit >= 0 else '#EF4444'};">
                                        {'+' if total_profit >= 0 else ''}{total_profit:,.2f}
                                    </div>
                                </div>""", 
                                unsafe_allow_html=True
                            )
                        with c_m4:
                            st.markdown(
                                f"""<div class="metric-card">
                                    <div class="metric-label">총 포트폴리오 수익률</div>
                                    <div class="metric-value" style="color: {'#10B981' if total_profit_pct >= 0 else '#EF4444'};">
                                        {'+' if total_profit_pct >= 0 else ''}{total_profit_pct:.2f}%
                                    </div>
                                </div>""", 
                                unsafe_allow_html=True
                            )
                            
                        st.markdown("<br>##### 📊 자산별 실시간 평가 손익 현황", unsafe_allow_html=True)
                        
                        col_cards = st.columns(len(df_res))
                        for idx, row in df_res.iterrows():
                            card_col = col_cards[idx % len(df_res)]
                            is_profit = row['평가손익'] >= 0
                            color_card = "#10B981" if is_profit else "#EF4444"
                            sign_card = "+" if is_profit else ""
                            arrow_card = "▲" if is_profit else "▼"
                            
                            card_col.markdown(f"""
                                <div class="spark-card" style="border-left: 5px solid {color_card};">
                                    <div style="font-size: 1.1rem; font-weight: 800; color: #F8FAFC;">{row['티커']}</div>
                                    <div style="font-size: 0.8rem; color: #94A3B8; margin-top: 0.2rem;">
                                        평단: {row['평단가']:,.2f} / 현재가: {row['현재가']:,.2f}
                                    </div>
                                    <hr style="border: 0; border-top: 1px solid #334155; margin: 8px 0;">
                                    <div style="font-size: 0.85rem; color: #94A3B8;">보유량: {row['보유수량']:.1f} 주</div>
                                    <div style="font-size: 0.85rem; color: #94A3B8;">평가액: {row['평가금액']:,.2f}</div>
                                    <div style="font-size: 1.1rem; font-weight: 700; color: {color_card}; margin-top: 0.4rem;">
                                        {arrow_card} {sign_card}{row['평가손익']:,.2f} ({sign_card}{row['수익률']:.2f}%)
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                            
                        st.markdown("<br>", unsafe_allow_html=True)
                        c_div1, c_div2 = st.columns([1.2, 1.8])
                        
                        with c_div1:
                            st.markdown("##### 🍩 실시간 자산 배분 비중")
                            live_donut = go.Figure(data=[go.Pie(
                                labels=df_res['티커'].tolist(),
                                values=df_res['평가금액'].tolist(),
                                hole=.4,
                                marker=dict(colors=['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#19D3F3'])
                            )])
                            live_donut.update_layout(
                                template="plotly_dark",
                                height=300,
                                margin=dict(l=10, r=10, t=10, b=10),
                                legend=dict(orientation="h", y=-0.1)
                            )
                            st.plotly_chart(live_donut, use_container_width=True)
                            
                        with c_div2:
                            st.markdown("##### 🛡️ 포트폴리오 리스크 진단 및 조언")
                            
                            diagnostics = []
                            num_tickers = len(df_res)
                            
                            if num_tickers <= 2:
                                diagnostics.append({
                                    "type": "warning",
                                    "title": "⚠️ 극심한 자산 집중 위험 감지",
                                    "desc": f"현재 보유 종목 수({num_tickers}개)가 너무 적어 특정 기업의 개별 악재(어닝 쇼크 등) 시 포트폴리오 전체가 큰 충격을 받습니다. 최소 3~5개 이상의 상관관계가 낮은 종목이나 시장 지수 ETF(SPY, QQQ)에 분산하는 것을 추천합니다."
                                })
                                
                            for _, r in df_res.iterrows():
                                ratio = (r["평가금액"] / total_eval_value) * 100
                                if ratio > 50.0:
                                    diagnostics.append({
                                        "type": "warning",
                                        "title": f"⚠️ 특정 자산 쏠림 주의 ({r['티커']})",
                                        "desc": f"현재 '{r['티커']}' 종목이 전체 자산의 {ratio:.1f}%를 차지하고 있어 자산 쏠림 위험이 높습니다. '💼 포트폴리오 분석' 메뉴에서 자산 배분 리밸런싱을 설계해 분산 효과를 극대화해 보세요."
                                    })
                                    
                            if not diagnostics:
                                diagnostics.append({
                                    "type": "success",
                                    "title": "🟢 매우 이상적인 자산 다각화 상태",
                                    "desc": "보유 종목 수가 적절하고, 특정 자산에 과도한 쏠림 없이 자금이 안정적으로 배분되어 있습니다. 시장 변동성이 오더라도 극단적인 손실(Tail Risk)을 효율적으로 방어할 수 있는 모범적인 상태입니다."
                                })
                                
                            for diag in diagnostics:
                                color_border = "#FF4B4B" if diag["type"] == "warning" else "#10B981"
                                st.markdown(f"""
                                    <div class="opt-card" style="border-color: {color_border}; margin-bottom: 0.8rem;">
                                        <div style="font-weight: 800; font-size: 1.05rem; color: #F8FAFC; margin-bottom: 0.4rem;">{diag['title']}</div>
                                        <div style="font-size: 0.9rem; color: #94A3B8; line-height: 1.4;">{diag['desc']}</div>
                                    </div>
                                """, unsafe_allow_html=True)

    # =======================================================
    #                      기존 백테스터 화면
    # =======================================================
    else:
        st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">📊 Dynamic Stock Backtester</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">수정 종가(Adjusted Close)와 정밀한 슬리피지/세금을 반영한 실전용 백테스터</p>', unsafe_allow_html=True)

        st.sidebar.subheader("1. 대상 종목 & 기간")
        st.sidebar.write("🔍 실시간 티커 사전 위젯을 통해 검색한 정확한 티커명을 아래에 입력하세요.")
        ticker_input = st.sidebar.text_input("주식 티커 입력 (yfinance 규격)", value="AAPL")
        st.sidebar.caption("💡 팁: 나스닥은 'AAPL', 'TSLA' 등 / 코스피는 '005930.KS', 코스닥은 '091990.KQ'")

        today = datetime.today()
        default_start = today - timedelta(days=365 * 3)
        start_date = st.sidebar.date_input("시작일", default_start)
        end_date = st.sidebar.date_input("종료일", today)

        st.sidebar.subheader("2. 실전 투자 조건")
        initial_capital = st.sidebar.number_input("초기 투자금 ($ 또는 ₩)", min_value=1000, value=10000, step=1000)
        commission_pct = st.sidebar.slider("증권사 수수료 (%)", min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100.0
        slippage_pct = st.sidebar.slider("슬리피지 (Slippage, %)", min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100.0
        tax_pct = st.sidebar.slider("거래세 (Tax, %)", min_value=0.0, max_value=1.0, value=0.18, step=0.02) / 100.0

        st.sidebar.subheader("3. 비교 벤치마크 지수")
        benchmark_option = st.sidebar.selectbox(
            "비교 대상 시장 지수", 
            ["선택 안 함", "S&P 500 (^GSPC)", "Nasdaq 100 (QQQ)", "KOSPI (^KS11)", "KOSDAQ (^KQ11)"]
        )

        st.sidebar.subheader("4. 이동평균선(SMA) 설정")
        short_window = st.sidebar.number_input("단기 이평선 기간 (일)", min_value=2, max_value=100, value=20)
        long_window = st.sidebar.number_input("장기 이평선 기간 (일)", min_value=5, max_value=300, value=50)

        if short_window >= long_window:
            st.sidebar.error("단기 이평선 기간은 장기 이평선 기간보다 작아야 합니다!")

        run_button = st.sidebar.button("⚡ 백테스트 실행", use_container_width=True)

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

                        results = run_backtest(df, short_window, long_window, initial_capital, commission_pct, slippage_pct, tax_pct)
                        metrics = calculate_metrics(results, initial_capital, benchmark_df)
                        
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
                        st.markdown("### 📈 인터랙티브 차트 분석")
                        
                        fig = make_subplots(
                            rows=2, cols=1, 
                            shared_xaxes=True, 
                            vertical_spacing=0.08,
                            row_heights=[0.6, 0.4]
                        )
                        
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Close'], name='Close Price', line=dict(color='#636EFA', width=1.5)),
                            row=1, col=1
                        )
                        
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Short_SMA'], name=f'{short_window} SMA', line=dict(color='#00CC96', width=1, dash='dash')),
                            row=1, col=1
                        )
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Long_SMA'], name=f'{long_window} SMA', line=dict(color='#EF553B', width=1, dash='dash')),
                            row=1, col=1
                        )
                        
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
                        
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Portfolio_Value'], name='SMA Strategy', line=dict(color='#F1C40F', width=2)),
                            row=2, col=1
                        )
                        fig.add_trace(
                            go.Scatter(x=results.index, y=results['Buy_Hold_Value'], name='Buy & Hold', line=dict(color='#7F8C8D', width=1.5, dash='dot')),
                            row=2, col=1
                        )
                        
                        if benchmark_df is not None:
                            fig.add_trace(
                                go.Scatter(x=benchmark_df.index, y=benchmark_df['Benchmark_Value'], name=benchmark_option, line=dict(color='#9B59B6', width=1.5, dash='dashdot')),
                                row=2, col=1
                            )
                        
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
