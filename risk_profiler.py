import re

# 초고위험 3배/2배 레버리지 키워드 정규식
RE_3X = re.compile(r'\b(3X|3x|TRIPLE)\b|TQQQ|SOXL|FNGU|TECL|UPRO|SPXL|SOXS|SQQQ|TECS|FNGD|SPXS|곱버스', re.IGNORECASE)
RE_2X = re.compile(r'\b(2X|2x|DOUBLE|ULTRA)\b|QLD|SSO|UWM|USD|MVV|SCO|UGL', re.IGNORECASE)

# 인버스(숏) 키워드 정규식
RE_INVERSE = re.compile(r'\b(INVERSE|SHORT|BEAR|SH)\b|SQQQ|SOXS|TECS|FNGD|SPXS|인버스|곱버스', re.IGNORECASE)

# 가상자산/코인 관련 ETF 및 주식 키워드 정규식
RE_CRYPTO = re.compile(r'\b(BTC|ETH|BITCOIN|ETHER|CRYPTO|COINBASE|MARA|RIOT|MSTR|IBIT|FBTC|BITO|COIN)\b', re.IGNORECASE)

def profile_asset_risk(ticker, annual_volatility=None):
    """
    구성 종목 티커를 분석하여 자산의 고유 위험 정보(레버리지, 인버스, 암호화폐, 초고변동성)와 경고 코멘트를 반환
    """
    ticker_clean = ticker.strip().upper()
    
    risks = []
    
    # 1. 3배 레버리지 체크
    if RE_3X.search(ticker_clean):
        risks.append({
            "level": "🚨 초고위험 (3배 레버리지)",
            "color": "#FF4B4B",
            "title": f"⚠️ {ticker_clean}: 3배 레버리지 고위험 자산 감지",
            "desc": "이 자산은 일간 기초자산 수익률의 3배를 추종하는 초고위험 상품입니다. 횡보장이나 변동성 장세가 장기화될 경우, '음의 복리 효과(Volatility Drag)'로 인해 기초자산 지수는 제자리임에도 내 원금은 크게 녹아내리는 치명적인 리스크가 있습니다. 장기 보유용 자산으로 적합하지 않으며, 단기 추세 추종 전략용으로만 접근할 것을 권장합니다."
        })
    # 2. 2배 레버리지 체크
    elif RE_2X.search(ticker_clean):
        risks.append({
            "level": "⚠️ 고위험 (2배 레버리지)",
            "color": "#F1C40F",
            "title": f"⚠️ {ticker_clean}: 2배 레버리지 위험 자산 감지",
            "desc": "이 자산은 일간 수익률의 2배를 추종하는 고위험 레버리지 상품입니다. 장기 보유 시 복리 침식 위험이 작동하므로 주기적인 리밸런싱을 반드시 수행하거나, 짧은 호흡의 전술적 자산 배분(Tactical Asset Allocation)에만 비중을 한정하여 담으시는 것을 조언합니다."
        })
        
    # 3. 인버스(숏) 상품 체크
    if RE_INVERSE.search(ticker_clean):
        risks.append({
            "level": "🚨 초고위험 (인버스/숏)",
            "color": "#FF4B4B",
            "title": f"⚠️ {ticker_clean}: 인버스(숏) 하락 추종 자산 감지",
            "desc": "이 자산은 시장 하락에 베팅하여 역방향 수익률을 추종하는 상품입니다. 자본주의 경제 성장 하에서 주식 시장은 장기적으로 우상향하는 경향이 있으므로, 인버스 상품을 연 단위로 장기 보유하는 것은 자멸에 가까운 투자 방식입니다. 헤지(Hedge) 목적으로 매우 짧은 기간만 사용하시길 권합니다."
        })
        
    # 4. 가상자산/코인 ETF 및 관련주 체크
    if RE_CRYPTO.search(ticker_clean):
        risks.append({
            "level": "⚠️ 고위험 (가상자산 연동)",
            "color": "#F1C40F",
            "title": f"⚠️ {ticker_clean}: 암호화폐(Crypto) 연동 자산 감지",
            "desc": "비트코인/이더리움 현물 ETF 또는 가상자산 거래소/채굴 관련 주식입니다. 가상자산 시장은 규제 변수 및 연중무휴 24시간 거래 특성상 일반 주식 시장보다 하루 변동폭이 극도로 큽니다. 투자 비중을 전체 포트폴리오의 5~10% 이내 소액으로 타이트하게 제한할 것을 강력히 권장합니다."
        })
        
    # 5. 통계적 초고변동성 체크 (연간 변동성 45% 초과인 경우)
    if annual_volatility and annual_volatility > 45.0:
        # 이미 3배 레버리지나 인버스로서 경고가 나갔다면 중복 보고 건너뜀
        if not any(r["level"].startswith("🚨") for r in risks):
            risks.append({
                "level": "⚠️ 고위험 (초고변동성 개별주/밈주)",
                "color": "#F1C40F",
                "title": f"⚠️ {ticker_clean}: 연간 변동성 경보 ({annual_volatility:.1f}%)",
                "desc": "이 주식은 통계적으로 연간 변동성(표준편차)이 45%를 상회하는 극도로 거친 종목입니다. 단기간에 큰 수익을 안겨줄 수도 있으나, 지수 하락장 도래 시 고점 대비 50~70% 이상의 끔찍한 최대 낙폭(MDD)을 겪어 심리적으로 분할매수가 깨지기 십상입니다. 안전한 포트폴리오 유지를 위해 비중 통제가 강제됩니다."
            })
            
    return risks
