# -*- coding: utf-8 -*-
"""
☀️ Morning Brief 메인 실행 파일.
실행: python main.py

흐름: 뉴스 수집 → 시장 수집 → Claude 브리핑 → 이메일 발송
- 각 단계는 에러가 나도 다음 단계로 진행 (하나 실패 ≠ 전체 실패)
- 모든 과정은 logs/ 폴더에 날짜별 로그로 저장
"""

import os
import sys
import logging
import warnings
warnings.filterwarnings("ignore")
from datetime import datetime

# 프로젝트 폴더를 기준으로 경로 잡기 (launchd에서 실행돼도 문제없게)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from config import NEWS_TOPICS, MARKET_TICKERS
from modules.news import fetch_all_news
from modules.market import fetch_all_market
from modules.brief import generate_brief
from modules.email_send import build_html, send_email
from modules.excel_export import build_analysis_workbook
from modules.alerts import compute_alerts, analyze_causes
from modules.analyst import generate_deep_analysis
from config import (ALERT_SIGMA_WINDOW, ALERT_Z_MULT, ALERT_PCT_INDEX,
                    ALERT_PCT_STOCK, CLAUDE_MODEL)


# ---------- 로그 설정 ----------
def setup_logging():
    log_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, datetime.now().strftime("%Y-%m-%d") + ".log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),  # 파일에 기록
            logging.StreamHandler(),                          # 화면에도 출력
        ],
    )
    return logging.getLogger("morning_brief")


def main():
    log = setup_logging()
    today = datetime.now().strftime("%Y년 %m월 %d일 (%a)")
    log.info("=" * 50)
    log.info(f"☀️ Morning Brief 시작 — {today}")

    # 1) 뉴스 수집
    try:
        news = fetch_all_news(NEWS_TOPICS)
        log.info(f"📰 뉴스: {news['total']}건 수집 (실패 {len(news['errors'])}건)")
        for e in news["errors"]:
            log.warning(f"   뉴스실패: {e}")
    except Exception as e:
        log.error(f"📰 뉴스 모듈 전체 실패: {e}")
        news = {"results": {}, "errors": [str(e)], "total": 0}

    # 2) 시장 수집
    try:
        market = fetch_all_market(MARKET_TICKERS)
        log.info(f"💰 시장: {len(market['results'])}개 수집 (실패 {len(market['errors'])}건)")
        for e in market["errors"]:
            log.warning(f"   시장실패: {e}")
    except Exception as e:
        log.error(f"💰 시장 모듈 전체 실패: {e}")
        market = {"results": [], "errors": [str(e)]}

    # 2.3) 이상변동 판정 + FLAG 자산 뉴스 원인분석
    alerts, causes = [], {}
    try:
        alerts = compute_alerts(MARKET_TICKERS, sigma_window=ALERT_SIGMA_WINDOW,
                                z_mult=ALERT_Z_MULT, pct_index=ALERT_PCT_INDEX,
                                pct_stock=ALERT_PCT_STOCK)
        flagged = [a for a in alerts if a.get("flagged")]
        log.info(f"🚨 알림: {len(flagged)}건 FLAG" +
                 (f" ({', '.join(a['name'] for a in flagged)})" if flagged else ""))
        if flagged:
            causes = analyze_causes(alerts, today, CLAUDE_MODEL)
            log.info("🚨 FLAG 자산 원인분석 완료")
    except Exception as e:
        log.error(f"🚨 알림 모듈 실패: {e}")

    # 2.4) 심층 애널리스트 분석 (정량지표 + FLAG + 뉴스 통합)
    analysis_text = ""
    try:
        analysis_text, aerr = generate_deep_analysis(
            MARKET_TICKERS, alerts, causes, news, today, CLAUDE_MODEL)
        if analysis_text:
            log.info("🧠 심층 애널리스트 분석 생성 성공")
        else:
            log.error(f"🧠 심층 분석 실패: {aerr}")
            analysis_text = ""
    except Exception as e:
        log.error(f"🧠 심층 분석 모듈 실패: {e}")

    # 2.5) Excel 분석 워크북 생성 (실패해도 나머지 진행)
    excel_path = None
    try:
        excel_path, xerr = build_analysis_workbook(
            MARKET_TICKERS, alerts=alerts, causes=causes, analysis_text=analysis_text)
        if excel_path:
            log.info(f"📊 Excel 워크북 생성 성공{' (참고: ' + xerr + ')' if xerr else ''}")
        else:
            log.error(f"📊 Excel 워크북 생성 실패: {xerr}")
    except Exception as e:
        log.error(f"📊 Excel 모듈 전체 실패: {e}")

    # 3) Claude 브리핑 생성
    brief, err = generate_brief(market, news, today)
    if err:
        log.error(f"🤖 브리핑 생성 실패: {err}")
        # 브리핑 실패해도 최소한 데이터라도 보내도록 대체 텍스트
        brief = f"## ⚠️ 브리핑 생성 실패\n- 이유: {err}\n- 아래 마켓 데이터는 정상 수집됨."
    else:
        log.info("🤖 브리핑 생성 성공")

    # 4) 이메일 발송
    try:
        subject = f"☀️ Morning Brief · {datetime.now().strftime('%m/%d')}"
        html = build_html(brief, market, news, today,
                          alerts=alerts, causes_text=causes.get("_full", ""),
                          analysis_text=analysis_text)
        ok, mail_err = send_email(subject, html, attachment_path=excel_path)
        if ok:
            log.info("📧 이메일 발송 성공")
        else:
            log.error(f"📧 이메일 발송 실패: {mail_err}")
    except Exception as e:
        log.error(f"📧 이메일 모듈 전체 실패: {e}")

    # 5) 완료된 Excel 파일을 화면에 자동으로 열기 (Mac 켜져 있을 때)
    if excel_path:
        try:
            import subprocess
            subprocess.run(["open", excel_path], check=False)
            log.info("📂 Excel 파일 자동 열기")
        except Exception as e:
            log.warning(f"📂 자동 열기 실패(무시 가능): {e}")

    log.info("✅ Morning Brief 종료")
    log.info("=" * 50)


if __name__ == "__main__":
    main()
