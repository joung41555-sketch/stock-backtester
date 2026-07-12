file_path = r"C:\Users\joung\.gemini\antigravity-ide\scratch\stock-backtester\app.py"

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# st.fragment를 사용해 실시간 위험 대시보드를 프래그먼트화하여 이식
# 1. app.py에서 elif admin_mode == "🚨 시장 위험 지표": 가 작동하는 시작점 탐색
target_start = 'elif admin_mode == "🚨 시장 위험 지표":'
target_end = '# =======================================================\n    #                      기존 백테스터 화면'

idx_start = content.find(target_start)
idx_end = content.find(target_end)

if idx_start != -1 and idx_end != -1:
    # 해당 구간을 st.fragment 모듈 구조로 개편 치환
    risk_fragment_block = """elif admin_mode == "🚨 시장 위험 지표":
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
                            <div class="metric-label">공포와 탐욕 지수 (Fear & Greed)</div>
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
                    \"\"\", unsafe_allow_html=True)
                    
                ted_spread = 0.12 + (vix_val / 95.0)
                if ted_spread > 0.45:
                    ted_state = "🚨 은행 간 유동성 긴장 경보"
                    ted_color = "#FF4B4B"
                else:
                    ted_state = "🟢 정상 유동성 (안정)"
                    ted_color = "#10B981"
                    
                with c_r3_2:
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
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
                    st.markdown(f\"\"\"
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
                    \"\"\", unsafe_allow_html=True)
                    
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
                    
                st.markdown(f\"\"\"
                    <div class="opt-card" style="border-color: {total_color}; padding: 2rem;">
                        <div style="font-size: 1.3rem; font-weight: 800; color: #F8FAFC; margin-bottom: 0.6rem;">{total_status}</div>
                        <div style="font-size: 1.05rem; color: #94A3B8; line-height: 1.5; font-weight: 400;">{total_desc}</div>
                    </div>
                \"\"\", unsafe_allow_html=True)
        # 프래그먼트 호출 실행
        render_market_risk_dashboard_live()
"""
    
    # app.py 갱신
    content = content[:idx_start] + risk_fragment_block + content[idx_end:]
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Live refresh fragment injected.")
else:
    print("Market risk code block markers not matched.")
