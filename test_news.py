# -*- coding: utf-8 -*-
"""
뉴스 수집이 잘 되는지 확인. 실행: python test_news.py
config.py의 주제들로 실제 뉴스를 긁어와서 화면에 예쁘게 출력한다.
"""
import warnings
warnings.filterwarnings("ignore")  # 무해한 경고 숨김

from config import NEWS_TOPICS
from modules.news import fetch_all_news

print("📰 뉴스 수집 중... (10~30초 걸려)\n")
data = fetch_all_news(NEWS_TOPICS)

for category, items in data["results"].items():
    print("=" * 55)
    print(f"{category}  ({len(items)}건)")
    print("=" * 55)
    if not items:
        print("  (수집된 기사 없음)")
    for it in items:
        src = f" · {it['source']}" if it["source"] else ""
        when = f" [{it['published']}]" if it["published"] else ""
        print(f"  • {it['title']}{src}{when}")
    print()

print("=" * 55)
print(f"✅ 총 {data['total']}건 수집 완료")
if data["errors"]:
    print(f"⚠️ 실패 {len(data['errors'])}건:")
    for e in data["errors"]:
        print(f"   - {e}")
else:
    print("⚠️ 실패: 없음")
