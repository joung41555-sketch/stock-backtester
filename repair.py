file_path = r"C:\Users\joung\.gemini\antigravity-ide\scratch\stock-backtester\app.py"

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 🎯 종합 분석 카드 출력 코드 바로 뒤에 이식할 타깃 구역 탐색
target_analysis_card_end = """                                # 성향 요약 카드 출력
                                st.markdown(f\"\"\"
                                    <div class="opt-card" style="border-color: {style_color}; padding: 1.5rem; margin-bottom: 1.5rem;">
                                        <div style="font-weight: 800; font-size: 1.15rem; color: #F8FAFC; margin-bottom: 0.5rem;">
                                            🎯 종합 분석: <span style="color: {style_color};">{user_style}</span>
                                        </div>
                                        <div style="font-size: 0.95rem; color: #94A3B8; line-height: 1.45;">
                                            {style_desc}
                                        </div>
                                    </div>
                                \"\"\", unsafe_allow_html=True)"""

idx_card = content.find(target_analysis_card_end)

if idx_card != -1:
    insert_point = idx_card + len(target_analysis_card_end)
    
    # 9대 정량 분석 리포트 연동 코드 작성
    quantitative_report_code = """
                                
                                # =======================================================
                                #        📊 포트폴리오 정량적 성과 & 리스크 정밀 진단 리포트
                                # =======================================================
                                st.markdown("<br>", unsafe_allow_html=True)
                                st.markdown("##### 📊 포트폴리오 정량적 성과 & 리스크 진단 (최근 1년 역사적 시뮬레이션)")
                                
                                with st.spinner("포트폴리오 과거 1년 일별 수익률 시뮬레이션 및 9대 정량 지표 산출 중..."):
                                    try:
                                        tickers = list(df_res['티커'].unique())
                                        all_tickers = tickers + ["SPY"]
                                        
                                        # 초고속 1년 역사적 데이터 다운로드
                                        raw_prices = yf.download(all_tickers, period="1y", progress=False)
                                        if isinstance(raw_prices.columns, pd.MultiIndex):
                                            raw_prices.columns = raw_prices.columns.get_level_values(0)
                                        
                                        close_prices = raw_prices['Close'] if 'Close' in raw_prices else raw_prices
                                        close_prices = close_prices.ffill().bfill()
                                        daily_rets = close_prices.pct_change().dropna()
                                        
                                        if not daily_rets.empty:
                                            # 유효 종목 추출 및 가중치 정규화
                                            valid_tickers = [t for t in tickers if t in daily_rets.columns]
                                            weights = [df_res[df_res['티커'] == t]['평가금액'].values[0] / total_amt for t in valid_tickers]
                                            w_sum = sum(weights)
                                            
                                            if w_sum > 0 and "SPY" in daily_rets.columns:
                                                weights = [w / w_sum for w in weights]
                                                
                                                # 포트폴리오 및 벤치마크 일일 수익률 계열 산출
                                                port_rets = (daily_rets[valid_tickers] * weights).sum(axis=1)
                                                spy_rets = daily_rets['SPY']
                                                
                                                # 1. 수익률 및 변동성 연화 (252 거래일 기준)
                                                ann_ret = (port_rets.mean() * 252) * 100
                                                ann_vol = (port_rets.std() * np.sqrt(252)) * 100
                                                spy_ann_ret = (spy_rets.mean() * 252) * 100
                                                
                                                # 2. 최대 낙폭 (MDD)
                                                cum_returns = (1 + port_rets).cumprod()
                                                running_max = cum_returns.cummax()
                                                drawdowns = (cum_returns - running_max) / running_max
                                                mdd = drawdowns.min() * 100
                                                
                                                # 3. 샤프 지수 ( Sharpe Ratio ) - 무위험 이자율 연 3.0% 가정
                                                sharpe = (ann_ret - 3.0) / ann_vol if ann_vol > 0 else 0.0
                                                
                                                # 4. 소르티노 지수 ( Sortino Ratio )
                                                downside_rets = port_rets[port_rets < 0]
                                                downside_vol = (downside_rets.std() * np.sqrt(252)) * 100 if len(downside_rets) > 0 else 0.001
                                                sortino = (ann_ret - 3.0) / downside_vol if downside_vol > 0 else 0.0
                                                
                                                # 5. 베타 ( Beta )
                                                covariance = port_rets.cov(spy_rets)
                                                spy_variance = spy_rets.var()
                                                beta_val = covariance / spy_variance if spy_variance > 0 else 1.0
                                                
                                                # 6. 트레이너 지수 ( Treynor Ratio )
                                                treynor = (ann_ret - 3.0) / beta_val if beta_val != 0 else 0.0
                                                
                                                # 7. 젠센의 알파 ( Jensen's Alpha )
                                                alpha_val = ann_ret - (3.0 + beta_val * (spy_ann_ret - 3.0))
                                                
                                                # 8. 정보 비율 ( Information Ratio )
                                                active_rets = port_rets - spy_rets
                                                tracking_error = (active_rets.std() * np.sqrt(252)) * 100
                                                info_ratio = (active_rets.mean() * 252 * 100) / tracking_error if tracking_error > 0 else 0.0
                                                
                                                # 9. 95% 일일 VaR (Value at Risk)
                                                var_95 = np.percentile(port_rets, 5) * 100
                                                
                                                # 10. 자산 간 평균 상관계수
                                                if len(valid_tickers) > 1:
                                                    corr_matrix = daily_rets[valid_tickers].corr()
                                                    num_pairs = (corr_matrix.shape[0] * (corr_matrix.shape[0] - 1)) / 2
                                                    corr_sum = (corr_matrix.values.sum() - corr_matrix.shape[0]) / 2
                                                    avg_corr = corr_sum / num_pairs if num_pairs > 0 else 1.0
                                                else:
                                                    avg_corr = 1.0
                                                    
                                                # 4대 지표 카테고리 렌더링
                                                st.markdown(f\"\"\"
                                                    <div style="background-color: #1E293B; border-radius: 12px; padding: 1.25rem; border: 1px solid #334155; margin-bottom: 1.5rem;">
                                                        <table style="width: 100%; border-collapse: collapse; font-size: 0.88rem; color: #E2E8F0;">
                                                            <thead>
                                                                <tr style="border-bottom: 2px solid #475569; text-align: left; font-weight: 800; color: #F1F5F9;">
                                                                    <th style="padding: 0.6rem 0.4rem;">구분 및 지표명</th>
                                                                    <th style="padding: 0.6rem 0.4rem; text-align: right;">산출 수치</th>
                                                                    <th style="padding: 0.6rem 0.4rem; text-align: left; padding-left: 1.5rem;">금융공학적 핵심 해석 가이드</th>
                                                                </tr>
                                                            </thead>
                                                            <tbody>
                                                                <!-- 위험 대비 수익률 지표 -->
                                                                <tr style="border-bottom: 1px solid #334155; background-color: #0F172A;">
                                                                    <td colspan="3" style="padding: 0.5rem; font-weight: 700; color: #3B82F6;">🏆 1. 위험 대비 수익률 지표 (투자 가성비 측정)</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #1E293B;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 샤프 지수 (Sharpe Ratio)</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700; color: {'#10B981' if sharpe >= 1.0 else '#F1C40F' if sharpe >= 0.0 else '#EF4444'};">{sharpe:.2f}</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">총 변동성 1단위 대비 초과수익률. 1.0 이상 시 매우 우수</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #1E293B;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 소르티노 지수 (Sortino Ratio)</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700; color: {'#10B981' if sortino >= 1.0 else '#F1C40F'};">{sortino:.2f}</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">하방 리스크(하락 변동성) 대비 초과수익. 수치가 클수록 하락에 강함</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #1E293B;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 트레이너 지수 (Treynor Ratio)</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700;">{treynor:.2f}%</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">시장 민감도(베타) 1단위 대비 초과수익. 분산이 잘 된 포트 평가에 유용</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #334155;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 정보 비율 (Information Ratio)</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700; color: {'#10B981' if info_ratio >= 0.5 else '#94A3B8'};">{info_ratio:.2f}</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">벤치마크(SPY) 대비 추적오차당 초과수익. 운용의 일관성 증명</td>
                                                                </tr>
                                                                
                                                                <!-- 하락 위험 및 변동성 지표 -->
                                                                <tr style="border-bottom: 1px solid #334155; background-color: #0F172A;">
                                                                    <td colspan="3" style="padding: 0.5rem; font-weight: 700; color: #EF553B;">🛡️ 2. 하락 위험 및 변동성 지표 (계좌 방어력 측정)</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #1E293B;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 최대 낙폭 (MDD)</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700; color: #EF4444;">{mdd:.1f}%</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">전고점 대비 최악의 역사적 낙폭. 계좌가 견뎌야 할 최대 스트레스선</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #1E293B;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 베타 ($\\\\beta$)</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700;">{beta_val:.2f}</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">시장(S&P500) 변동에 대한 민감도. 1.0 초과 시 시장보다 공격적인 자산</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #1E293B;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 표준편차 (Annual Volatility)</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700;">{ann_vol:.1f}%</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">연화 표준편차. 포트폴리오 가치가 평균 대비 일상적으로 출렁이는 범위</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #334155;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 일일 95% 신뢰 VaR</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700; color: #EF4444;">{var_95:.2f}%</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">95% 신뢰 수준 하에 발생 가능한 일일 최대 손실 추정 한계치</td>
                                                                </tr>
                                                                
                                                                <!-- 시장 대비 초과 수익 지표 -->
                                                                <tr style="border-bottom: 1px solid #334155; background-color: #0F172A;">
                                                                    <td colspan="3" style="padding: 0.5rem; font-weight: 700; color: #10B981;">📈 3. 시장 대비 초과 수익 지표 (운용 능력)</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #1E293B;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 젠센의 알파 ($\\\\alpha$)</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700; color: {'#10B981' if alpha_val >= 0 else '#EF4444'};">{alpha_val:+.2f}%</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">감수한 위험 대비 초과 수익률. 양수(+) 시 시장을 이긴 우수한 운용력</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #334155;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 벤치마크(SPY) 대비 초과수익</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700; color: {'#10B981' if (ann_ret - spy_ann_ret) >= 0 else '#EF4444'};">{(ann_ret - spy_ann_ret):+.2f}%</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">내 포트폴리오 수익률({ann_ret:.1f}%)과 S&P500 수익률({spy_ann_ret:.1f}%)의 단순 격차</td>
                                                                </tr>
                                                                
                                                                <!-- 구조 및 다각화 진단 -->
                                                                <tr style="border-bottom: 1px solid #334155; background-color: #0F172A;">
                                                                    <td colspan="3" style="padding: 0.5rem; font-weight: 700; color: #AB63FA;">⛓️ 4. 구조 및 다각화 진단</td>
                                                                </tr>
                                                                <tr style="border-bottom: 1px solid #1E293B;">
                                                                    <td style="padding: 0.5rem; font-weight: 600;">• 자산 간 평균 상관계수 ($\\\\rho$)</td>
                                                                    <td style="padding: 0.5rem; text-align: right; font-weight: 700; color: {'#10B981' if avg_corr < 0.3 else '#F1C40F' if avg_corr < 0.6 else '#EF4444'};">{avg_corr:.2f}</td>
                                                                    <td style="padding: 0.5rem; padding-left: 1.5rem; color: #94A3B8;">자산 상호간 움직임의 동조성. 수치가 낮을수록(0.3 미만) 다각화 헤지 성능 최상</td>
                                                                </tr>
                                                            </tbody>
                                                        </table>
                                                    </div>
                                                \"\"\", unsafe_allow_html=True)
                                            else:
                                                st.warning("유효 자산 데이터 연산에 실패했습니다.")
                                        else:
                                            st.warning("과거 시세 데이터를 불러오지 못했습니다.")
                                    except Exception as e:
                                        st.error(f"정량 분석 도중 오류가 발생했습니다: {str(e)}")
                                """
    
    content = content[:insert_point] + quantitative_report_code + content[insert_point:]
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Comprehensive quantitative risk/return report successfully injected.")
else:
    print("Target analysis card end block not found.")
