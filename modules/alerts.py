# -*- coding: utf-8 -*-
"""
🚨 이상변동 알림 모듈.

- compute_alerts(): 자산별로 각자의 최신 정규장 종가 기준 1일 변동률 + Z-score 계산 → FLAG 판정
  (한국은 당일 국장 종가, 미국은 당일 새벽 정규장 종가 — 자산별로 따로 봐서 시차 문제 없음)
- analyze_causes(): FLAG된 자산만 관련 뉴스를 끌어와 Claude가 원인 분석 (2~3문장)
"""

import os
import warnings
warnings.filterwarnings("ignore")
from datetime import datetime

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
import anthropic

from modules.news import fetch_topic
from modules.excel_export import _last_bar_complete

load_dotenv()


def _is_index_like(symbol: str) -> bool:
    """지수(^...)나 환율(...=X)이면 True → 작은 고정 임계치 적용."""
    return symbol.startswith("^") or symbol.endswith("=X")


def _lang_for(symbol: str) -> str:
    """뉴스 검색 언어: 한국 자산은 ko, 나머지는 en."""
    if symbol.endswith(".KS") or symbol.endswith(".KQ") or symbol == "^KS11" or symbol == "KRW=X":
        return "ko"
    return "en"


def compute_alerts(tickers, sigma_window=60, z_mult=2.0, pct_index=0.02, pct_stock=0.04):
    """
    자산별 이상변동 판정. 정규장 일봉 기준(prepost 미포함).
    반환: alert dict 리스트 (flagged=True/False 포함)
    """
    alerts = []
    for t in tickers:
        sym, name = t["symbol"], t["name"]
        try:
            # auto_adjust=False → 실제 종가. 진행 중인 장중 봉은 제거(정규장 완료봉만)
            h = yf.Ticker(sym).history(period="1y", interval="1d", auto_adjust=False)
            close = h["Close"].dropna()
            now_utc = pd.Timestamp(datetime.utcnow())
            if len(close) and not _last_bar_complete(sym, close.index[-1].date(), now_utc):
                close = close.iloc[:-1]
            if len(close) < 5:
                alerts.append({"name": name, "symbol": sym, "error": "데이터 부족", "flagged": False})
                continue

            rets = close.pct_change().dropna()
            last_ret = float(rets.iloc[-1])
            sigma = float(rets.tail(sigma_window).std())
            z = (last_ret / sigma) if sigma else 0.0
            fixed = pct_index if _is_index_like(sym) else pct_stock
            z_hit = abs(z) >= z_mult
            pct_hit = abs(last_ret) >= fixed

            alerts.append({
                "name": name, "symbol": sym,
                "date": close.index[-1].strftime("%Y-%m-%d"),
                "last_close": float(close.iloc[-1]),
                "ret_1d": last_ret, "sigma": sigma, "z": z, "fixed": fixed,
                "z_hit": z_hit, "pct_hit": pct_hit,
                "flagged": (z_hit or pct_hit),
                "direction": "▲" if last_ret > 0 else "▼",
                "lang": _lang_for(sym),
            })
        except Exception as e:
            alerts.append({"name": name, "symbol": sym, "error": str(e), "flagged": False})
    return alerts


def analyze_causes(alerts, today_str, model, max_tokens=1500):
    """
    FLAG된 자산들에 대해 뉴스 원인을 Claude가 분석.
    반환: {자산명: 원인분석텍스트} (뉴스 헤드라인도 함께 저장: key '_headlines')
    """
    flagged = [a for a in alerts if a.get("flagged")]
    if not flagged:
        return {}

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {a["name"]: "(API 키 없음 — 원인분석 생략)" for a in flagged}

    # 자산별 뉴스 수집
    blocks = []
    for a in flagged:
        items, _ = fetch_topic(a["name"], lang=a.get("lang", "en"), max_items=5, hours=48)
        heads = "\n".join(f"  - {it['title']} ({it['source']})" for it in items) or "  (관련 뉴스 못 찾음)"
        blocks.append(f"[{a['name']}] {a['direction']} {a['ret_1d']*100:+.2f}% (Z={a['z']:.2f})\n{heads}")

    sys_prompt = (
        "너는 CFA 애널리스트야. 아래는 오늘 임계치를 초과해 움직인 자산들과 관련 뉴스 헤드라인이야. "
        "각 자산이 왜 그렇게 움직였는지 뉴스 근거로 2~3문장, 반말로 분석해. "
        "반드시 이 형식으로: 각 자산마다 '### 자산명' 한 줄 헤더 뒤에 분석. "
        "뉴스에 뚜렷한 근거가 없으면 '뚜렷한 뉴스 원인 불명 — 수급/기술적 요인 가능성' 이라고 써. 사실을 지어내지 마."
    )
    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, system=sys_prompt,
            messages=[{"role": "user", "content": f"오늘: {today_str}\n\n" + "\n\n".join(blocks)}],
        )
        text = resp.content[0].text.strip()
    except Exception as e:
        return {a["name"]: f"(원인분석 실패: {type(e).__name__})" for a in flagged}

    # '### 자산명' 기준으로 잘라서 자산별로 매핑
    causes = {}
    names = [a["name"] for a in flagged]
    for chunk in text.split("### "):
        chunk = chunk.strip()
        if not chunk:
            continue
        first_line = chunk.split("\n", 1)[0].strip()
        body = chunk.split("\n", 1)[1].strip() if "\n" in chunk else ""
        # 헤더 이름과 가장 잘 맞는 자산에 매핑
        for nm in names:
            if nm in first_line or first_line in nm:
                causes[nm] = body or first_line
                break
    # 혹시 파싱 실패한 자산은 전체 텍스트라도 넣어줌
    for nm in names:
        causes.setdefault(nm, text)
    causes["_full"] = text
    return causes
