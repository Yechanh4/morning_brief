# -*- coding: utf-8 -*-
"""
전체 재료(시장+뉴스) 모아서 Claude 브리핑 생성 테스트.
실행: python test_brief.py
비용: opus 기준 약 몇십 원. 실제 오늘 데이터로 브리핑을 만들어 화면에 출력.
"""
import warnings
warnings.filterwarnings("ignore")

from datetime import datetime

from config import NEWS_TOPICS, MARKET_TICKERS
from modules.news import fetch_all_news
from modules.market import fetch_all_market
from modules.brief import generate_brief

today = datetime.now().strftime("%Y년 %m월 %d일 (%a)")

print("1/3 📰 뉴스 수집 중...")
news = fetch_all_news(NEWS_TOPICS)
print(f"    → {news['total']}건 (실패 {len(news['errors'])})")

print("2/3 💰 시장 수집 중...")
market = fetch_all_market(MARKET_TICKERS)
print(f"    → {len(market['results'])}개 (실패 {len(market['errors'])})")

print("3/3 🤖 Claude 브리핑 생성 중... (20~40초)\n")
brief, err = generate_brief(market, news, today)

if err:
    print(f"❌ 브리핑 생성 실패: {err}")
else:
    print("=" * 60)
    print(f"📬 {today} 모닝 브리핑")
    print("=" * 60)
    print(brief)
    print("=" * 60)
    print("\n🎉 브리핑 생성 성공!")
