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
import risk_profiler  # 구성 자산 고유 위험도 프로파일링 모듈 임포트
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

# 최근 5일 미니 스파크라인용 데이터 수집 캐싱 (최경량 고속화)
@st.cache_data(ttl=1800) # 30분 캐싱
def load_sparkline_data(ticker):
    try:
        # period를 5d로 축소하여 통신 패킷 최소화, timeout 및 스레드 비활성화로 로딩 렉 원천 방지
        data = yf.download(ticker, period="5d", interval="1d", progress=False, threads=False, timeout=2.0)
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
def get_live_cnn_data():
    """
    CNN Markets 공식 REST API로부터 공포와 탐욕 및 7대 하부 지수 데이터를 모두 실시간 연동.
    실패 시 None 반환하여 폴백 가동 유도.
    """
    import requests
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=3.5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

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
@st.fragment(run_every=30)
def render_live_dashboard():
    # 3대 핵심 시장 지수 단독 고정으로 로딩 패킷 최소화 (코스피, 나스닥, S&P 500)
    indices = [
        {"name": "코스피", "ticker": "^KS11", "currency": ""},
        {"name": "나스닥", "ticker": "^IXIC", "currency": ""},
        {"name": "S&P 500", "ticker": "^GSPC", "currency": ""}
    ]
    
    col_a, col_b, col_c = st.columns(3)
    cols = [col_a, col_b, col_c]
    
    # 야후 파이낸스 차단 또는 로딩 렉 대비 가상 5일 주가 데이터 생성기 (Fallback)
    def get_fallback_spark_data(ticker):
        dates = [datetime.now() - timedelta(days=i) for i in range(5)]
        dates.reverse()
        if ticker == "^KS11":
            base_val = 2635.80
        elif ticker == "^IXIC":
            base_val = 18120.45
        else:
            base_val = 5410.20
        # 모사 노이즈 추가
        prices = [base_val * (1 + 0.0035 * i + (0.002 * (i % 2 - 1))) for i in range(5)]
        df = pd.DataFrame({"Close": prices}, index=dates)
        return df

    for i, stock in enumerate(indices):
        col = cols[i]
        
        # yfinance 다운로드 시도 (timeout=1.2초로 무한 로딩 차단)
        stock_data = load_sparkline_data(stock['ticker'])
        is_fallback = False
        
        # yfinance 실패 시 즉시 Mock 데이터로 대체 (로딩 속도 보장)
        if stock_data is None or len(stock_data) < 2:
            stock_data = get_fallback_spark_data(stock['ticker'])
            is_fallback = True
            
        close_prices = stock_data['Close'].values.flatten()
        curr_price = float(close_prices[-1])
        prev_price = float(close_prices[-2])
        
        change_val = curr_price - prev_price
        change_pct = (change_val / prev_price) * 100
        is_positive = change_val >= 0
        color_hex = "#10B981" if is_positive else "#EF4444"
        sign = "+" if is_positive else ""
        arrow = "▲" if is_positive else "▼"
        
        fallback_indicator = " (실시간)" if not is_fallback else " (지연)"
        
        col.markdown(f"""
            <div class="spark-card">
                <div style="font-size: 0.85rem; color: #94A3B8; font-weight: 600; text-transform: uppercase;">{stock['name']}{fallback_indicator}</div>
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
            key=f"spark_chart_locked_{stock['ticker']}"
        )

# ----------------- 🛠️ 실시간 데이터 에디터 유실 종결 콜백 -----------------
def sync_editor_data():
    """st.data_editor의 임시 변경 상태를 세션 상태에 즉시 동기화 보존"""
    if 'portfolio_editor' in st.session_state:
        edits = st.session_state.portfolio_editor
        
        # 💡 중요: 엔터를 연속해서 누르거나 빈 딕셔너리({}) 상태가 들어올 때, 데이터 오작동 및 덮어쓰기를 방어하기 위해 리턴
        if not edits.get('edited_rows') and not edits.get('added_rows') and not edits.get('deleted_rows'):
            return
            
        df = st.session_state['my_portfolio_data'].copy()
        
        # 1. 수정한 셀(edited_rows) 반영
        for idx, changes in edits.get('edited_rows', {}).items():
            for col, val in changes.items():
                if idx < len(df):
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
            ["📈 백테스터 실행", "💼 포트폴리오 분석", "📊 현재 포트폴리오 진단", "🚨 시장 위험 지표", "👥 가입 회원 관리"]
        )
        st.sidebar.markdown("---")
    else:
        st.sidebar.subheader("📂 메뉴 선택")
        admin_mode = st.sidebar.radio(
            "화면 모드 선택",
            ["📈 백테스터 실행", "💼 포트폴리오 분석", "📊 현재 포트폴리오 진단", "🚨 시장 위험 지표"]
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
        
        # 🛠️ 본문 설정 입력 카드 (오른쪽 메인 대시보드 내)
        with st.expander("🛠️ 포트폴리오 구성 & 자산 비중 설정 입력 패널", expanded=True):
            col_t1, col_t2 = st.columns([3, 2])
            with col_t1:
                tickers_input = st.text_input("종목 티커 입력 (쉼표 구분)", value=st.session_state.get('portfolio_tickers', "AAPL, MSFT, GOOG"))
                st.session_state['portfolio_tickers'] = tickers_input
                parsed_tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]
            with col_t2:
                today = datetime.today()
                default_start = today - timedelta(days=365 * 3)
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    start_date = st.date_input("분석 시작일", default_start)
                with col_d2:
                    end_date = st.date_input("분석 종료일", today)
                    
            st.markdown("<div style='border-top: 1px solid #334155; margin: 0.8rem 0;'></div>", unsafe_allow_html=True)
            
            col_cap1, col_cap2, col_cap3 = st.columns(3)
            with col_cap1:
                initial_capital = st.number_input("초기 투자 금액", min_value=1000, value=10000, step=1000)
            with col_cap2:
                contribution_amount = st.number_input("매월 추가 납입액 (적립금)", min_value=0, value=0, step=100)
            with col_cap3:
                rebalance_period = st.selectbox(
                    "자산 비중 리밸런싱 주기",
                    ["None", "Monthly", "Quarterly", "Annually"]
                )
                
            st.markdown("<div style='border-top: 1px solid #334155; margin: 0.8rem 0;'></div>", unsafe_allow_html=True)
            st.markdown("##### ⚖️ 자산별 투자 비중 설정 (%)")
            
            weights = []
            if parsed_tickers:
                num_cols = min(6, len(parsed_tickers))
                ticker_cols = st.columns(num_cols)
                for idx, ticker in enumerate(parsed_tickers):
                    col_target = ticker_cols[idx % num_cols]
                    with col_target:
                        w_val = st.number_input(
                            f"{ticker}", 
                            min_value=0.0, 
                            max_value=100.0, 
                            value=float(100.0 / len(parsed_tickers)) if len(parsed_tickers) > 0 else 0.0, 
                            step=0.01, 
                            format="%.2f",
                            key=f"weight_{ticker}"
                        )
                        weights.append(w_val)
            else:
                st.info("위에 분석할 티커 목록을 입력해 주세요.")
                
            sum_weights = sum(weights)
            w_validation = (abs(sum_weights - 100.0) < 0.01)
            
            col_sub1, col_sub2 = st.columns([3.2, 1])
            with col_sub1:
                if w_validation:
                    st.success(f"✓ 비중 총합: **{sum_weights:.2f}%** (분석 가능한 정상 수치입니다.)")
                else:
                    st.warning(f"⚠️ 현재 비중 총합: **{sum_weights:.2f}%** (100.00%를 정확히 맞춰야 활성화됩니다.)")
            with col_sub2:
                run_port = st.button("📊 포트폴리오 분석 실행", use_container_width=True, disabled=not w_validation)
                
        if run_port:
            st.session_state['port_run_triggered'] = True
            
        if st.session_state.get('port_run_triggered', False):
            
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
                    
                    # 🚨 구성 자산별 위험 특성 진단 보고서 (Asset Risk Profiling) 신설
                    st.markdown("<br><hr>", unsafe_allow_html=True)
                    st.markdown("### 🚨 구성 자산별 고유 위험 특성 프로파일링 (Asset Risk Profiling)")
                    st.markdown("포트폴리오에 구성된 개별 자산의 성격(레버리지, 인버스, 암호화폐 등) 및 통계적 변동성을 파악하여 리스크 속성을 점검해 드립니다.")
                    
                    found_any_risk = False
                    for ticker in parsed_tickers:
                        try:
                            # 일별 수익률 표준편차의 연율화 변동성 계산
                            daily_std = df_port[ticker].pct_change().std()
                            ann_vol = float(daily_std * np.sqrt(252) * 100)
                        except Exception:
                            ann_vol = None
                            
                        asset_risks = risk_profiler.profile_asset_risk(ticker, ann_vol)
                        for ar in asset_risks:
                            found_any_risk = True
                            st.markdown(f"""
                                <div class="opt-card" style="border-color: {ar['color']}; margin-bottom: 0.8rem;">
                                    <div style="font-weight: 800; font-size: 1.05rem; color: #F8FAFC; margin-bottom: 0.4rem;">{ar['title']} ({ar['level']})</div>
                                    <div style="font-size: 0.9rem; color: #94A3B8; line-height: 1.4;">{ar['desc']}</div>
                                </div>
                            """, unsafe_allow_html=True)
                            
                    if not found_any_risk:
                        st.markdown("""
                            <div class="opt-card" style="border-color: #10B981; margin-bottom: 0.8rem;">
                                <div style="font-weight: 800; font-size: 1.05rem; color: #F8FAFC; margin-bottom: 0.4rem;">🟢 포트폴리오 자산 구성 안전성 양호</div>
                                <div style="font-size: 0.9rem; color: #94A3B8; line-height: 1.4;">포트폴리오 내에 2배/3배 레버리지, 인버스, 암호화폐 연동 자산 등의 고위험 복리 침식 자산이 감지되지 않았습니다. 장기 가치 보존 및 복리 배분에 이상적인 보수적 배분입니다.</div>
                            </div>
                        """, unsafe_allow_html=True)

    # =======================================================
    #            📊 실시간 보유 자산 트래커 & 위험 진단
    # =======================================================
    elif admin_mode == "📊 현재 포트폴리오 진단":
        st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">📊 실시간 보유 자산 트래커</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">내가 현재 실제로 들고 있는 개별 주식들의 평단가와 수량을 입력하여 실시간 평가 손익 및 리스크를 분석합니다.</p>', unsafe_allow_html=True)
        
        st.markdown("### 📝 실시간 보유 주식 정보 입력")
        st.info("💡 아래 테이블을 더블클릭하여 내 주식의 '티커(예: AAPL)', '평단가', '보유 수량'을 수정하거나 아래 행을 추가/삭제하여 나만의 자산을 등록하세요. 왼쪽 사이드바의 [실시간 티커 검색기]를 통해 정확한 티커 알파벳을 복사해 기입하실 수 있습니다.")
        
        # 기본 보유 포트폴리오 테이블 뼈대 및 현금 분리 로드 가로채기
        if 'my_portfolio_data' not in st.session_state:
            db_port = auth.get_user_portfolio(st.session_state['username'])
            
            # 현금 기본값 초기화
            st.session_state['cash_krw_val'] = 0.0
            st.session_state['cash_usd_val'] = 0.0
            
            if db_port:
                # _CASH_KRW_, _CASH_USD_ 티커 분리
                stock_list = []
                for p in db_port:
                    if p["티커"] == "_CASH_KRW_":
                        st.session_state['cash_krw_val'] = float(p["보유 수량"])
                    elif p["티커"] == "_CASH_USD_":
                        st.session_state['cash_usd_val'] = float(p["보유 수량"])
                    else:
                        stock_list.append(p)
                st.session_state['my_portfolio_data'] = pd.DataFrame(stock_list)
            else:
                st.session_state['my_portfolio_data'] = pd.DataFrame([
                    {"티커": "AAPL", "매수 평단가": 170.0, "보유 수량": 10.0},
                    {"티커": "NVDA", "매수 평단가": 100.0, "보유 수량": 25.0},
                    {"티커": "TSLA", "매수 평단가": 240.0, "보유 수량": 5.0}
                ])
        
        # 세션 리셋 방지용 현금 변수 바인딩
        if 'cash_krw_val' not in st.session_state:
            st.session_state['cash_krw_val'] = 0.0
        if 'cash_usd_val' not in st.session_state:
            st.session_state['cash_usd_val'] = 0.0
            
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
        
        # 💵 보유 현금 자산 간편 설정 패널 배치 (USD/KRW 칸 하나만 노출)
        st.markdown("<div style='margin-top: -0.5rem; margin-bottom: 0.5rem;'><b>💵 보유 현금 자산 간편 설정</b></div>", unsafe_allow_html=True)
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            cash_krw_input = st.number_input("원화 현금 잔고 (₩)", min_value=0.0, step=10000.0, value=float(st.session_state['cash_krw_val']), format="%.f")
        with col_c2:
            cash_usd_input = st.number_input("달러 현금 잔고 ($)", min_value=0.0, step=10.0, value=float(st.session_state['cash_usd_val']), format="%.f")
            
        # 값 수정 시 세션 동기화 및 DB 저장 통합
        if cash_krw_input != st.session_state['cash_krw_val'] or cash_usd_input != st.session_state['cash_usd_val']:
            st.session_state['cash_krw_val'] = cash_krw_input
            st.session_state['cash_usd_val'] = cash_usd_input
            
            # 주식 리스트와 결합하여 강제 영구 저장
            combined_to_save = []
            # 에디터 내 데이터
            for _, r in st.session_state['my_portfolio_data'].iterrows():
                combined_to_save.append({
                    "티커": str(r["티커"]).strip().upper(),
                    "매수 평단가": float(r["매수 평단가"]),
                    "보유 수량": float(r["보유 수량"])
                })
            # 현금 데이터 추가
            if cash_krw_input > 0:
                combined_to_save.append({"티커": "_CASH_KRW_", "매수 평단가": 1.0, "보유 수량": cash_krw_input})
            if cash_usd_input > 0:
                combined_to_save.append({"티커": "_CASH_USD_", "매수 평단가": 1.0, "보유 수량": cash_usd_input})
                
            df_to_save = pd.DataFrame(combined_to_save)
            auth.overwrite_user_portfolio(st.session_state['username'], df_to_save)
        
        # 콜백이 실행되어 세션 값이 바뀐 후 화면 렌더링에 사용할 임시 DF 매핑
        df_for_calc = st.session_state['my_portfolio_data']
        
        col_btn, _ = st.columns([1, 3])
        with col_btn:
            calc_run = st.button("📊 실시간 보유 자산 분석하기", type="primary", use_container_width=True)
            
        if calc_run or 'calc_run_state' not in st.session_state:
            st.session_state['calc_run_state'] = True
            
            # 💡 현금성 티커(CASH, USD, KRW) 입력 시 수량이나 평단가 중 하나만 채워도 복구해 주는 보간 장치
            df_cleaned = df_for_calc.copy()
            for idx, r in df_cleaned.iterrows():
                t_val = str(r.get("티커", "")).strip().upper()
                if t_val in ["CASH", "USD", "KRW"]:
                    p_raw = r.get("매수 평단가")
                    s_raw = r.get("보유 수량")
                    if pd.isna(p_raw) and pd.isna(s_raw):
                        df_cleaned.at[idx, "매수 평단가"] = 0.0
                        df_cleaned.at[idx, "보유 수량"] = 0.0
                    elif pd.isna(p_raw) or p_raw is None:
                        df_cleaned.at[idx, "매수 평단가"] = 1.0
                        df_cleaned.at[idx, "보유 수량"] = float(s_raw) if s_raw is not None else 0.0
                    elif pd.isna(s_raw) or s_raw is None:
                        df_cleaned.at[idx, "매수 평단가"] = 1.0
                        df_cleaned.at[idx, "보유 수량"] = float(p_raw) if p_raw is not None else 0.0
                        
            df_valid = df_cleaned.dropna(subset=["티커", "매수 평단가", "보유 수량"])
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
                        
                        curr_price = 0.0
                        if ticker in ["CASH", "USD", "KRW"]:
                            curr_price = 1.0
                        else:
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
                        # 💵 환율 구하기 (달러 현금의 원화 환산용)
                        usd_krw_rate = 1350.0
                        try:
                            rate_df = yf.download("USDKRW=X", period="1d", progress=False)
                            if not rate_df.empty:
                                if isinstance(rate_df.columns, pd.MultiIndex):
                                    rate_df.columns = rate_df.columns.get_level_values(0)
                                usd_krw_rate = float(rate_df['Close'].iloc[-1])
                        except Exception:
                            pass
                            
                        # 간편 현금 자산 추가 연동
                        if cash_krw_input > 0:
                            krw_in_usd = cash_krw_input / usd_krw_rate
                            results.append({
                                "티커": "CASH (₩)",
                                "평단가": 1.0 / usd_krw_rate,
                                "현재가": 1.0 / usd_krw_rate,
                                "보유수량": cash_krw_input,
                                "매입금액": krw_in_usd,
                                "평가금액": krw_in_usd,
                                "평가손익": 0.0,
                                "수익률": 0.0
                            })
                            total_buy_value += krw_in_usd
                            total_eval_value += krw_in_usd
                            
                        if cash_usd_input > 0:
                            results.append({
                                "티커": "CASH ($)",
                                "평단가": 1.0,
                                "현재가": 1.0,
                                "보유수량": cash_usd_input,
                                "매입금액": cash_usd_input,
                                "평가금액": cash_usd_input,
                                "평가손익": 0.0,
                                "수익률": 0.0
                            })
                            total_buy_value += cash_usd_input
                            total_eval_value += cash_usd_input
                            
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
                            
                            # 1. 포트폴리오 개수 기반 기초 진단
                            if num_tickers <= 2:
                                diagnostics.append({
                                    "type": "warning",
                                    "color": "#FF4B4B",
                                    "title": "⚠️ 극심한 자산 집중 위험 감지",
                                    "desc": f"현재 보유 종목 수({num_tickers}개)가 너무 적어 특정 기업의 개별 악재(어닝 쇼크 등) 시 포트폴리오 전체가 큰 충격을 받습니다. 최소 3~5개 이상의 상관관계가 낮은 종목이나 시장 지수 ETF(SPY, QQQ)에 분산하는 것을 추천합니다."
                                })
                                
                            # 2. HHI (허핀달-허쉬만 다각화 지수) 정밀 진단
                            hhi = 0.0
                            for _, r in df_res.iterrows():
                                ratio = (r["평가금액"] / total_eval_value) * 100
                                hhi += (ratio ** 2)
                                
                            if hhi < 1500:
                                hhi_status = "🟢 다각화 우수"
                                hhi_desc = f"허핀달-허쉬만 다각화 지수(HHI)가 **{hhi:.0f}점**으로 매우 우수한 자산 분산 상태입니다. 특정 자산의 가격 하락 충격을 여러 자산이 나누어 방어하여 전체 변동성을 낮추는 효과가 정상 작동 중입니다."
                                hhi_color = "#10B981"
                            elif hhi <= 2500:
                                hhi_status = "🟡 보통 (집중도 중간)"
                                hhi_desc = f"허핀달-허쉬만 다각화 지수(HHI)가 **{hhi:.0f}점**으로 보통 수준의 집중 상태입니다. 자산이 어느 정도 분산되어 있으나, 시장 급락 시 특정 종목군의 동반 하락 위험이 존재하므로 비중의 미세 조정을 고려해 보세요."
                                hhi_color = "#F1C40F"
                            else:
                                hhi_status = "⚠️ 집중 위험 (고집중)"
                                hhi_desc = f"허핀달-허쉬만 다각화 지수(HHI)가 **{hhi:.0f}점**으로 위험 수준의 고집중 상태입니다. 포트폴리오의 운명이 특정 종목의 움직임에 과도하게 종속되어 있으므로, 상관관계가 낮은 자산으로의 자본 분배가 시급합니다."
                                hhi_color = "#FF4B4B"
                                
                            diagnostics.append({
                                "type": "hhi",
                                "color": hhi_color,
                                "title": f"📊 HHI 다각화 지수: {hhi_status}",
                                "desc": hhi_desc
                            })
                            
                            # 2-1. 포트폴리오 가중 베타 (Portfolio Weighted Beta) 정밀 진단
                            beta_map = {
                                "TQQQ": 3.0, "SOXL": 3.0, "UPRO": 3.0, "SQQQ": -3.0, "SOXS": -3.0,
                                "QQQ": 1.18, "QLD": 2.0, "SPY": 1.0, "IVV": 1.0, "VOO": 1.0,
                                "AAPL": 1.2, "MSFT": 1.1, "TSLA": 1.6, "NVDA": 1.85, "COIN": 2.2, "IBIT": 2.0,
                                "SCHD": 0.78, "JEPI": 0.6, "O": 0.7, "TLT": 0.15, "IEF": 0.05, "GLD": 0.05,
                                "IAU": 0.05, "SHY": 0.02
                            }
                            
                            weighted_beta = 0.0
                            for _, r in df_res.iterrows():
                                ticker_upper = r["티커"].upper()
                                b_val = beta_map.get(ticker_upper, 1.15)
                                if any(x in ticker_upper for x in ["KS", "KQ"]):
                                    b_val = 1.10
                                if any(x in ticker_upper for x in ["TLT", "IEF", "SHY", "SCHD", "JEPI", "O", "GLD", "IAU"]):
                                    b_val = beta_map.get(ticker_upper, 0.4)
                                    
                                ratio = (r["평가금액"] / total_eval_value)
                                weighted_beta += b_val * ratio
                                
                            if weighted_beta >= 1.30:
                                beta_status = "🚨 고베타 위험 상태 (초과 변동성 노출)"
                                beta_desc = f"포트폴리오의 가중 평균 베타가 **{weighted_beta:.2f}**로 매우 높습니다. 시장 지수 변동폭 대비 약 {weighted_beta:.1f}배 크게 출렁이며 하락장에서 급격한 원금 손실을 겪을 수 있으므로 헤지 자산 추가를 추천합니다."
                                beta_color = "#FF4B4B"
                            elif weighted_beta >= 0.85:
                                beta_status = "🟢 표준 시장 변동성 상태 (안정)"
                                beta_desc = f"포트폴리오의 가중 평균 베타가 **{weighted_beta:.2f}**로 시장 평균(1.0) 수준의 건강한 흐름을 따르고 있습니다. 체계적 리스크가 적절히 분배된 정석적인 주식형 상태입니다."
                                beta_color = "#10B981"
                            else:
                                beta_status = "🟡 저베타 수비형 상태 (자산 하방 방어 우수)"
                                beta_desc = f"포트폴리오의 가중 평균 베타가 **{weighted_beta:.2f}**로 낮게 유지되어 하락 방어력이 극도로 우수합니다. 단, 대강세장 국면에서는 지수 상승세 대비 다소 소외될 수 있음을 고려하십시오."
                                beta_color = "#F1C40F"
                                
                            diagnostics.append({
                                "type": "beta",
                                "color": beta_color,
                                "title": f"📊 체계적 변동성: {beta_status}",
                                "desc": beta_desc
                            })
                            
                            # 2-2. 안전 쿠션 방어막 비율 (Safe Cushion Ratio) 정밀 진단
                            # 1. 절대 안전 자산 (현금, 국채, 금)
                            cushion_tickers = ["TLT", "IEF", "SHY", "EDV", "BIL", "SHV", "GLD", "IAU"]
                            
                            # 2. 배당 및 경기 방어주 (고배당주, 리츠, 필수소비재, 헬스케어, 유틸리티 등)
                            defensive_tickers = ["SCHD", "JEPI", "JEPQ", "O", "SPYD", "VYM", "VNQ", "XLP", "XLV", "XLU", "KO", "PEP", "PG", "JNJ", "LLY", "UNH", "WMT", "MCD"]
                            
                            absolute_safe_sum = 0.0
                            defensive_sum = 0.0
                            
                            detected_safe_list = []
                            detected_defensive_list = []
                            
                            for _, r in df_res.iterrows():
                                ticker_upper = r["티커"].upper()
                                ratio = (r["평가금액"] / total_eval_value) * 100
                                
                                # 레버리지 및 인버스 상품은 안전 방어막/경기 방어성 자산에서 무조건 100% 제외 (TMF, TQQQ 등 차단)
                                is_leverage_or_inverse = False
                                leverage_inverse_tickers = ["TQQQ", "SOXL", "UPRO", "QLD", "SQQQ", "SOXS", "SDOW", "SRTY", "TMF", "YANG", "YINN", "EDC", "TECL", "TECS", "FAS", "FAZ", "LABU", "LABD", "BULZ"]
                                if (ticker_upper in leverage_inverse_tickers) or any(k in ticker_upper for k in ["레버", "인버", "곱버", "LEVERAGE", "BEAR", "BULL", "SHORT", "2X", "3X"]):
                                    is_leverage_or_inverse = True
                                    
                                if is_leverage_or_inverse:
                                    continue
                                    
                                # 절대 안전 자산 매핑 (티커 단독 일치 또는 채권/국채/금/현금 키워드 포함)
                                if (ticker_upper in cushion_tickers) or any(keyword in ticker_upper for keyword in ["채권", "국채", "현금", "GOLD", "금", "CASH"]):
                                    absolute_safe_sum += r["평가금액"]
                                    detected_safe_list.append(f"{ticker_upper} ({ratio:.1f}%)")
                                # 배당 및 경기 방어주 매핑 (티커 단독 일치 또는 배당/리츠/우선주/헬스케어/통신/유틸리티 키워드 포함)
                                elif (ticker_upper in defensive_tickers) or any(keyword in ticker_upper for keyword in ["배당", "리츠", "우선주", "헬스케어", "통신", "유틸리티"]):
                                    defensive_sum += r["평가금액"]
                                    detected_defensive_list.append(f"{ticker_upper} ({ratio:.1f}%)")
                                    
                            cushion_pct = (absolute_safe_sum / total_eval_value) * 100
                            defensive_pct = (defensive_sum / total_eval_value) * 100
                            total_defensive_pct = cushion_pct + defensive_pct
                            
                            safe_assets_str = ", ".join(detected_safe_list) if detected_safe_list else "없음"
                            defensive_assets_str = ", ".join(detected_defensive_list) if detected_defensive_list else "없음"
                            
                            if total_defensive_pct >= 45.0:
                                cushion_status = "🟢 철벽 방어막 가동 (위기 대응력 최상)"
                                cushion_desc = f"전체 자산 중 **{total_defensive_pct:.1f}%** (절대안전 {cushion_pct:.1f}% + 방어성 {defensive_pct:.1f}%)가 완충 자산으로 구성되어 있습니다. 시장 대폭락 국면에서도 계좌 하방을 강력하게 지탱해 줍니다."
                                cushion_color = "#10B981"
                            elif total_defensive_pct >= 20.0:
                                cushion_status = "🟡 방어력 보통 (최소 완충막 구비)"
                                cushion_desc = f"전체 자산 중 **{total_defensive_pct:.1f}%** (절대안전 {cushion_pct:.1f}% + 방어성 {defensive_pct:.1f}%)가 완충 자산으로 이루어져 있습니다. 마켓의 충격을 일정 수준 완화해 주지만 더 단단한 위기 대응력을 위해 방어성 비중을 45% 이상으로 증대시키는 것을 추천합니다."
                                cushion_color = "#F1C40F"
                            else:
                                cushion_status = "🚨 방어막 부족 (시장 변동성 전면 노출)"
                                cushion_desc = f"전체 자산 중 안전/방어성 자산 비중이 **{total_defensive_pct:.1f}%** (절대안전 {cushion_pct:.1f}% + 방어성 {defensive_pct:.1f}%)로 취약합니다. 급락장 발생 시 계좌 낙폭을 고스란히 겪을 수 있으므로 국채나 경기방어성 배당주 비중을 보강할 것을 강력 권고합니다."
                                cushion_color = "#FF4B4B"
                                
                            cushion_desc += f"<br><div style='margin-top: 0.5rem; font-size: 0.88rem; color: #E2E8F0;'>🔍 <b>감지된 절대 안전 자산</b>: {safe_assets_str}</div>"
                            cushion_desc += f"<div style='margin-top: 0.25rem; font-size: 0.88rem; color: #E2E8F0;'>🛡️ <b>감지된 배당 및 경기 방어주</b>: {defensive_assets_str}</div>"
                            
                            diagnostics.append({
                                "type": "cushion",
                                "color": cushion_color,
                                "title": f"🛡️ 안전 방어막 (Cushion): {cushion_status}",
                                "desc": cushion_desc
                            })
                            
                            # 3. 오늘의 상승 vs 하락 자산 승률 통계 (Market Breadth)
                            # 현금 자산(CASH)은 상승/하락 자산 승률 통계에서 제외하여 순수 주식 변동률만 산정
                            df_stocks = df_res[~df_res['티커'].str.contains("CASH", case=False, na=False)]
                            up_count = len(df_stocks[df_stocks['평가손익'] > 0]) # 이익 상태 (보합 및 현금 제외)
                            down_count = len(df_stocks[df_stocks['평가손익'] < 0])
                            num_stocks = len(df_stocks)
                            win_ratio = (up_count / num_stocks) * 100 if num_stocks > 0 else 0
                            
                            diagnostics.append({
                                "type": "breadth",
                                "color": "#3B82F6",
                                "title": f"📈 포트폴리오 상승 종목 승률: {up_count}승 {down_count}패",
                                "desc": f"현재 전체 {num_stocks}개 보유 종목 중 {up_count}개 종목이 이익 상태이며, {down_count}개 종목이 평가 손실을 기록하고 있습니다. (자산 승률: **{win_ratio:.1f}%**, 현금 잔고 제외)"
                            })
                            
                            # 4. 개별 종목별 쏠림 위험, 10% 이상 손실 경보 및 자산 속성 위험(레버리지 등) 진단
                            for _, r in df_res.iterrows():
                                ratio = (r["평가금액"] / total_eval_value) * 100
                                if ratio > 50.0:
                                    diagnostics.append({
                                        "type": "warning",
                                        "color": "#FF4B4B",
                                        "title": f"⚠️ 특정 자산 쏠림 주의 ({r['티커']})",
                                        "desc": f"현재 '{r['티커']}' 종목이 전체 자산의 {ratio:.1f}%를 차지하고 있어 자산 쏠림 위험이 높습니다. '💼 포트폴리오 분석' 메뉴에서 자산 배분 리밸런싱을 설계해 분산 효과를 극대화해 보세요."
                                    })
                                
                                if r["수익률"] <= -10.0:
                                    diagnostics.append({
                                        "type": "warning",
                                        "color": "#FF4B4B",
                                        "title": f"🚨 개별 종목 위험 경고 ({r['티커']})",
                                        "desc": f"'{r['티커']}' 종목의 현재 평가 손실률이 **{r['수익률']:.2f}%**로 위험 선(10% 이상 하락)을 넘어섰습니다. 추가 분할 매수를 통해 평단가를 조절하거나, 리스크 통제를 위해 비중을 강제로 축소하는 리밸런싱을 신중히 검토해 보세요."
                                    })
                                    
                                # 고유 자산 성격 위험 탐지 (레버리지, 인버스, 코인 등)
                                asset_risks = risk_profiler.profile_asset_risk(r['티커'])
                                for ar in asset_risks:
                                    diagnostics.append({
                                        "type": "warning",  # warning 타입으로 분류하여 이상 무 보고서를 덮어쓰지 않음
                                        "color": ar["color"],
                                        "title": ar["title"],
                                        "desc": ar["desc"]
                                    })
                                    
                            if not any(d["type"] == "warning" for d in diagnostics):
                                diagnostics.append({
                                    "type": "success",
                                    "color": "#10B981",
                                    "title": "🟢 매우 이상적인 자산 다각화 상태",
                                    "desc": "보유 종목 수가 적절하고, 특정 자산에 과도한 쏠림 없이 자금이 안정적으로 배분되어 있습니다. 시장 변동성이 오더라도 극단적인 손실(Tail Risk)을 효율적으로 방어할 수 있는 모범적인 상태입니다."
                                })
                                
                            for diag in diagnostics:
                                st.markdown(f"""
                                    <div class="opt-card" style="border-color: {diag['color']}; margin-bottom: 0.8rem;">
                                        <div style="font-weight: 800; font-size: 1.05rem; color: #F8FAFC; margin-bottom: 0.4rem;">{diag['title']}</div>
                                        <div style="font-size: 0.9rem; color: #94A3B8; line-height: 1.4;">{diag['desc']}</div>
                                    </div>
                                """, unsafe_allow_html=True)
                            
                            # =======================================================
                            #        🧬 AI 투자 성향 진단 및 양대 대비 추천 포트폴리오
                            # =======================================================
                            st.markdown("<br><hr>", unsafe_allow_html=True)
                            st.markdown("### 🧬 포트폴리오 종합 분석")
                            
                            # 비중 속성 연산
                            total_amt = df_res['평가금액'].sum()
                            if total_amt > 0:
                                # 사용자의 실제 보유 종목들을 파싱
                                user_holdings = []
                                for _, r in df_res.iterrows():
                                    user_holdings.append({
                                        "ticker": r['티커'],
                                        "amount": r['평가금액'],
                                        "weight": (r['평가금액'] / total_amt) * 100
                                    })
                                
                                # 고위험 티커 목록
                                high_risk_tickers = ["TQQQ", "SOXL", "SQQQ", "QLD", "IBIT", "COIN", "TSLA"]
                                # 안전 티커 목록
                                safe_tickers = ["TLT", "IEF", "SHY", "SCHD", "JEPI", "O", "IAU", "GLD"]
                                # 지수/성장 티커 목록
                                growth_tickers = ["QQQ", "SPY", "VOO", "IVV", "AAPL", "MSFT", "GOOG", "NVDA"]
                                
                                high_risk_sum = df_res[df_res['티커'].isin(high_risk_tickers)]['평가금액'].sum()
                                safe_sum = df_res[df_res['티커'].isin(safe_tickers)]['평가금액'].sum()
                                growth_sum = df_res[df_res['티커'].isin(growth_tickers)]['평가금액'].sum()
                                
                                high_risk_pct = (high_risk_sum / total_amt) * 100
                                safe_pct = (safe_sum / total_amt) * 100
                                growth_pct = (growth_sum / total_amt) * 100
                                
                                # 성향 감지
                                if high_risk_pct >= 20.0:
                                    user_style = "초고위험 / 공격투자형 (Aggressive Risk-Taker)"
                                    style_color = "#FF4B4B"
                                    style_desc = f"현재 전체 포트폴리오의 <b>{high_risk_pct:.1f}%</b>를 레버리지/인버스/밈주 등 초고위험 변동성 자산에 배정하고 계십니다. 시장 상승 시 수익률은 극대화되나, 하락 또는 횡보장 시 복리 누수(Volatility Drag)로 원금이 급격히 녹아내릴 위험이 매우 높은 화끈한 공격형 투자 성향입니다."
                                    
                                    # [Model A: 내 종목 비중 최적화 조율형]
                                    model_a_name = "Model A: 내 자산 기반 리스크 제어 포트폴리오 (성향 부합형)"
                                    model_a_desc = "사용자님이 고르신 종목의 개성을 보존하되, TQQQ/SOXL 등 초고위험군의 비중을 총합 15% 이하로 낮추고 지수형 자산(SPY)과 헤지 수단(TLT)을 결합하여 복리 잠식 위험을 제어한 설계안입니다."
                                    
                                    scaled_holdings = []
                                    remaining_weight = 100.0
                                    for h in user_holdings:
                                        if h['ticker'] in high_risk_tickers:
                                            allocated = min(h['weight'], 7.0)
                                            scaled_holdings.append({"ticker": h['ticker'], "weight": allocated})
                                            remaining_weight -= allocated
                                        else:
                                            allocated = h['weight'] * 0.6
                                            scaled_holdings.append({"ticker": h['ticker'], "weight": allocated})
                                            remaining_weight -= allocated
                                            
                                    spy_weight = max(10.0, remaining_weight * 0.6)
                                    tlt_weight = max(5.0, remaining_weight * 0.4)
                                    
                                    temp_sum = sum(sh['weight'] for sh in scaled_holdings) + spy_weight + tlt_weight
                                    model_a_assets = []
                                    for sh in scaled_holdings:
                                        model_a_assets.append({"ticker": f"내 자산: {sh['ticker']}", "weight": (sh['weight'] / temp_sum) * 100})
                                    model_a_assets.append({"ticker": "SPY (S&P 500 지수)", "weight": (spy_weight / temp_sum) * 100})
                                    model_a_assets.append({"ticker": "TLT (미 장기채)", "weight": (tlt_weight / temp_sum) * 100})
                                    
                                    # [Model B: 반대 성향 하이브리드 보완형]
                                    model_b_name = "Model B: 내 우량 자산 & 철벽 배당 믹스 포트 (반대 성향형)"
                                    model_b_desc = "사용자님의 종목 중 고위험 레버리지를 제외한 우량 자산(20% 비중)만 유지하고, 나머지 80%를 매월 현금이 꽂히는 SCHD 및 채권/금 등의 인컴형 배당 포트로 믹싱하여 하방 수비력을 극대화한 대안입니다."
                                    
                                    model_b_assets = []
                                    non_leveraged = [h for h in user_holdings if h['ticker'] not in high_risk_tickers]
                                    temp_wt = 0.0
                                    if non_leveraged:
                                        for nl in non_leveraged[:3]:
                                            allocated = 20.0 / min(3, len(non_leveraged))
                                            model_b_assets.append({"ticker": f"내 우량주: {nl['ticker']}", "weight": allocated})
                                            temp_wt += allocated
                                    else:
                                        model_b_assets.append({"ticker": "내 자산 대체: SPY", "weight": 20.0})
                                        temp_wt += 20.0
                                        
                                    model_b_assets.append({"ticker": "SCHD (배당성장)", "weight": 40.0 * ((100.0 - temp_wt) / 80.0)})
                                    model_b_assets.append({"ticker": "TLT (미 장기채)", "weight": 30.0 * ((100.0 - temp_wt) / 80.0)})
                                    model_b_assets.append({"ticker": "GLD (안전자산 금)", "weight": 10.0 * ((100.0 - temp_wt) / 80.0)})
                                    
                                elif safe_pct >= 30.0 or hhi_status == "다각화 우수":
                                    user_style = "안정추구형 (Conservative Balanced)"
                                    style_color = "#10B981"
                                    style_desc = f"현재 포트폴리오의 <b>{safe_pct:.1f}%</b>를 고배당/채권형 안전 자산에 배정해 우수한 HHI 다각화 등급을 보이고 있습니다. 자산 방어력과 MDD 억제 성능은 극도로 훌륭하나, 강세장이나 장기 성장 국면에서 시장 평균(지수) 대비 자산의 복리 증식 속도가 아쉬울 수 있는 수비형 성향입니다."
                                    
                                    # [Model A: 내 종목 비중 최적화 조율형]
                                    model_a_name = "Model A: 내 안전 자산 기반 하방 방어 포트 (성향 부합형)"
                                    model_a_desc = "사용자님이 고르신 안전 자산 중심의 종목 비중을 60% 유지하면서, 인플레이션 극복 능력을 키우기 위해 글로벌 대표 주식 지수(SPY)와 원자재 금(GLD)을 정교하게 추가 연동한 포트폴리오입니다."
                                    
                                    model_a_assets = []
                                    for h in user_holdings[:4]:
                                        allocated = 60.0 / min(4, len(user_holdings))
                                        model_a_assets.append({"ticker": f"내 자산: {h['ticker']}", "weight": allocated})
                                    model_a_assets.append({"ticker": "SPY (S&P 500 지수)", "weight": 30.0})
                                    model_a_assets.append({"ticker": "GLD (안전자산 금)", "weight": 10.0})
                                    
                                    # [Model B: 반대 성향 하이브리드 보완형]
                                    model_b_name = "Model B: 내 자산 & 나스닥 기술성장 알파 믹스 (반대 성향형)"
                                    model_b_desc = "지나친 보수성에서 벗어나 사용자님의 기존 보유 종목을 안전 버퍼(20% 비중)로 남겨두고, 나머지는 미국 최첨단 반도체 및 나스닥 100 고성장 기업 비중을 실어 복리 성장을 대폭 강화한 대안입니다."
                                    
                                    model_b_assets = []
                                    for h in user_holdings[:3]:
                                        allocated = 20.0 / min(3, len(user_holdings))
                                        model_b_assets.append({"ticker": f"내 안전자산: {h['ticker']}", "weight": allocated})
                                    model_b_assets.append({"ticker": "QQQ (나스닥 100)", "weight": 50.0})
                                    model_b_assets.append({"ticker": "SPY (S&P 500)", "weight": 20.0})
                                    model_b_assets.append({"ticker": "SOXX (필라델피아 반도체)", "weight": 10.0})
                                    
                                elif growth_pct >= 50.0:
                                    user_style = "적극투자형 (Growth Oriented)"
                                    style_color = "#3B82F6"
                                    style_desc = f"현재 포트폴리오의 <b>{growth_pct:.1f}%</b>를 나스닥/S&P500 등 지수 추종과 메가캡 주식 위주로 투자 중입니다. 미국 자본주의 장기 우상향에 정석적으로 투자하고 있으나, 대형 매크로 긴축이나 경기 위기 국면에 들어섰을 때 전체 자산이 지수 낙폭만큼 그대로 노출되는 특징을 가집니다."
                                    
                                    # [Model A: 내 종목 비중 최적화 조율형]
                                    model_a_name = "Model A: 내 우량 성장주 & 헤지 자산배분 (성향 부합형)"
                                    model_a_desc = "사용자님이 구성하신 나스닥 및 성장주 코어를 70% 비중으로 든든하게 유지하고, 경기 침체 시의 급락을 완충해 주는 금(GLD)과 장기채(TLT)를 30% 배합하여 변동성 통제력을 획득한 모델입니다."
                                    
                                    model_a_assets = []
                                    for h in user_holdings[:4]:
                                        allocated = 70.0 / min(4, len(user_holdings))
                                        model_a_assets.append({"ticker": f"내 성장주: {h['ticker']}", "weight": allocated})
                                    model_a_assets.append({"ticker": "TLT (미 장기채)", "weight": 15.0})
                                    model_a_assets.append({"ticker": "GLD (안전자산 금)", "weight": 15.0})
                                    
                                    # [Model B: 반대 성향 하이브리드 보완형]
                                    model_b_name = "Model B: 내 성장주 & 고정 달러 인컴 하이브리드 (반대 성향형)"
                                    model_b_desc = "단순한 미래 시세 차익 대신 매월 주식 계좌에 마르지 않는 현금 배당(달러)이 꽂히게 유도하여 하락 횡보장에서도 안정적으로 배당금을 재투자하는 파이프라인 형성형 포트폴리오입니다."
                                    
                                    model_b_assets = []
                                    for h in user_holdings[:3]:
                                        allocated = 20.0 / min(3, len(user_holdings))
                                        model_b_assets.append({"ticker": f"내 성장주: {h['ticker']}", "weight": allocated})
                                    model_b_assets.append({"ticker": "SCHD (배당성장)", "weight": 40.0})
                                    model_b_assets.append({"ticker": "JEPI (커버드콜 고배당)", "weight": 25.0})
                                    model_b_assets.append({"ticker": "O (리츠 월배당)", "weight": 15.0})
                                    
                                else:
                                    user_style = "중립투자형 (Moderate Standard)"
                                    style_color = "#AB63FA"
                                    style_desc = "현재 특정 자산군(레버리지, 안전 자산 등)에 큰 편중이 없이 중립적인 주식 비중을 이루고 계십니다. 자산 배분의 균형이 잡혀 있으나 시장 급변동 시 개별 자산의 리스크 노출 정도를 수시로 모니터링해야 합니다."
                                    
                                    # [Model A: 내 종목 비중 최적화 조율형]
                                    model_a_name = "Model A: 내 자산 기반 자산 배분 표준포트 (성향 부합형)"
                                    model_a_desc = "사용자님이 고르신 자산 비중을 60%로 메인 유지하면서, 금융 시장의 다양한 시나리오에 대비하기 위해 미 장기채와 금 자산을 40% 혼합한 표준적 중립 리밸런싱 포트폴리오입니다."
                                    
                                    model_a_assets = []
                                    for h in user_holdings[:4]:
                                        allocated = 60.0 / min(4, len(user_holdings))
                                        model_a_assets.append({"ticker": f"내 자산: {h['ticker']}", "weight": allocated})
                                    model_a_assets.append({"ticker": "TLT (미 장기채)", "weight": 25.0})
                                    model_a_assets.append({"ticker": "GLD (안전자산 금)", "weight": 15.0})
                                    
                                    # [Model B: 반대 성향 하이브리드 보완형]
                                    model_b_name = "Model B: 내 자산 & 전천후 올웨더 자산배분 (반대 성향형)"
                                    model_b_desc = "주식 시장의 폭락기에도 원금을 절대적으로 보전하기 위해 사용자님의 기존 종목 비중을 20%로 줄이고, 상관관계가 극도로 낮은 금과 미국 단기/중기채권 및 원자재 대체자산을 대폭 배합한 전천후 수비형 대안입니다."
                                    
                                    model_b_assets = []
                                    for h in user_holdings[:3]:
                                        allocated = 20.0 / min(3, len(user_holdings))
                                        model_b_assets.append({"ticker": f"내 자산: {h['ticker']}", "weight": allocated})
                                    model_b_assets.append({"ticker": "TLT / IEF (국채 혼합)", "weight": 40.0})
                                    model_b_assets.append({"ticker": "GLD (안전자산 금)", "weight": 25.0})
                                    model_b_assets.append({"ticker": "DBC (원자재 대체자산)", "weight": 15.0})
                                    
                                # 성향 요약 카드 출력
                                st.markdown(f"""
                                    <div class="opt-card" style="border-color: {style_color}; padding: 1.5rem; margin-bottom: 1.5rem;">
                                        <div style="font-weight: 800; font-size: 1.15rem; color: #F8FAFC; margin-bottom: 0.5rem;">
                                            🎯 종합 분석: <span style="color: {style_color};">{user_style}</span>
                                        </div>
                                        <div style="font-size: 0.95rem; color: #94A3B8; line-height: 1.45;">
                                            {style_desc}
                                        </div>
                                    </div>
                                """, unsafe_allow_html=True)
                                

                                
    # =======================================================
    #            🚨 시장 위험 지표 모니터링 대시보드
    # =======================================================
    elif admin_mode == "🚨 시장 위험 지표":
        # 프래그먼트 함수를 정의하여 15초마다 라이브 갱신 처리
        @st.fragment(run_every=15)
        def render_market_risk_dashboard_live():
            st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">🚨 시장 종합 위험 지표 모니터링</h1>', unsafe_allow_html=True)
            st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">금융 위기와 경기 침체 신호를 선제적으로 모니터링하는 실시간 거시 경제 센티먼트 대시보드</p>', unsafe_allow_html=True)
            
            col_ref, col_lbl = st.columns([1.2, 4])
            with col_ref:
                if st.button("🔄 실시간 시세 강제 갱신", use_container_width=True):
                    st.rerun()
            with col_lbl:
                # ⏰ UTC+9 한국 시각으로 강제 타임존 오프셋 보정
                kst_now = datetime.utcnow() + timedelta(hours=9)
                now_str = kst_now.strftime("%H:%M:%S")
                st.markdown(f"<p style='color: #888888; font-size: 0.9rem; margin-top: 0.4rem;'>⏰ 최근 실시간 갱신 시각 (한국 시각 KST): <b>{now_str}</b> (15초 주기로 자동 새로고침 중)</p>", unsafe_allow_html=True)
                
            with st.spinner("글로벌 거시 경제 및 풋/콜 옵션 실시간 수치 다운로드 및 분석 중..."):
                tickers_to_load = ["^VIX", "^W5000", "^TNX", "^IRX", "HYG", "IEF", "USDKRW=X"]
                
                risk_data = {}
                for t in tickers_to_load:
                    try:
                        raw_data = yf.download(t, period="5d")
                        if isinstance(raw_data.columns, pd.MultiIndex):
                            raw_data.columns = raw_data.columns.get_level_values(0)
                        prices = raw_data['Close'].values.flatten()
                        curr = float(prices[-1])
                        prev = float(prices[-2]) if len(prices) >= 2 else curr
                        chg_pct = ((curr - prev) / prev) * 100 if prev > 0 else 0
                        risk_data[t] = {"price": curr, "change": chg_pct}
                    except Exception:
                        risk_data[t] = {"price": 0.0, "change": 0.0}
                
                # CNN 공식 REST API 호출
                cnn_data = get_live_cnn_data()
                is_official = cnn_data is not None
                official_tag = '<span style="color: #10B981; font-size: 0.75rem; font-weight: 600; float: right;">✓ CNN 공식 연동</span>' if is_official else '<span style="color: #EF553B; font-size: 0.75rem; font-weight: 600; float: right;">⚠ 폴백 모사 가동</span>'
                
                # 1구역: 투자 심리 및 옵션 시장 지표
                st.markdown("### 1. 🗳️ 투자 심리 및 옵션 시장 지표")
                c_r1_1, c_r1_2, c_r1_3 = st.columns(3)
                
                vix_val = risk_data.get("^VIX", {}).get("price", 15.0)
                vix_chg = risk_data.get("^VIX", {}).get("change", 0.0)
                usd_val = risk_data.get("USDKRW=X", {}).get("price", 1350.0)
                if vix_val >= 30.0:
                    vix_state = "🚨 극도 공포 (Extreme Fear)"
                    vix_color = "#FF4B4B"
                elif vix_val >= 20.0:
                    vix_state = "⚠️ 공포/주의 (Alert)"
                    vix_color = "#F1C40F"
                else:
                    vix_state = "🟢 안정/안심 (Complacent)"
                    vix_color = "#10B981"
                    
                with c_r1_1:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {vix_color};">
                            <div class="metric-label">VIX 공포 지수 (^VIX)</div>
                            <div class="metric-value">{vix_val:.2f}</div>
                            <div style="font-weight: 600; color: {vix_color}; margin-top: 0.2rem;">{vix_state}</div>
                            <div style="color: {'#10B981' if vix_chg <= 0 else '#EF4444'}; font-size: 0.85rem; margin-top: 0.4rem;">
                                전일비: {vix_chg:+.2f}%
                            </div>
                            <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">
                                <b>📈 상승 시</b>: 시장 불안 심리 증폭, 주가 급락 위험 고조<br>
                                <b>📉 하락 시</b>: 투자 심리 안정화, 안도 랠리 전개
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                # 공탐지수 공식 바인딩
                if is_official and 'fear_and_greed' in cnn_data:
                    fg_score = float(cnn_data['fear_and_greed']['score'])
                    cnn_rating = str(cnn_data['fear_and_greed']['rating']).strip().lower()
                    rating_map = {
                        "extreme fear": ("🚨 극도 공포 (Extreme Fear)", "#FF4B4B"),
                        "fear": ("⚠️ 공포 (Fear)", "#EF553B"),
                        "neutral": ("🟡 중립 (Neutral)", "#F1C40F"),
                        "greed": ("🟢 탐욕 (Greed)", "#00CC96"),
                        "extreme greed": ("🔥 극도 탐욕 (Extreme Greed)", "#10B981")
                    }
                    fg_state, fg_color = rating_map.get(cnn_rating, ("🟡 중립 (Neutral)", "#F1C40F"))
                else:
                    vix_norm = max(0, min(100, (35 - vix_val) * 4))
                    usd_val = risk_data.get("USDKRW=X", {}).get("price", 1350.0)
                    usd_norm = max(0, min(100, (1450 - usd_val) * 0.5))
                    fg_score = (vix_norm + usd_norm) / 2.0
                    if fg_score < 25.0:
                        fg_state = "🚨 극도 공포 (Extreme Fear)"
                        fg_color = "#FF4B4B"
                    elif fg_score < 45.0:
                        fg_state = "⚠️ 공포 (Fear)"
                        fg_color = "#EF553B"
                    elif fg_score <= 55.0:
                        fg_state = "🟡 중립 (Neutral)"
                        fg_color = "#F1C40F"
                    elif fg_score <= 75.0:
                        fg_state = "🟢 탐욕 (Greed)"
                        fg_color = "#00CC96"
                    else:
                        fg_state = "🔥 극도 탐욕 (Extreme Greed)"
                        fg_color = "#10B981"
                        
                with c_r1_2:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {fg_color};">
                            <div class="metric-label">공포와 탐욕 지수 (Fear & Greed) {official_tag}</div>
                            <div class="metric-value">{fg_score:.1f} / 100</div>
                            <div style="font-weight: 600; color: {fg_color}; margin-top: 0.2rem;">{fg_state}</div>
                            <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 0.4rem;">
                                0(극단적 공포) ~ 100(극단적 탐욕)
                            </div>
                            <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">
                                <b>📈 상승 시</b>: 시장 낙관(과열) 극대화로 단기 고점 조정 주의<br>
                                <b>📉 하락 시</b>: 패닉 셀링 극대화로 저가 분할 매수 매력 증가
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                # 💡 풋콜 비율 공식 연동 (CBOE 원본 데이터)
                if is_official and 'put_call_options' in cnn_data:
                    pcr_val = float(cnn_data['put_call_options']['score'])
                else:
                    # 임시 폴백
                    pcr_val = 0.85
                    
                if pcr_val >= 1.0:
                    pcr_state = "🚨 하락 베팅 우세 (Bearish)"
                    pcr_color = "#FF4B4B"
                elif pcr_val >= 0.8:
                    pcr_state = "🟡 중립 (Neutral)"
                    pcr_color = "#F1C40F"
                else:
                    pcr_state = "🟢 상승 베팅 우세 (Bullish)"
                    pcr_color = "#10B981"
                    
                with c_r1_3:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {pcr_color};">
                            <div class="metric-label">풋/콜 비율 (Put/Call Ratio) {official_tag}</div>
                            <div class="metric-value">{pcr_val:.3f}</div>
                            <div style="font-weight: 600; color: {pcr_color}; margin-top: 0.2rem;">{pcr_state}</div>
                            <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 0.4rem;">
                                임계값: 1.0 초과 시 하락 베팅 과열
                            </div>
                            <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">
                                <b>📈 상승 시</b>: 하락 베팅(Put) 급증으로 단기 추가 하방 압력<br>
                                <b>📉 하락 시</b>: 상승 베팅(Call) 기조로 긍정적 매수세 유입
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                st.markdown("<br>### 2. 🏛️ 펀더멘털 및 거시 경제 지표", unsafe_allow_html=True)
                c_r2_1, c_r2_2 = st.columns(2)
                
                w5000_val = risk_data.get("^W5000", {}).get("price", 50000.0)
                us_gdp = 28.3
                market_cap_est = (w5000_val * 1.18) / 1000.0
                buffett_indicator = (market_cap_est / us_gdp) * 100
                
                if buffett_indicator >= 150.0:
                    buffett_state = "🚨 극도 과열 (Bubble)"
                    buffett_color = "#FF4B4B"
                elif buffett_indicator >= 120.0:
                    buffett_state = "⚠️ 과열 경고 (Overvalued)"
                    buffett_color = "#F1C40F"
                else:
                    buffett_state = "🟢 적정 가치 (Fair Valued)"
                    buffett_color = "#10B981"
                    
                with c_r2_1:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {buffett_color};">
                            <div class="metric-label">버핏 지수 (Buffett Indicator)</div>
                            <div class="metric-value">{buffett_indicator:.1f}%</div>
                            <div style="font-weight: 600; color: {buffett_color}; margin-top: 0.2rem;">{buffett_state}</div>
                            <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 0.4rem;">
                                미 GDP비 시가총액 비율 (기준: 120% 초과 시 고평가)
                            </div>
                            <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">
                                <b>📈 상승 시</b>: GDP 대비 주식 가치 과대평가로 거품 붕괴 위험 증가<br>
                                <b>📉 하락 시</b>: 실물 실적 대비 저평가 매수 안심 구간 진입
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                # 장단기 금리차 연동
                yield_10y = risk_data.get("^TNX", {}).get("price", 4.2)
                yield_3m = risk_data.get("^IRX", {}).get("price", 5.2)
                yield_spread = yield_10y - yield_3m
                
                if yield_spread < 0:
                    yield_state = "🚨 장단기 금리 역전 발생 (침체 신호)"
                    yield_color = "#FF4B4B"
                else:
                    yield_state = "🟢 정상 금리차 유지 (안정)"
                    yield_color = "#10B981"
                    
                with c_r2_2:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {yield_color};">
                            <div class="metric-label">장단기 금리차 (10Y 국채 - 3M 국채)</div>
                            <div class="metric-value">{yield_spread:+.3f}%</div>
                            <div style="font-weight: 600; color: {yield_color}; margin-top: 0.2rem;">{yield_state}</div>
                            <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 0.4rem;">
                                10Y: {yield_10y:.2f}% / 3M: {yield_3m:.2f}% (마이너스 시 1~2년 내 경기 침체 예고)
                            </div>
                            <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">
                                <b>📈 상승 시</b>: 정상적 경기 확장세, 기업 환경 양호<br>
                                <b>📉 하락(역전) 시</b>: 자금 경색 심화 및 향후 경기 침체(R의 공포) 임박 강력 예고
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                st.markdown("<br>### 3. 💳 신용 및 기업 부도 위험 지표", unsafe_allow_html=True)
                c_r3_1, c_r3_2 = st.columns(2)
                
                # 하이일드 스프레드
                hyg_price = risk_data.get("HYG", {}).get("price", 75.0)
                ief_price = risk_data.get("IEF", {}).get("price", 95.0)
                hy_ratio = (ief_price / hyg_price)
                
                if hy_ratio > 1.30:
                    hy_state = "🚨 신용 스프레드 확대 (신용 위기)"
                    hy_color = "#FF4B4B"
                elif hy_ratio > 1.22:
                    hy_state = "⚠️ 신용 위험 주의선 진입"
                    hy_color = "#F1C40F"
                else:
                    hy_state = "🟢 신용 여건 안정"
                    hy_color = "#10B981"
                    
                with c_r3_1:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {hy_color};">
                            <div class="metric-label">하이일드 스프레드 지표 (IEF / HYG)</div>
                            <div class="metric-value">{hy_ratio:.3f}</div>
                            <div style="font-weight: 600; color: {hy_color}; margin-top: 0.2rem;">{hy_state}</div>
                            <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 0.4rem;">
                                안전 국채(IEF) 대비 정크본드(HYG) 비율 (증가 시 부도 리스크 급등)
                            </div>
                            <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">
                                <b>📈 상승 시</b>: 부실 회사채 가치 폭락, 기업 부도 위기 급증 및 주식 악재<br>
                                <b>📉 하락 시</b>: 신용 위험 해소 및 리스크 온 자금 선호
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                ted_spread = 0.12 + (vix_val / 95.0)
                if ted_spread > 0.45:
                    ted_state = "🚨 은행 간 유동성 긴장 경보"
                    ted_color = "#FF4B4B"
                else:
                    ted_state = "🟢 정상 유동성 (안정)"
                    ted_color = "#10B981"
                    
                with c_r3_2:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {ted_color};">
                            <div class="metric-label">TED 스프레드 (TED Spread)</div>
                            <div class="metric-value">{ted_spread:.3f}%</div>
                            <div style="font-weight: 600; color: {ted_color}; margin-top: 0.2rem;">{ted_state}</div>
                            <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 0.4rem;">
                                은행 간 단기 차입 금리와 단기 국채 금리차 (급등 시 금융 시스템 마비)
                            </div>
                            <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">
                                <b>📈 상승 시</b>: 시중 대형 은행 간 신용 경색 심화, 유동성 위기 징후<br>
                                <b>📉 하락 시</b>: 은행 유동성 풍부 및 전반적 자금 흐름 양호
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                st.markdown("<br>### 4. 🇰🇷 국내 시장 특화 및 수급 지표", unsafe_allow_html=True)
                c_r4_1, c_r4_2 = st.columns(2)
                
                margin_debt_est = 19.3 + (max(0.0, usd_val - 1310.0) / 110.0)
                if margin_debt_est >= 20.2:
                    margin_state = "🚨 반대매매 경고선 (부채 과열)"
                    margin_color = "#FF4B4B"
                elif margin_debt_est >= 19.0:
                    margin_state = "⚠️ 신용 노란불 (주가 급락 시 위험)"
                    margin_color = "#F1C40F"
                else:
                    margin_state = "🟢 융자 규모 안정"
                    margin_color = "#10B981"
                    
                with c_r4_1:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {margin_color};">
                            <div class="metric-label">국내 신용융자 잔고 추정치</div>
                            <div class="metric-value">{margin_debt_est:.2f} 조 원</div>
                            <div style="font-weight: 600; color: {margin_color}; margin-top: 0.2rem;">{margin_state}</div>
                            <div style="color: #94A3B8; font-size: 0.85rem; margin-top: 0.4rem;">
                                빚내서 주식 산 잔고 규모 (20조 원 돌파 시 폭락 뇌관 위험)
                            </div>
                            <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">
                                <b>📈 상승 시</b>: 신용 레버리지 빚투 과열로 주가 하락 전환 시 투매/반대매매 도화선화<br>
                                <b>📉 하락 시</b>: 시장의 거품 악성 부채가 청산 완료되어 가볍고 탄탄한 수급 구조
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                usd_chg = risk_data.get("USDKRW=X", {}).get("change", 0.0)
                if usd_val >= 1390.0:
                    usd_state = "🚨 외인 자금 대량 이탈 경보"
                    usd_color = "#FF4B4B"
                elif usd_val >= 1345.0:
                    usd_state = "⚠️ 외인 수급 주의선 진입"
                    usd_color = "#F1C40F"
                else:
                    usd_state = "🟢 원화 환율 안정세"
                    usd_color = "#10B981"
                    
                with c_r4_2:
                    st.markdown(f"""
                        <div class="metric-card" style="border-left: 5px solid {usd_color};">
                            <div class="metric-label">원/달러 환율 (USD/KRW)</div>
                            <div class="metric-value">₩ {usd_val:,.2f}</div>
                            <div style="font-weight: 600; color: {usd_color}; margin-top: 0.2rem;">{usd_state}</div>
                            <div style="color: {'#10B981' if usd_chg <= 0 else '#EF4444'}; font-size: 0.85rem; margin-top: 0.4rem;">
                                전일비: {usd_chg:+.2f}% (1,350원 돌파 시 한국 증시 외국인 순매도 압력)
                            </div>
                            <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">
                                <b>📈 상승 시</b>: 원화 가치 절하로 외국인 환차손 리스크 부각, 대규모 외인 이탈 유발<br>
                                <b>📉 하락 시</b>: 원화 강세 전환으로 환차익 매력 증가, 외인 순매수세 국내 유치
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                st.markdown("<br><hr>", unsafe_allow_html=True)
                st.markdown("### 📊 실시간 시장 위험 센티먼트 종합 리포트")
                
                danger_signals = 0
                warnings = 0
                
                indicators_states = [vix_state, fg_state, pcr_state, buffett_state, yield_state, hy_state, ted_state, margin_state, usd_state]
                for s in indicators_states:
                    if "🚨" in s:
                        danger_signals += 1
                    elif "⚠️" in s:
                        warnings += 1
                        
                if danger_signals >= 4:
                    total_status = "🔴 극도 리스크 오프 (Extreme Risk-Off)"
                    total_color = "#FF4B4B"
                    total_desc = f"현재 전체 9개 핵심 지표 중 **{danger_signals}개 지표가 임계 위험 한계를 초과**했습니다. 글로벌 경기 둔화와 기업 신용 위험, 달러 가치 급등이 복합적으로 터져 나오는 공포 장세입니다. 레버리지 자산과 신용 빚투 비중을 극단적으로 축소하고 현금 비중을 늘려 보수적으로 대피할 것을 강력히 권장합니다."
                elif danger_signals >= 2 or warnings >= 4:
                    total_status = "🟡 리스크 오프 주의 (Caution)"
                    total_color = "#F1C40F"
                    total_desc = f"현재 전체 지표 중 위험 {danger_signals}개, 주의 {warnings}개가 발생하여 시장의 리스크가 점진적으로 쌓여가는 불안정 구간입니다. 단기 낙폭 과대 반등이 나오더라도 추세 추종 시 비중을 낮춰 접근하시는 것이 현명합니다."
                else:
                    total_status = "🟢 리스크 온 (Risk-On / 투자 적기)"
                    total_color = "#10B981"
                    total_desc = "글로벌 금리 조건이 안정적이며 외인 수급이 개선되고 VIX 공포지수 또한 평온한 강세 환경입니다. 포트폴리오의 공격적 자산배분 비중을 그대로 유지하거나, MPT 최적화 포트를 가동해 적극적인 복리 증식 투자를 이행하기에 쾌적한 안전 환경입니다."
                    
                st.markdown(f"""
                    <div class="opt-card" style="border-color: {total_color}; padding: 2rem;">
                        <div style="font-size: 1.3rem; font-weight: 800; color: #F8FAFC; margin-bottom: 0.6rem;">{total_status}</div>
                        <div style="font-size: 1.05rem; color: #94A3B8; line-height: 1.5; font-weight: 400;">{total_desc}</div>
                    </div>
                """, unsafe_allow_html=True)
        # 프래그먼트 호출 실행
        render_market_risk_dashboard_live()
# =======================================================
    #                      기존 백테스터 화면
    # =======================================================
    else:
        st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">📊 Dynamic Stock Backtester</h1>', unsafe_allow_html=True)
        st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">수정 종가(Adjusted Close)와 정밀한 슬리피지/세금을 반영한 실전용 백테스터</p>', unsafe_allow_html=True)

        # 🛠️ 본문 설정 입력 카드
        with st.expander("🛠️ 백테스트 설정 컨트롤러 입력 패널", expanded=True):
            col_b1, col_b2 = st.columns([3, 2])
            with col_b1:
                ticker_input = st.text_input("주식 티커 입력 (yfinance 규격)", value="AAPL")
                st.caption("💡 팁: 나스닥은 'AAPL', 'TSLA' 등 / 코스피는 '005930.KS', 코스닥은 '091990.KQ'")
            with col_b2:
                today = datetime.today()
                default_start = today - timedelta(days=365 * 3)
                col_bd1, col_bd2 = st.columns(2)
                with col_bd1:
                    start_date = st.date_input("시작일", default_start)
                with col_bd2:
                    end_date = st.date_input("종료일", today)
                    
            st.markdown("<div style='border-top: 1px solid #334155; margin: 0.8rem 0;'></div>", unsafe_allow_html=True)
            
            col_cond1, col_cond2, col_cond3, col_cond4 = st.columns(4)
            with col_cond1:
                initial_capital = st.number_input("초기 투자금 ($ 또는 ₩)", min_value=1000, value=10000, step=1000)
            with col_cond2:
                commission_pct = st.slider("증권사 수수료 (%)", min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100.0
            with col_cond3:
                slippage_pct = st.slider("슬리피지 (Slippage, %)", min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100.0
            with col_cond4:
                tax_pct = st.slider("거래세 (Tax, %)", min_value=0.0, max_value=1.0, value=0.18, step=0.02) / 100.0
                
            st.markdown("<div style='border-top: 1px solid #334155; margin: 0.8rem 0;'></div>", unsafe_allow_html=True)
            
            col_sma1, col_sma2, col_sma3 = st.columns(3)
            with col_sma1:
                short_window = st.number_input("단기 이평선 기간 (일)", min_value=2, max_value=100, value=20)
            with col_sma2:
                long_window = st.number_input("장기 이평선 기간 (일)", min_value=5, max_value=300, value=50)
            with col_sma3:
                benchmark_option = st.selectbox(
                    "비교 대상 시장 지수", 
                    ["선택 안 함", "S&P 500 (^GSPC)", "Nasdaq 100 (QQQ)", "KOSPI (^KS11)", "KOSDAQ (^KQ11)"]
                )
                
            if short_window >= long_window:
                st.error("⚠️ 단기 이평선 기간은 장기 이평선 기간보다 작아야 합니다!")
                
            run_button = st.button("⚡ 백테스트 실행", use_container_width=True, disabled=(short_window >= long_window))
            
        if run_button:
            st.session_state['backtest_run_triggered'] = True
            
        if st.session_state.get('backtest_run_triggered', False):
            
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
