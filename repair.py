file_path = r"C:\Users\joung\.gemini\antigravity-ide\scratch\stock-backtester\app.py"

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 1. df_valid 필터링 직전에 CASH/USD 단일 입력 보간 코드 삽입
target_valid_df = """            df_valid = df_for_calc.dropna(subset=["티커", "매수 평단가", "보유 수량"])
            df_valid = df_valid[df_valid["티커"].str.strip() != ""]"""

idx_valid = content.find(target_valid_df)

if idx_valid != -1:
    refined_valid_df = """            # 💡 현금성 티커(CASH, USD, KRW) 입력 시 수량이나 평단가 중 하나만 채워도 복구해 주는 보간 장치
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
            df_valid = df_valid[df_valid["티커"].str.strip() != ""]"""
            
    content = content.replace(target_valid_df, refined_valid_df)
    print("Cash data editor interpolation code successfully written.")
else:
    print("df_valid target block not found.")

# 2. results.append 루프가 종료된 직후에 간편 입력 현금 병합
target_loop_end = """                    if has_error:
                        st.error(f"티커 '{error_ticker}'의 실시간 시세를 가져오는데 실패했습니다. 올바른 해외/국내 주식 티커인지 다시 확인해 주세요.")
                    else:
                        df_res = pd.DataFrame(results)"""

idx_loop = content.find(target_loop_end)

if idx_loop != -1:
    refined_loop_end = """                    if has_error:
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
                            results.append({
                                "티커": "CASH (₩)",
                                "평단가": 1.0,
                                "현재가": 1.0,
                                "보유수량": cash_krw_input,
                                "매입금액": cash_krw_input,
                                "평가금액": cash_krw_input,
                                "평가손익": 0.0,
                                "수익률": 0.0
                            })
                            total_buy_value += cash_krw_input
                            total_eval_value += cash_krw_input
                            
                        if cash_usd_input > 0:
                            usd_in_krw = cash_usd_input * usd_krw_rate
                            results.append({
                                "티커": "CASH ($)",
                                "평단가": usd_krw_rate,
                                "현재가": usd_krw_rate,
                                "보유수량": cash_usd_input,
                                "매입금액": usd_in_krw,
                                "평가금액": usd_in_krw,
                                "평가손익": 0.0,
                                "수익률": 0.0
                            })
                            total_buy_value += usd_in_krw
                            total_eval_value += usd_in_krw
                            
                        df_res = pd.DataFrame(results)"""
                        
    content = content.replace(target_loop_end, refined_loop_end)
    print("Cash data merge and integration code successfully written.")
else:
    print("Loop end target block not found.")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
