import re

file_path = r"C:\Users\joung\.gemini\antigravity-ide\scratch\stock-backtester\app.py"

with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# 1420행 부근 HHI가 깨진 구역을 완전히 정상적인 코드로 교체합니다.
# HHI 진단 시작부터 breadth 카드 진단 이전까지의 깨진 텍스트 영역을 찾아 교체합니다.

# st.markdown("##### 🛡️ 포트폴리오 리스크 진단 및 조언") 아래 HHI 계산 로직 부분
broken_section_start = '# 2. HHI (허핀달-허쉬만 다각화 지수) 정밀 진단'
broken_section_end = '# 3. 오늘의 상승 vs 하락 자산 승률 통계 (Market Breadth)'

idx_start = content.find(broken_section_start)
idx_end = content.find(broken_section_end)

if idx_start != -1 and idx_end != -1:
    hhi_clean_block = """# 2. HHI (허핀달-허쉬만 다각화 지수) 정밀 진단
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
                            
                            """
    # 교체 처리
    content = content[:idx_start] + hhi_clean_block + content[idx_end:]
    print("Clean HHI block injected successfully.")

# 지표 설명 문구 교체 로직
content = content.replace(
    'vix_chg:+.2f}%\n                        </div>\n                    </div>',
    'vix_chg:+.2f}%\n                        </div>\n                        <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">\n                            <b>📈 상승 시</b>: 시장 불안 심리 증폭, 주가 급락 위험 고조<br>\n                            <b>📉 하락 시</b>: 투자 심리 안정화, 안도 랠리 전개\n                        </div>\n                    </div>'
)

content = content.replace(
    '0(극단적 공포) ~ 100(극단적 탐욕)\n                        </div>\n                    </div>',
    '0(극단적 공포) ~ 100(극단적 탐욕)\n                        </div>\n                        <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">\n                            <b>📈 상승 시</b>: 시장 낙관(과열) 극대화로 단기 고점 조정 주의<br>\n                            <b>📉 하락 시</b>: 패닉 셀링 극대화로 저가 분할 매수 매력 증가\n                        </div>\n                    </div>'
)

content = content.replace(
    '임계값: 1.0 초과 시 하락 베팅 과열\n                        </div>\n                    </div>',
    '임계값: 1.0 초과 시 하락 베팅 과열\n                        </div>\n                        <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">\n                            <b>📈 상승 시</b>: 하락 베팅(Put) 급증으로 단기 추가 하방 압력<br>\n                            <b>📉 하락 시</b>: 상승 베팅(Call) 기조로 긍정적 매수세 유입\n                        </div>\n                    </div>'
)

content = content.replace(
    '미 GDP비 시가총액 비율 (기준: 120% 초과 시 고평가)\n                        </div>\n                    </div>',
    '미 GDP비 시가총액 비율 (기준: 120% 초과 시 고평가)\n                        </div>\n                        <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">\n                            <b>📈 상승 시</b>: GDP 대비 주식 가치 과대평가로 거품 붕괴 위험 증가<br>\n                            <b>📉 하락 시</b>: 실물 실적 대비 저평가 매수 안심 구간 진입\n                        </div>\n                    </div>'
)

content = content.replace(
    '10Y: {yield_10y:.2f}% / 3M: {yield_3m:.2f}% (마이너스 시 1~2년 내 경기 침체 예고)\n                        </div>\n                    </div>',
    '10Y: {yield_10y:.2f}% / 3M: {yield_3m:.2f}% (마이너스 시 1~2년 내 경기 침체 예고)\n                        </div>\n                        <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">\n                            <b>📈 상승 시</b>: 정상적 경기 확장세, 기업 환경 양호<br>\n                            <b>📉 하락(역전) 시</b>: 자금 경색 심화 및 향후 경기 침체(R의 공포) 임박 강력 예고\n                        </div>\n                    </div>'
)

content = content.replace(
    '안전 국채(IEF) 대비 정크본드(HYG) 비율 (증가 시 부도 리스크 급등)\n                        </div>\n                    </div>',
    '안전 국채(IEF) 대비 정크본드(HYG) 비율 (증가 시 부도 리스크 급등)\n                        </div>\n                        <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">\n                            <b>📈 상승 시</b>: 부실 회사채 가치 폭락, 기업 부도 위기 급증 및 주식 악재<br>\n                            <b>📉 하락 시</b>: 신용 위험 해소 및 리스크 온 자금 선호\n                        </div>\n                    </div>'
)

content = content.replace(
    '은행 간 단기 차입 금리와 단기 국채 금리차 (급등 시 금융 시스템 마비)\n                        </div>\n                    </div>',
    '은행 간 단기 차입 금리와 단기 국채 금리차 (급등 시 금융 시스템 마비)\n                        </div>\n                        <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">\n                            <b>📈 상승 시</b>: 시중 대형 은행 간 신용 경색 심화, 유동성 위기 징후<br>\n                            <b>📉 하락 시</b>: 은행 유동성 풍부 및 전반적 자금 흐름 양호\n                        </div>\n                    </div>'
)

content = content.replace(
    '빚내서 주식 산 잔고 규모 (20조 원 돌파 시 폭락 뇌관 위험)\n                        </div>\n                    </div>',
    '빚내서 주식 산 잔고 규모 (20조 원 돌파 시 폭락 뇌관 위험)\n                        </div>\n                        <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">\n                            <b>📈 상승 시</b>: 신용 레버리지 빚투 과열로 주가 하락 전환 시 투매/반대매매 도화선화<br>\n                            <b>📉 하락 시</b>: 시장의 거품 악성 부채가 청산 완료되어 가볍고 탄탄한 수급 구조\n                        </div>\n                    </div>'
)

content = content.replace(
    '전일비: {usd_chg:+.2f}% (1,350원 돌파 시 한국 증시 외국인 순매도 압력)\n                        </div>\n                    </div>',
    '전일비: {usd_chg:+.2f}% (1,350원 돌파 시 한국 증시 외국인 순매도 압력)\n                        </div>\n                        <div style="border-top: 1px solid #334155; margin-top: 0.6rem; padding-top: 0.4rem; font-size: 0.78rem; color: #94A3B8; line-height: 1.35;">\n                            <b>📈 상승 시</b>: 원화 가치 절하로 외국인 환차손 리스크 부각, 대규모 외인 이탈 유발<br>\n                            <b>📉 하락 시</b>: 원화 강세 전환으로 환차익 매력 증가, 외인 순매수세 국내 유치\n                        </div>\n                    </div>'
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Repair completed successfully!")
