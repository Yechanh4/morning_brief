# -*- coding: utf-8 -*-
"""
💰 시장 데이터 모듈 — yfinance 실시간 시세로 현재가 + 등락률 + 원화환산.

fast_info(실시간)를 우선 사용해서 일봉 반영 지연 문제를 피한다.
해외(USD 등) 자산은 실시간 환율로 원화 환산값도 함께 제공.
"""

import warnings
warnings.filterwarnings("ignore")

from modules.quote import get_quote, get_krw_rate


def fetch_one(name: str, symbol: str, unit: str = "", krw_rate: float = None):
    """
    종목 1개의 현재가·등락률·원화환산.
    반환: (데이터dict, 에러메시지 or None)
    """
    q, err = get_quote(symbol)
    if err:
        return None, err
    price = q["last"] if q["last"] is not None else q["completed_close"]
    prev = q["prev_close"]
    if price is None:
        return None, "가격 없음(심볼 확인 필요)"

    change = (price - prev) if prev else 0.0
    change_pct = (change / prev * 100) if prev else 0.0

    # 원화 환산: USD 자산만. 단, 지수(^...)는 '포인트'라 환산 무의미 → 제외
    currency = q.get("currency") or ""
    krw_price = None
    is_index = symbol.startswith("^")
    if currency == "USD" and krw_rate and not is_index:
        krw_price = price * krw_rate

    return {
        "name": name, "symbol": symbol, "unit": unit,
        "price": price, "change": change, "change_pct": change_pct,
        "arrow": "▲" if change > 0 else ("▼" if change < 0 else "="),
        "currency": currency, "is_open": q["is_open"],
        "completed_close": q["completed_close"],
        "krw_price": krw_price,
    }, None


def format_price(value: float, unit: str) -> str:
    """숫자를 보기 좋게 포맷."""
    if value is None:
        return "-"
    if unit == "원":
        return f"{value:,.1f}원"
    if abs(value) >= 1000:
        return f"{value:,.0f}{unit}"
    return f"{value:,.2f}{unit}"


def format_krw(value: float) -> str:
    """원화 환산값 포맷."""
    if value is None:
        return ""
    return f"{value:,.0f}원"


def fetch_all_market(tickers):
    """
    전체 시장 데이터 수집 (+ 실시간 환율로 원화 환산).
    반환 dict: {"results":[...], "errors":[...], "krw_rate": 환율}
    """
    krw_rate = get_krw_rate()
    results, errors = [], []
    for t in tickers:
        data, err = fetch_one(t["name"], t["symbol"], t.get("unit", ""), krw_rate=krw_rate)
        if err:
            errors.append(f"{t['name']}({t['symbol']}): {err}")
            continue
        results.append(data)
    return {"results": results, "errors": errors, "krw_rate": krw_rate}
