import streamlit as st
import requests

# 기본 인기 주식 리스트 (사용자가 타이핑을 시작하기 전이나 입력이 없을 때 추천)
DEFAULT_RECOMMENDATIONS = [
    "AAPL (Apple Inc.)",
    "MSFT (Microsoft Corporation)",
    "NVDA (NVIDIA Corporation)",
    "TSLA (Tesla, Inc.)",
    "AMZN (Amazon.com, Inc.)",
    "GOOGL (Alphabet Inc.)",
    "META (Meta Platforms, Inc.)",
    "005930.KS (Samsung Electronics)",
    "000660.KS (SK Hynix)",
    "^GSPC (S&P 500 Index)",
    "^IXIC (Nasdaq Composite)",
    "^KS11 (KOSPI Index)"
]

@st.cache_data(ttl=600)  # 10분 동안 동일 검색 결과 캐싱 (성능 및 지연 방지)
def search_yahoo_tickers(query: str):
    """
    야후 파이낸스 API를 호출하여 입력 문자열과 관련된 티커 및 주식명 리스트를 반환
    """
    if not query or len(query.strip()) < 1:
        return DEFAULT_RECOMMENDATIONS
        
    query = query.strip()
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={query}&newsCount=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=2.5)
        if r.status_code == 200:
            data = r.json()
            quotes = data.get("quotes", [])
            
            results = []
            for q in quotes:
                symbol = q.get("symbol")
                name = q.get("shortname") or q.get("longname") or ""
                exchange = q.get("exchange") or ""
                
                # 지표 및 주요 주식 필터링 (주로 상장 거래소 정보가 있는 것 타겟팅)
                if symbol:
                    display_name = f"{symbol} ({name}"
                    if exchange:
                        display_name += f" - {exchange}"
                    display_name += ")"
                    results.append(display_name)
                    
            if results:
                return results[:8]  # 최대 8개 목록만 리턴
    except Exception:
        pass
        
    # 예외 또는 결과 없을 시 기본 리스트 필터링해서 부분 반환
    fallback_res = [stock for stock in DEFAULT_RECOMMENDATIONS if query.upper() in stock.upper()]
    return fallback_res if fallback_res else DEFAULT_RECOMMENDATIONS
