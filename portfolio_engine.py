import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

def get_portfolio_data(tickers, start_date, end_date):
    """여러 종목의 종가 데이터를 가져와 단일 데이터프레임으로 병합"""
    if not tickers:
        return None
        
    data_dict = {}
    for ticker in tickers:
        ticker = ticker.strip().upper()
        if not ticker:
            continue
        try:
            raw = yf.download(ticker, start=start_date, end=end_date)
            if not raw.empty:
                # yfinance MultiIndex 컬럼 수정
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                
                # 수정 종가 반영
                if 'Adj Close' in raw.columns:
                    data_dict[ticker] = raw['Adj Close']
                elif 'Close' in raw.columns:
                    data_dict[ticker] = raw['Close']
        except Exception:
            continue
            
    if not data_dict:
        return None
        
    # 하나의 데이터프레임으로 결합
    df = pd.DataFrame(data_dict)
    df = df.ffill().bfill()  # 누락 데이터 보정
    return df

def backtest_portfolio(df, weights, initial_capital, rebalance_period="None", contribution_amount=0.0):
    """
    주어진 자산 비중으로 포트폴리오 백테스트 시뮬레이션
    - rebalance_period: "None", "Monthly", "Annually"
    - contribution_amount: 매월 초 추가로 납입할 적립식 자금
    """
    # 비중 배열 변환 및 정규화
    w = np.array(weights)
    w = w / np.sum(w)  # 비중 합이 1이 되도록 조정
    
    num_assets = len(df.columns)
    prices = df.values  # 일별 주가 행렬
    dates = df.index
    
    portfolio_values = []
    
    # 초기 주식 수 및 현금 분배
    total_val = initial_capital
    shares = np.zeros(num_assets)
    cash = 0.0
    
    # 첫째 날 매수 진행
    first_prices = prices[0]
    for j in range(num_assets):
        shares[j] = (total_val * w[j]) / first_prices[j]
        
    portfolio_values.append(total_val)
    
    prev_date = dates[0]
    
    # 일별 시뮬레이션 루프
    for i in range(1, len(df)):
        curr_date = dates[i]
        curr_prices = prices[i]
        
        # 1) 매월 초 적립식 자금 추가 납입 감지 (이전 데이터와 비교해 달이 변경되었을 때)
        is_new_month = curr_date.month != prev_date.month
        is_new_year = curr_date.year != prev_date.year
        
        if is_new_month and contribution_amount > 0:
            # 적립금을 현재 비중(타겟 비중)대로 추가 매수
            for j in range(num_assets):
                additional_shares = (contribution_amount * w[j]) / curr_prices[j]
                shares[j] += additional_shares
        
        # 2) 주기적 리밸런싱 감지 및 수행
        should_rebalance = False
        if rebalance_period == "Monthly" and is_new_month:
            should_rebalance = True
        elif rebalance_period == "Annually" and is_new_year:
            should_rebalance = True
            
        if should_rebalance:
            # 현재 모든 주식을 당일 주가로 현금화(평가)
            current_total_value = np.sum(shares * curr_prices) + cash
            # 평가액을 다시 타겟 비중으로 쪼개서 재매수
            for j in range(num_assets):
                shares[j] = (current_total_value * w[j]) / curr_prices[j]
            
        # 당일 평가 가치 기록
        day_value = np.sum(shares * curr_prices) + cash
        portfolio_values.append(day_value)
        
        prev_date = curr_date
        
    # 결과 데이터프레임 정리
    results_df = pd.DataFrame(index=df.index)
    results_df['Portfolio_Value'] = portfolio_values
    results_df['Daily_Return'] = results_df['Portfolio_Value'].pct_change().fillna(0)
    
    # 최종 성과 통계 연산
    final_value = portfolio_values[-1]
    
    # 누적 투자 금액 계산 (초기자본 + 매월 적립금)
    total_invested = initial_capital
    if contribution_amount > 0:
        # 월별 변동 횟수만큼 적립금 누적
        months_count = len(results_df.resample('ME' if hasattr(pd.Series, 'resample') else 'M').last()) - 1
        total_invested += (months_count * contribution_amount)
        
    total_return = (final_value - total_invested) / total_invested * 100
    
    total_days = len(df)
    years = total_days / 252.0 if total_days > 0 else 1.0
    cagr = ((final_value / initial_capital) ** (1 / years) - 1) * 100 if years > 0 and final_value > 0 else 0
    
    peak = results_df['Portfolio_Value'].cummax()
    mdd = ((results_df['Portfolio_Value'] - peak) / peak).min() * 100
    
    # 샤프 비율 및 소르티노 비율 계산 (무위험 수익률 2% 가정)
    risk_free_rate = 0.02
    daily_rf = risk_free_rate / 252.0
    excess_returns = results_df['Daily_Return'] - daily_rf
    
    # 샤프 분모: 전체 변동성
    std_dev = results_df['Daily_Return'].std() * np.sqrt(252)
    sharpe_ratio = (excess_returns.mean() * 252) / std_dev if std_dev > 0 else 0
    
    # 소르티노 분모: 하방 변동성 (음의 초과 수익률만 사용)
    downside_returns = excess_returns[excess_returns < 0]
    downside_deviation = downside_returns.std() * np.sqrt(252)
    sortino_ratio = (excess_returns.mean() * 252) / downside_deviation if downside_deviation > 0 else 0
    
    # 연도별 수익률 통계 추출 (Portfolio Visualizer 핵심 탑재)
    results_df['Year'] = results_df.index.year
    yearly_last_val = results_df.groupby('Year')['Portfolio_Value'].last()
    
    yearly_returns = []
    prev_val = initial_capital
    for yr, val in yearly_last_val.items():
        # 해당 연도 동안의 추가 납입금 계산
        yr_contributions = 0
        if contribution_amount > 0:
            # 해당 연도의 월 수 계산
            yr_months = len(results_df[results_df.index.year == yr].resample('ME' if hasattr(pd.Series, 'resample') else 'M').last())
            # 첫 해나 매월 초 추가 납입 처리
            yr_contributions = yr_months * contribution_amount
            
        # 순수한 투자 자산 성장 대비 연도별 수익률 산출
        yr_return = (val - (prev_val + yr_contributions)) / (prev_val + yr_contributions) * 100
        yearly_returns.append({"Year": yr, "Return": yr_return})
        prev_val = val
        
    # Best / Worst Year 선정
    return_rates = [yr["Return"] for yr in yearly_returns]
    best_year = max(return_rates) if return_rates else 0.0
    worst_year = min(return_rates) if return_rates else 0.0
    
    return {
        "df": results_df,
        "final_value": float(final_value),
        "total_invested": float(total_invested),
        "total_return": total_return,
        "cagr": cagr,
        "mdd": mdd,
        "sharpe_ratio": sharpe_ratio,
        "sortino_ratio": sortino_ratio,
        "std_dev": std_dev * 100,
        "yearly_returns": yearly_returns,
        "best_year": best_year,
        "worst_year": worst_year
    }

