file_path = r"C:\Users\joung\.gemini\antigravity-ide\scratch\stock-backtester\app.py"

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 1. 💼 포트폴리오 분석 및 최적화 기존 사이드바 입력 코드 구간 치환
old_port_input = """        st.sidebar.subheader("1. 포트폴리오 구성 종목")
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
            st.session_state['port_run'] = True"""

new_port_input = """        # 🛠️ 본문 설정 입력 카드 (오른쪽 메인 대시보드 내)
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
            
        if st.session_state.get('port_run_triggered', False):"""

content = content.replace(old_port_input, new_port_input)

# 2. 백테스터 기존 사이드바 입력 코드 구간 치환
old_backtest_input = """        st.sidebar.subheader("1. 대상 종목 & 기간")
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
            st.session_state['backtest_run'] = True"""

new_backtest_input = """        # 🛠️ 본문 설정 입력 카드
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
            
        if st.session_state.get('backtest_run_triggered', False):"""

content = content.replace(old_backtest_input, new_backtest_input)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Migration of controls executed successfully.")
