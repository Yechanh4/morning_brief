# -*- coding: utf-8 -*-
"""
📡 시세/세션/환율 모듈 — '정규장 종가'를 정확히 가져온다 (애프터장 제외).

핵심:
- info['regularMarketPrice'] = 정규장 가격 (시간외/애프터장 제외). 이걸 종가로 사용.
- info['marketState'] 로 정규장 진행중인지 판단.
- 한국시간 기준 각 시장의 현재 세션(프리/정규/애프터/휴장) 판정 (DST 자동 반영).
- 결과는 실행 중 캐시 (같은 심볼 .info 중복 호출 방지).
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

import yfinance as yf

_cache = {}   # {symbol: quote dict}


def market_class(symbol: str) -> str:
    if symbol.endswith(".KS") or symbol.endswith(".KQ") or symbol == "^KS11":
        return "KR"
    if symbol.endswith("=X"):
        return "FX"
    if symbol.endswith("-USD"):
        return "CRYPTO"
    if symbol.endswith("=F"):
        return "FUT"
    return "US"


# ---------------- 세션 판정 (한국시간 기준, 거래소 로컬타임으로 계산해 DST 자동반영) ----------------
def current_session(market: str, now=None) -> str:
    """
    market: 'KR' 또는 'US'. 반환: '프리장'/'정규장'/'애프터장'/'휴장'
    거래소 로컬타임으로 계산 → 서머타임 자동 반영.
    """
    tz = ZoneInfo("Asia/Seoul" if market == "KR" else "America/New_York")
    n = (now.astimezone(tz) if now else datetime.now(tz))
    if n.weekday() >= 5:
        return "휴장(주말)"
    t = n.time()
    if market == "KR":   # 한국 로컬
        if time(8, 0) <= t < time(9, 0):   return "프리장"
        if time(9, 0) <= t <= time(15, 30): return "정규장"
        if time(15, 30) < t <= time(20, 0): return "애프터장"
        return "휴장"
    else:                # 미국 로컬(ET)
        if time(4, 0) <= t < time(9, 30):  return "프리장"
        if time(9, 30) <= t <= time(16, 0): return "정규장"
        if time(16, 0) < t <= time(20, 0):  return "애프터장"
        return "휴장"


def session_context() -> str:
    """분석 헤더용 한 줄: 지금 국장/미장 세션 상태."""
    return f"🇰🇷 국장 {current_session('KR')} · 🇺🇸 미장 {current_session('US')}"


def is_market_open(symbol: str) -> bool:
    cls = market_class(symbol)
    if cls == "CRYPTO":
        return True
    if cls in ("FX", "FUT"):
        return current_session("US") != "휴장(주말)"
    return current_session("KR" if cls == "KR" else "US") == "정규장"


# ---------------- 시세 (정규장 종가 우선) ----------------
def get_quote(symbol: str):
    """
    반환 dict:
      reg             : 정규장 가격 (regularMarketPrice; 정규장중=실시간, 그외=마지막 정규장 종가)
      prev_close      : 직전 정규장 종가
      completed_close : '마지막으로 마감된 정규장' 종가 (정규장 진행중이면 prev_close)
      is_open         : 정규장 진행중 여부
      currency, timezone
    (last = reg 로 별칭 유지 — 기존 코드 호환)
    """
    if symbol in _cache:
        return _cache[symbol], None
    try:
        t = yf.Ticker(symbol)
        info = t.info
        reg = info.get("regularMarketPrice")
        prev = info.get("regularMarketPreviousClose")
        state = info.get("marketState", "CLOSED")
        cur = info.get("currency")
        tz = info.get("exchangeTimezoneName") or info.get("timezone")
        if reg is None:
            raise ValueError("regularMarketPrice 없음")
        is_reg_live = (state == "REGULAR")
        completed = prev if (is_reg_live and prev is not None) else reg
        res = {
            "symbol": symbol, "reg": reg, "last": reg, "prev_close": prev,
            "completed_close": completed, "is_open": is_reg_live,
            "currency": cur, "timezone": tz, "state": state,
        }
        _cache[symbol] = res
        return res, None
    except Exception:
        # 폴백: fast_info (정규장 종가 정보가 부족할 때)
        try:
            fi = yf.Ticker(symbol).fast_info
            last = fi.get("lastPrice"); prev = fi.get("previousClose")
            opn = is_market_open(symbol)
            completed = prev if (opn and prev) else last
            res = {"symbol": symbol, "reg": last, "last": last, "prev_close": prev,
                   "completed_close": completed, "is_open": opn,
                   "currency": fi.get("currency"), "timezone": fi.get("timezone"),
                   "state": "REGULAR" if opn else "CLOSED"}
            _cache[symbol] = res
            return res, None
        except Exception as e:
            return None, f"{type(e).__name__}: {e}"


def get_krw_rate():
    """실시간 원/달러 환율. 실패 시 None."""
    q, err = get_quote("KRW=X")
    if q and q.get("reg"):
        return float(q["reg"])
    return None
