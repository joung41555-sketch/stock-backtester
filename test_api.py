import requests

url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    r = requests.get(url, headers=headers, timeout=10)
    print("Status Code:", r.status_code)
    data = r.json()
    print("Keys in JSON response:", data.keys())
    # fear_and_greed_historical 등과 같은 세부 값 구조 출력
    print("Latest Fear & Greed Data Dump:")
    # 데이터를 예쁘게 출력
    import json
    # 최근 1일치 지수(보통 데이터의 마지막 요소 또는 current 가 있을 것)
    # 데이터의 형태 확인
    # 'fear_and_greed' 키 혹은 'fear_and_greed_historical' 등이 있는지 탐색
    if 'fear_and_greed' in data:
        print("fear_and_greed:", data['fear_and_greed'])
    elif 'fear_and_greed_historical' in data:
        # 마지막 요소를 출력
        hist = data['fear_and_greed_historical']['data']
        print("Last 5 historical data:", hist[-5:])
    else:
        # 전체 데이터 중 첫 500글자만 출력
        print(json.dumps(data)[:1000])
except Exception as e:
    print("Error:", e)
