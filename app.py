import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import auth  # 사용자 정의 인증 모듈 임포트

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

# 커스텀 CSS로 디자인 개선 (유려한 글꼴, 그라데이션 및 카드 스타일, 헤더 감추기)
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    /* 우측 상단 깃허브 버튼, 메뉴 버튼 및 하단 푸터 숨기기 */
    .stAppDeployButton, header, #MainMenu {
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
    
    /* 인증 폼 전용 커스텀 스타일 */
    .auth-container {
        background-color: #0F172A;
        border-radius: 16px;
        padding: 2.5rem;
        border: 1px solid #1E293B;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
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
        # yfinance MultiIndex 컬럼 수정 (단일 티커 조회 시 1차원 컬럼으로 변환)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception as e:
        st.error(f"데이터를 가져오는 중 오류가 발생했습니다: {e}")
        return None

# ----------------- 백테스트 엔진 -----------------
def run_backtest(df, short_window, long_window, initial_capital, commission_pct=0.001):
    data = df.copy()
    
    # 이동평균선 계산
    data['Short_SMA'] = data['Close'].rolling(window=short_window).mean()
    data['Long_SMA'] = data['Close'].rolling(window=long_window).mean()
    
    # 거래 시그널 생성 (1: 매수 신호구간, 0: 매도/현금화 신호구간)
    data['Signal'] = np.where(data['Short_SMA'] > data['Long_SMA'], 1, 0)
    
    # 포지션 (전일 시그널을 기준으로 오늘 매매가 실행됨)
    data['Position'] = data['Signal'].shift(1).fillna(0)
    
    # 포지션 변경 감지 (1: 매수 발생, -1: 매도 발생)
    data['Action'] = data['Position'].diff().fillna(0)
    
    # 일별 주가 변동률
    data['Daily_Return'] = data['Close'].pct_change().fillna(0)
    
    # 포트폴리오 가치 추적 배열
    portfolio_values = []
    cash = initial_capital
    shares = 0.0
    current_position = 0 # 0: 현금, 1: 주식
    
    prices = data['Close'].values
    positions = data['Position'].values
    actions = data['Action'].values
    
    for i in range(len(data)):
        current_price = prices[i]
        pos = positions[i]
        act = actions[i]
        
        # 매수 실행
        if act == 1 and cash > 0:
            buy_capital = cash * (1 - commission_pct)
            shares = buy_capital / current_price
            cash = 0.0
            current_position = 1
        
        # 매도 실행
        elif act == -1 and shares > 0:
            sell_value = shares * current_price
            cash = sell_value * (1 - commission_pct)
            shares = 0.0
            current_position = 0
            
        # 자산 가치 평가
        if current_position == 1:
            total_value = shares * current_price
        else:
            total_value = cash
            
        portfolio_values.append(total_value)
        
    data['Portfolio_Value'] = portfolio_values
    
    # 단순 Buy & Hold 수익률 및 자산 가치 계산
    data['Buy_Hold_CumReturn'] = (1 + data['Daily_Return']).cumprod()
    data['Buy_Hold_Value'] = initial_capital * data['Buy_Hold_CumReturn']
    
    return data

# ----------------- 성과 지표 계산 -----------------
def calculate_metrics(data, initial_capital):
    final_val = data['Portfolio_Value'].iloc[-1]
    bh_final_val = data['Buy_Hold_Value'].iloc[-1]
    
    # 누적 수익률
    total_return = (final_val - initial_capital) / initial_capital * 100
    bh_return = (bh_final_val - initial_capital) / initial_capital * 100
    
    # 영업일 수 계산 및 연도 변환 (252일 기준)
    total_days = len(data)
    years = total_days / 252.0 if total_days > 0 else 1.0
    
    # 연평균 수익률 (CAGR)
    cagr = ((final_val / initial_capital) ** (1 / years) - 1) * 100 if years > 0 and final_val > 0 else 0
    bh_cagr = ((bh_final_val / initial_capital) ** (1 / years) - 1) * 100 if years > 0 and bh_final_val > 0 else 0
    
    # 최대 낙폭 (MDD) 계산
    peak = data['Portfolio_Value'].cummax()
    drawdown = (data['Portfolio_Value'] - peak) / peak
    mdd = drawdown.min() * 100
    
    bh_peak = data['Buy_Hold_Value'].cummax()
    bh_drawdown = (data['Buy_Hold_Value'] - bh_peak) / bh_peak
    bh_mdd = bh_drawdown.min() * 100
    
    # 총 매매 횟수
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
        "trade_count": trade_count
    }

