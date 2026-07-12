file_path = r"C:\Users\joung\.gemini\antigravity-ide\scratch\stock-backtester\app.py"

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 1. 탑레벨 헬퍼 함수 get_live_cnn_fear_and_greed() 추가
# 'def draw_sparkline(df, is_positive):' 검색 후 바로 위에 이식
helper_target = "def draw_sparkline(df, is_positive):"
idx_helper = content.find(helper_target)

if idx_helper != -1 and "get_live_cnn_fear_and_greed" not in content:
    helper_code = """def get_live_cnn_fear_and_greed():
    \"\"\"
    CNN Markets 공식 REST API로부터 현재 공포와 탐욕 지수 점수 및 등급을 실시간 크롤링 연동.
    실패 시 (None, None) 반환하여 폴백 가동 유도.
    \"\"\"
    import requests
    url = "https://r1.cnn.io/fear-and-greed-index/current"
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
    return None, None

"""
    content = content[:idx_helper] + helper_code + content[idx_helper:]
    print("CNN F&G API helper function injected.")

# 2. 대시보드 내의 F&G 카드 계산 로직을 실시간 API 연동 + 폴백 구조로 교체
# st.fragment 내부의 F&G 점수 연산 파트 교체
old_fg_calc = """                vix_norm = max(0, min(100, (35 - vix_val) * 4))
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
                    \"\"\", unsafe_allow_html=True)"""

new_fg_calc = """                # CNN 공식 REST API 연동 시도 (실패 시 프록시 보정 엔진 가동)
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
                    \"\"\", unsafe_allow_html=True)"""

idx_fg = content.find(old_fg_calc)
if idx_fg != -1:
    content = content.replace(old_fg_calc, new_fg_calc)
    print("Fear & Greed official logic replaced successfully.")
else:
    print("Could not find old Fear & Greed logic block in app.py.")

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Repair completed.")
