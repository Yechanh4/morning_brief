# -*- coding: utf-8 -*-
"""
🧠 심층 애널리스트 모듈.

계산된 정량지표(수익률·연변동성·샤프·MA체제·52주낙폭·상관관계) + FLAG + 뉴스를
opus에게 통째로 먹여서 '시니어 CFA 애널리스트 메모'를 생성한다.
(엑셀인 클로드가 하던 크로스에셋 인사이트를 매일 자동으로)

핵심 함수: generate_deep_analysis(tickers, alerts, causes, news_data, today, model)
"""

import os
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from dotenv import load_dotenv
import anthropic

from modules.excel_export import _download_prices

load_dotenv()
TD = 252
RF = 0.03


def compute_metrics(tickers, period="1y", include_today=True):
    """자산별 정량지표 + 상관관계 계산."""
    prices, failed = _download_prices(tickers, period=period, include_today=include_today)
    rets = prices.pct_change()
    out = {}
    for name in prices.columns:
        s = prices[name].dropna()
        r = rets[name].dropna()
        if len(s) < 30:
            continue

        def ret(k):
            return (s.iloc[-1] / s.iloc[-1 - k] - 1) if len(s) > k else None

        ma = lambda k: (s.tail(k).mean() if len(s) >= k else None)
        ann_vol = float(r.std() * np.sqrt(TD)) if len(r) > 2 else None
        ann_ret = float(r.mean() * TD) if len(r) > 2 else None
        sharpe = ((ann_ret - RF) / ann_vol) if (ann_vol and ann_vol > 0) else None
        ma20, ma60, ma200 = ma(20), ma(60), ma(200)
        last = float(s.iloc[-1])
        if ma20 and ma60 and ma200:
            if last > ma20 > ma60 > ma200:
                regime = "정배열(강세)"
            elif last < ma20 < ma60 < ma200:
                regime = "역배열(약세)"
            else:
                regime = "혼조"
        else:
            regime = "-"
        hi = float(s.tail(252).max())
        out[name] = {
            "last": last, "r1d": ret(1), "r1w": ret(5), "r1m": ret(21), "r3m": ret(63),
            "ann_vol": ann_vol, "ann_ret": ann_ret, "sharpe": sharpe,
            "vs_ma200": (last / ma200 - 1) if ma200 else None,
            "regime": regime, "dd_from_high": (last / hi - 1) if hi else None,
        }
    corr = rets.corr()
    return out, corr, failed


def _p(x):
    return f"{x*100:+.1f}%" if x is not None else "-"


def _metrics_text(metrics, corr):
    lines = ["자산 | 최신 | 1D | 1W | 1M | 3M | 연수익 | 연변동 | 샤프 | MA체제 | vsMA200 | 52주낙폭"]
    for n, m in metrics.items():
        sh = f"{m['sharpe']:.2f}" if m["sharpe"] is not None else "-"
        lines.append(
            f"{n} | {m['last']:,.1f} | {_p(m['r1d'])} | {_p(m['r1w'])} | {_p(m['r1m'])} | "
            f"{_p(m['r3m'])} | {_p(m['ann_ret'])} | {_p(m['ann_vol'])} | {sh} | {m['regime']} | "
            f"{_p(m['vs_ma200'])} | {_p(m['dd_from_high'])}"
        )
    # 주목할 상관관계 (절댓값 큰 쌍 Top)
    pairs = []
    cols = list(corr.columns)
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = corr.iloc[i, j]
            if pd.notna(v):
                pairs.append((abs(v), cols[i], cols[j], v))
    pairs.sort(reverse=True)
    ctext = "\n".join(f"{a} ↔ {b}: {v:+.2f}" for _, a, b, v in pairs[:10])
    return "\n".join(lines) + "\n\n[주요 상관관계 Top10]\n" + ctext


def _news_digest(news_data, per_cat=3):
    if not news_data or not news_data.get("results"):
        return "(뉴스 없음)"
    blocks = []
    for cat, items in news_data["results"].items():
        if not items:
            continue
        heads = "\n".join(f"  - {it['title']}" for it in items[:per_cat])
        blocks.append(f"[{cat}]\n{heads}")
    return "\n".join(blocks)


SYSTEM_PROMPT = """너는 예찬(케어마인더 co-founder, CFA L2 준비, IB/PE 지향)의 전담 시니어 매크로/멀티에셋 애널리스트야.
아래 정량지표(수익률·연환산변동성·샤프·MA체제·52주낙폭·상관관계) + 오늘 FLAG된 이상변동 + 뉴스 헤드라인을 통합해서
'데스크 애널리스트 아침 메모' 수준의 깊이 있는 분석을 반말로 써.

규칙:
- 데이터에 근거해서 구체적 숫자를 인용해. 뜬구름 금지. 없는 사실 지어내지 마.
- 통찰 위주로. "그래서 뭐?"에 답해. CFA 개념(위험조정성과, 상관/분산, 체제) 자연스럽게 활용.
- 아래 형식(마크다운)을 따르되 각 섹션 2~5줄로 밀도있게.

## 🧭 시장 체제 진단
- 리스크온/오프? VIX 수준·위치, 지수 정배열 여부로 판단. 한 문장 결론 + 근거.

## 🔀 디커플링 / 로테이션
- 한국 vs 미국, 섹터/개별 간 엇갈림. 누가 이끌고 누가 뒤쳐지나(수익률·MA체제·낙폭 근거).

## 📊 위험조정성과 (샤프)
- 샤프 기준 '위험 대비 보상' 좋은/나쁜 자산. rf 3% 미달 자산 지적. 포지셔닝 함의.

## 🔗 상관관계 · 분산/헤지
- 상관 데이터 기반 분산효과·헤지 아이디어(예: VIX/금 활용, 고상관 쌍 주의).

## 🚨 오늘 이상변동 심층 원인
- FLAG 자산을 정량(Z·낙폭)과 뉴스 원인을 엮어서 해석. 2차 파급 vs 통계적 이상치 구분.

## 🎯 오늘의 실전 포인트 3개
1~3. 위 분석에서 도출한 구체적 관전/행동 포인트 (투자/CFA/케어마인더 관점 섞어서)."""


def generate_deep_analysis(tickers, alerts, causes, news_data, today, model,
                           max_tokens=3200, include_today=True):
    """심층 애널리스트 메모(markdown) 생성. 반환: (텍스트, 에러 or None)"""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "API 키 없음"
    try:
        metrics, corr, _ = compute_metrics(tickers, include_today=include_today)
    except Exception as e:
        return None, f"지표계산 실패: {type(e).__name__}: {e}"
    if not metrics:
        return None, "지표 없음"

    flagged = [a for a in alerts if a.get("flagged")]
    flag_text = "\n".join(
        f"- {a['name']} {a['direction']} {a['ret_1d']*100:+.2f}% (Z={a['z']:.2f}) "
        f"원인: {causes.get(a['name'], '(분석없음)')}"
        for a in flagged
    ) or "- 오늘 임계치 초과 FLAG 없음"

    user = f"""오늘: {today}

=== 자산별 정량지표 ===
{_metrics_text(metrics, corr)}

=== 오늘 FLAG된 이상변동 ===
{flag_text}

=== 오늘 뉴스 헤드라인 ===
{_news_digest(news_data)}

위 데이터를 통합해 시니어 애널리스트 메모를 작성해줘."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=model, max_tokens=max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user}],
        )
        return resp.content[0].text.strip(), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
