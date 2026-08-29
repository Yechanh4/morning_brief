# -*- coding: utf-8 -*-
"""시장 데이터 수집 테스트. 실행: python test_market.py"""
import warnings
warnings.filterwarnings("ignore")

from config import MARKET_TICKERS
from modules.market import fetch_all_market, format_price

print("💰 시장 데이터 수집 중... (10~20초)\n")
data = fetch_all_market(MARKET_TICKERS)

print("=" * 45)
for m in data["results"]:
    price = format_price(m["price"], m["unit"])
    sign = "+" if m["change_pct"] >= 0 else ""
    print(f"  {m['arrow']} {m['name']:<14} {price:>14}  ({sign}{m['change_pct']:.2f}%)")
print("=" * 45)

print(f"\n✅ {len(data['results'])}개 수집 완료")
if data["errors"]:
    print(f"⚠️ 실패 {len(data['errors'])}건:")
    for e in data["errors"]:
        print(f"   - {e}")
else:
    print("⚠️ 실패: 없음")