def optimize_portfolio(df, num_portfolios=2000):
    """현대 포트폴리오 이론(MPT) 기반 몬테카를로 최적 자산 배분 탐색"""
    returns = df.pct_change().dropna()
    num_assets = len(df.columns)
    
    # 연평균 수익률 및 공분산 행렬
    mean_returns = returns.mean() * 252
    cov_matrix = returns.cov() * 252
    
    results = np.zeros((3 + num_assets, num_portfolios))
    
    # 몬테카를로 시뮬레이션 루프
    for i in range(num_portfolios):
        # 무작위 비중 생성 및 정규화
        w = np.random.random(num_assets)
        w /= np.sum(w)
        
        # 기대 수익률 및 리스크 계산
        p_return = np.sum(mean_returns * w)
        p_volatility = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
        
        # 샤프 지수 (무위험 수익률 2% 가정)
        p_sharpe = (p_return - 0.02) / p_volatility if p_volatility > 0 else 0
        
        results[0, i] = p_return
        results[1, i] = p_volatility
        results[2, i] = p_sharpe
        
        for j in range(num_assets):
            results[3 + j, i] = w[j]
            
    # 데이터프레임으로 변환
    columns = ['Return', 'Volatility', 'Sharpe'] + list(df.columns)
    sim_df = pd.DataFrame(results.T, columns=columns)
    
    # 1) 최대 샤프 비율 조합 (Max Sharpe Ratio)
    max_sharpe_idx = sim_df['Sharpe'].idxmax()
    max_sharpe_portfolio = sim_df.iloc[max_sharpe_idx]
    
    # 2) 최소 변동성 조합 (Min Volatility)
    min_vol_idx = sim_df['Volatility'].idxmin()
    min_vol_portfolio = sim_df.iloc[min_vol_idx]
    
    return {
        "raw_sim": sim_df,
        "max_sharpe": {
            "return": max_sharpe_portfolio['Return'] * 100,
            "volatility": max_sharpe_portfolio['Volatility'] * 100,
            "sharpe": max_sharpe_portfolio['Sharpe'],
            "weights": {ticker: max_sharpe_portfolio[ticker] * 100 for ticker in df.columns}
        },
        "min_vol": {
            "return": min_vol_portfolio['Return'] * 100,
            "volatility": min_vol_portfolio['Volatility'] * 100,
            "sharpe": min_vol_portfolio['Sharpe'],
            "weights": {ticker: min_vol_portfolio[ticker] * 100 for ticker in df.columns}
        }
    }
