# -*- coding: utf-8 -*-
"""
💰 시장 데이터 모듈 — yfinance로 지수/환율/원자재 현재가 + 등락률을 가져온다.

핵심 함수: fetch_all_market(tickers) -> dict
- 한 종목이 실패해도 나머지는 계속 (에러 격리)
- 최근 종가 2개를 비교해서 등락률(%) 계산
"""

import warnings
warnings.filterwarnings("ignore")  # yfinance/urllib 잔소리 숨김

import yfinance as yf


def fetch_one(name: str, symbol: str, unit: str = ""):
    """
    종목 1개의 현재가와 등락률을 가져온다.
    반환: (데이터dict, 에러메시지 or None)
    """
    try:
        ticker = yf.Ticker(symbol)
        # 최근 5거래일치 종가를 받아서, 마지막 2개(어제/오늘)를 비교
        hist = ticker.history(period="5d")

        if hist is None or hist.empty or len(hist) < 1:
            return None, "데이터 없음(심볼 확인 필요)"

        closes = hist["Close"].dropna()
        if len(closes) < 1:
            return None, "종가 데이터 없음"

        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) >= 2 else last

        change = last - prev
        change_pct = (change / prev * 100) if prev else 0.0

        return {
            "name": name,
            "symbol": symbol,
            "unit": unit,
            "price": last,
            "change": change,
            "change_pct": change_pct,
            "arrow": "▲" if change > 0 else ("▼" if change < 0 else "="),
        }, None

    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def format_price(value: float, unit: str) -> str:
    """숫자를 보기 좋게 포맷 (환율/큰 수는 콤마, 소수점 정리)."""
    if unit == "원":
        return f"{value:,.1f}원"
    if abs(value) >= 1000:
        return f"{value:,.0f}{unit}"
    return f"{value:,.2f}{unit}"


def fetch_all_market(tickers):
    """
    config.py의 MARKET_TICKERS 전체를 수집.

    반환 dict:
    {
      "results": [ {name, price, change_pct, arrow, ...}, ... ],
      "errors":  [ "이름: 에러", ... ],
    }
    """
    results = []
    errors = []

    for t in tickers:
        data, err = fetch_one(t["name"], t["symbol"], t.get("unit", ""))
        if err:
            errors.append(f"{t['name']}({t['symbol']}): {err}")
            continue
        results.append(data)

    return {"results": results, "errors": errors}
