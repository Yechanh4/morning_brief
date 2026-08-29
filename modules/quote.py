# -*- coding: utf-8 -*-
"""
📡 시세/장시간/환율 모듈 — Yahoo Finance(yfinance) 실시간 시세를 정확하게 가져온다.

핵심:
- history()(일봉)는 최근 거래일 종가 반영이 지연될 때가 있어(NaN) → fast_info(실시간)를 병행.
- 한국시간(KST) 기준으로 각 거래소의 개장/폐장을 판단해서
  '장중가(live)'인지 '완료 종가(completed close)'인지 정확히 구분.
- 해외자산 원화 환산용 실시간 환율 제공.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import yfinance as yf


def market_class(symbol: str) -> str:
    if symbol.endswith(".KS") or symbol.endswith(".KQ") or symbol == "^KS11":
        return "KR"
    if symbol.endswith("=X"):
        return "FX"
    if symbol.endswith("-USD"):
        return "CRYPTO"
    if symbol.endswith("=F"):
        return "FUT"
    return "US"   # 미국 지수/개별주


_TZ = {"KR": "Asia/Seoul", "US": "America/New_York", "FUT": "America/New_York",
       "FX": "UTC", "CRYPTO": "UTC"}


def is_market_open(symbol: str, now=None) -> bool:
    """지금 이 자산의 정규장이 열려있는지 (거래소 로컬타임 기준)."""
    cls = market_class(symbol)
    tz = ZoneInfo(_TZ[cls])
    n = (now.astimezone(tz) if now else datetime.now(tz))
    if cls == "CRYPTO":
        return True
    if n.weekday() >= 5:        # 토·일 휴장
        return False
    t = n.time()
    if cls == "KR":
        return time(9, 0) <= t <= time(15, 30)      # 한국 정규장
    if cls == "US":
        return time(9, 30) <= t <= time(16, 0)      # 미국 정규장
    return True                 # FX·선물: 평일 사실상 24h


def get_quote(symbol: str):
    """
    한 자산의 정확한 시세.
    반환 dict:
      last            : 현재/최근 체결가 (앱에 뜨는 값)
      prev_close      : 직전 거래일 종가
      completed_close : '가장 최근에 마감된 정규장' 종가
                        (장 열려있으면 prev_close, 닫혀있으면 last)
      is_open         : 지금 정규장 개장 여부
      currency, timezone
    """
    try:
        fi = yf.Ticker(symbol).fast_info
        last = fi.get("lastPrice")
        prev = fi.get("previousClose")
        cur = fi.get("currency")
        tz = fi.get("timezone")
        opn = is_market_open(symbol)
        completed = (prev if opn else last)   # 장중이면 어제 종가가 마지막 '완료' 종가
        if completed is None:
            completed = last if last is not None else prev
        return {
            "symbol": symbol, "last": last, "prev_close": prev,
            "completed_close": completed, "is_open": opn,
            "currency": cur, "timezone": tz,
        }, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def get_krw_rate():
    """실시간 원/달러 환율 (USD→KRW). 실패 시 None."""
    try:
        fi = yf.Ticker("KRW=X").fast_info
        r = fi.get("lastPrice") or fi.get("previousClose")
        return float(r) if r else None
    except Exception:
        return None