# =======================================================
#                      로그인 / 회원가입 제어
# =======================================================
if not st.session_state['logged_in']:
    # 타이틀 영역
    st.markdown('<div class="main-title">📊 Dynamic Stock Backtester</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">SMA(이동평균선) 골든/데드 크로스 전략으로 과거 데이터를 분석하고 투자 성과를 검증하세요.</div>', unsafe_allow_html=True)

    # 중앙 정렬용 레이아웃 구성
    _, center_col, _ = st.columns([1, 1.8, 1])
    
    with center_col:
        st.markdown('<div class="auth-container">', unsafe_allow_html=True)
        tab_login, tab_register = st.tabs(["🔐 로그인", "📝 회원가입"])
        
        # 1) 로그인 탭
        with tab_login:
            st.markdown("<br>", unsafe_allow_html=True)
            login_username = st.text_input("아이디", key="login_user")
            login_password = st.text_input("비밀번호", type="password", key="login_pass")
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("로그인", use_container_width=True, type="primary"):
                if auth.verify_user(login_username, login_password):
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = login_username
                    st.success("로그인에 성공했습니다! 페이지를 로드 중...")
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
                    
        # 2) 회원가입 탭
        with tab_register:
            st.markdown("<br>", unsafe_allow_html=True)
            reg_username = st.text_input("새로운 아이디", key="reg_user")
            reg_password = st.text_input("새로운 비밀번호", type="password", key="reg_pass")
            reg_password_confirm = st.text_input("비밀번호 확인", type="password", key="reg_pass_conf")
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("회원가입", use_container_width=True):
                if reg_password != reg_password_confirm:
                    st.error("비밀번호와 비밀번호 확인이 서로 일치하지 않습니다.")
                else:
                    success, msg = auth.register_user(reg_username, reg_password)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
                        
        st.markdown('</div>', unsafe_allow_html=True)

# =======================================================
#                      메인 애플리케이션 화면
# =======================================================
else:
    # 사이드바 설정 영역
    st.sidebar.header("⚙️ 백테스트 설정")
    
    # 사용자 정보 및 로그아웃 버튼 노출
    st.sidebar.markdown(f"👤 **{st.session_state['username']}**님 환영합니다!")
    if st.sidebar.button("🔓 로그아웃", use_container_width=True):
        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.rerun()
        
    st.sidebar.markdown("---")

    # 타이틀 영역 (로그인 후 화면에서는 중앙 정렬 제외)
    st.markdown('<h1 style="font-weight: 800; background: linear-gradient(90deg, #FF4B4B 0%, #FF8F8F 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">📊 Dynamic Stock Backtester</h1>', unsafe_allow_html=True)
    st.markdown('<p style="color: #888888; font-size: 1.1rem; margin-bottom: 2rem;">SMA(이동평균선) 골든/데드 크로스 전략으로 과거 데이터를 분석하고 투자 성과를 검증하세요.</p>', unsafe_allow_html=True)

    # 1. 티커 및 기간 설정
    st.sidebar.subheader("1. 대상 종목 & 기간")
    ticker_input = st.sidebar.text_input("주식 티커 입력 (yfinance 규격)", value="AAPL")
    st.sidebar.caption("💡 팁: 나스닥은 'AAPL', 'TSLA' 등 / 코스피는 '005930.KS', 코스닥은 '091990.KQ' 형식으로 입력하세요.")

    today = datetime.today()
    default_start = today - timedelta(days=365 * 3) # 기본 3년 전
    start_date = st.sidebar.date_input("시작일", default_start)
    end_date = st.sidebar.date_input("종료일", today)

    # 2. 투자 조건 설정
    st.sidebar.subheader("2. 투자 조건")
    initial_capital = st.sidebar.number_input("초기 투자금 ($ 또는 ₩)", min_value=1000, value=10000, step=1000)
    commission_pct = st.sidebar.slider("거래 수수료 (%)", min_value=0.0, max_value=1.0, value=0.1, step=0.05) / 100.0

    # 3. SMA 변수 설정
    st.sidebar.subheader("3. 이동평균선(SMA) 설정")
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
                    st.error("데이터를 불러오지 못했거나 백테스트를 위한 충분한 역사적 데이터(장기 이평선 기준 이상)가 없습니다. 티커 및 날짜 범위를 확인해 주세요.")
                else:
                    # 백테스트 수행
                    results = run_backtest(df, short_window, long_window, initial_capital, commission_pct)
                    metrics = calculate_metrics(results, initial_capital)
                    
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
                    
                    with col2:
                        st.markdown(
                            f"""<div class="metric-card">
                                <div class="metric-label">연평균 수익률 (CAGR)</div>
                                <div class="metric-value">{metrics['cagr']:.2f}%</div>
                                <div style="color: #94A3B8; font-size: 0.85rem;">
                                    시장 평균(B&H): {metrics['bh_cagr']:.2f}%
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
                                    시장 평균(B&H): {metrics['bh_mdd']:.2f}%
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
                                    수수료 적용: {commission_pct*100:.2f}% / 거래
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
