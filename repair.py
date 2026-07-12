file_path = r"C:\Users\joung\.gemini\antigravity-ide\scratch\stock-backtester\app.py"

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 1. get_live_cnn_fear_and_greed 헬퍼 함수를 get_live_cnn_data 통합 데이터 연동 함수로 전면 개체 치환
old_helper_code = """def get_live_cnn_fear_and_greed():
    \"\"\"
    CNN Markets 공식 REST API로부터 현재 공포와 탐욕 지수 점수 및 등급을 실시간 크롤링 연동.
    실패 시 (None, None) 반환하여 폴백 가동 유도.
    \"\"\"
    import requests
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        r = requests.get(url, headers=headers, timeout=3.5)
        if r.status_code == 200:
            data = r.json()
            score = float(data.get("fear_and_greed", {}).get("score", 50.0))
            rating = str(data.get("fear_and_greed", {}).get("rating", "neutral")).strip().lower()
            return score, rating
    except Exception:
        pass
    return None, None"""

new_helper_code = """def get_live_cnn_data():
    \"\"\"
    CNN Markets 공식 REST API로부터 공포와 탐욕 및 7대 하부 지수 데이터를 모두 실시간 연동.
    실패 시 None 반환하여 폴백 가동 유도.
    \"\"\"
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
    return None"""

content = content.replace(old_helper_code, new_helper_code)

# 2. 대시보드 내의 시간 보정(KST) 및 CNN 풋콜 지수/F&G 데이터 바인딩 로직 업데이트
# elif admin_mode == "🚨 시장 위험 지표": 안의 render_market_risk_dashboard_live 내부 통째 교체

old_dashboard_internal = """            col_ref, col_lbl = st.columns([1.2, 4])
            with col_ref:
                if st.button("🔄 실시간 시세 강제 갱신", use_container_width=True):
                    st.rerun()
            with col_lbl:
                now_str = datetime.now().strftime("%H:%M:%S")
                st.markdown(f"<p style='color: #888888; font-size: 0.9rem; margin-top: 0.4rem;'>⏰ 최근 실시간 갱신 시각: <b>{now_str}</b> (15초 주기로 자동 새로고침 중)</p>", unsafe_allow_html=True)
                
            with st.spinner("글로벌 거시 경제 및 풋/콜 옵션 실시간 수치 다운로드 및 분석 중..."):
                tickers_to_load = ["^VIX", "^W5000", "^TNX", "^IRX", "HYG", "IEF", "USDKRW=X"]
                
                risk_data = {}
                for t in tickers_to_load:
                    try:
                        # 실시간 수집 보장을 위해 캐시 우회형 5일치 다운로드
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
                
                try:
                    spy_ticker = yf.Ticker("SPY")
                    opt_dates = spy_ticker.options
                    if opt_dates:
                        nearest_opt = spy_ticker.option_chain(opt_dates[0])
                        put_oi = nearest_opt.puts['openInterest'].sum()
                        call_oi = nearest_opt.calls['openInterest'].sum()
                        put_call_ratio = put_oi / call_oi if call_oi > 0 else 0.85
                    else:
                        put_call_ratio = 0.82
                except Exception:
                    put_call_ratio = 0.85
                    
                # 1구역: 투자 심리 및 옵션 시장 지표
                st.markdown("### 1. 🗳️ 투자 심리 및 옵션 시장 지표")
                c_r1_1, c_r1_2, c_r1_3 = st.columns(3)
                
                vix_val = risk_data.get("^VIX", {}).get("price", 15.0)
                vix_chg = risk_data.get("^VIX", {}).get("change", 0.0)
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
                # CNN 공식 REST API 연동 시도 (실패 시 프록시 보정 엔진 가동)
                cnn_score, cnn_rating = get_live_cnn_fear_and_greed()
                is_official = False
                
                if cnn_score is not None:
                    fg_score = cnn_score
                    is_official = True
                    # CNN 등급을 한글 상태 라벨로 매핑
                    rating_map = {
                        "extreme fear": ("🚨 극도 공포 (Extreme Fear)", "#FF4B4B"),
                        "fear": ("⚠️ 공포 (Fear)", "#EF553B"),
                        "neutral": ("🟡 중립 (Neutral)", "#F1C40F"),
                        "greed": ("🟢 탐욕 (Greed)", "#00CC96"),
                        "extreme greed": ("🔥 극도 탐욕 (Extreme Greed)", "#10B981")
                    }
                    fg_state, fg_color = rating_map.get(cnn_rating, ("🟡 중립 (Neutral)", "#F1C40F"))
                else:
                    # Fallback (야후 파이낸스 프록시)
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
                        
                official_tag = '<span style="color: #10B981; font-size: 0.75rem; font-weight: 600; float: right;">✓ CNN 공식 연동</span>' if is_official else '<span style="color: #EF553B; font-size: 0.75rem; font-weight: 600; float: right;">⚠ 폴백 모사 가동</span>'
                
                with c_r1_2:
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
                pcr_val = put_call_ratio
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
                    st.markdown(f\"\"\"
                        <div class="metric-card" style="border-left: 5px solid {pcr_color};">
                            <div class="metric-label">풋/콜 비율 (Put/Call Ratio)</div>
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
                    \"\"\", unsafe_allow_html=True)
                    
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
                st.markdown("<br>### 3. 💳 신용 및 기업 부도 위험 지표", unsafe_allow_html=True)
                c_r3_1, c_r3_2 = st.columns(2)
                
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)"""

new_dashboard_internal = """            col_ref, col_lbl = st.columns([1.2, 4])
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)"""

idx_internal = content.find(old_dashboard_internal)
if idx_internal != -1:
    content = content.replace(old_dashboard_internal, new_dashboard_internal)
    print("Dashboard internal logic successfully replaced.")
else:
    print("Could not find old dashboard internal block in app.py.")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Repair completed.")
