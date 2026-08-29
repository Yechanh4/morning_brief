# -*- coding: utf-8 -*-
"""
📰 뉴스 수집 모듈 — Google 뉴스 RSS에서 주제별 최신 기사를 긁어온다.

핵심 함수: fetch_all_news(topics) -> dict
- API 키 필요 없음
- 한 주제(피드)가 실패해도 나머지는 계속 진행 (에러 격리)
- 반환값에 성공 기사 + 실패 목록을 함께 담아서, 이메일에 "이 부분 실패" 표시 가능
"""

import time
import urllib.parse
from datetime import datetime, timezone, timedelta

import feedparser

# 브라우저인 척하는 신분증(User-Agent). 없으면 가끔 Google이 막음.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def _build_url(query: str, lang: str) -> str:
    """검색어 + 언어에 맞는 Google 뉴스 RSS 주소를 만든다."""
    q = urllib.parse.quote(query)
    if lang == "en":
        return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    # 기본값: 한국어
    return f"https://news.google.com/rss/search?q={q}&hl=ko&gl=KR&ceid=KR:ko"


def _entry_datetime(entry):
    """기사 발행 시각을 UTC datetime으로 변환 (없으면 None)."""
    parsed = getattr(entry, "published_parsed", None)
    if not parsed:
        return None
    return datetime.fromtimestamp(time.mktime(parsed), tz=timezone.utc)


def _clean_title(title: str):
    """
    Google 뉴스 제목은 보통 '제목 - 언론사' 형태.
    제목과 언론사를 분리해서 돌려준다.
    """
    if " - " in title:
        head, _, tail = title.rpartition(" - ")
        return head.strip(), tail.strip()
    return title.strip(), ""


def fetch_topic(query: str, lang: str = "ko", max_items: int = 4, hours: int = 48):
    """
    검색어 하나에 대한 기사 리스트를 가져온다.
    반환: (기사리스트, 에러메시지 or None)
    """
    url = _build_url(query, lang)
    try:
        feed = feedparser.parse(url, agent=_USER_AGENT)

        # feedparser는 예외를 안 던지고 bozo 플래그로 파싱 오류를 알려줌
        if feed.bozo and not feed.entries:
            return [], f"피드 파싱 실패({type(feed.bozo_exception).__name__})"

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        items = []
        for e in feed.entries:
            dt = _entry_datetime(e)
            # 발행시각이 있고 너무 오래됐으면 건너뜀
            if dt and dt < cutoff:
                continue

            title, src_from_title = _clean_title(getattr(e, "title", ""))
            # 언론사 이름: source 태그 우선, 없으면 제목에서 뽑은 것
            source = ""
            if getattr(e, "source", None):
                source = e.source.get("title", "") or ""
            source = source or src_from_title

            items.append({
                "title": title,
                "source": source,
                "link": getattr(e, "link", ""),
                "published": dt.astimezone().strftime("%m/%d %H:%M") if dt else "",
                "published_dt": dt,
            })
            if len(items) >= max_items:
                break

        return items, None

    except Exception as e:
        return [], f"{type(e).__name__}: {e}"


def fetch_all_news(topics):
    """
    config.py의 NEWS_TOPICS 전체를 돌면서 뉴스를 수집한다.

    반환 dict:
    {
      "results": { "카테고리명": [기사, ...], ... },
      "errors":  [ "카테고리 · 키워드: 에러내용", ... ],
      "total":   전체 기사 수(중복 제거 후),
    }
    """
    from config import NEWS_MAX_PER_QUERY, NEWS_LOOKBACK_HOURS

    results = {}
    errors = []
    seen_titles = set()   # 중복 기사 제거용
    total = 0

    for topic in topics:
        category = topic["category"]
        lang = topic.get("lang", "ko")
        results[category] = []

        for query in topic["queries"]:
            items, err = fetch_topic(
                query, lang=lang,
                max_items=NEWS_MAX_PER_QUERY,
                hours=NEWS_LOOKBACK_HOURS,
            )
            if err:
                errors.append(f"{category} · '{query}': {err}")
                continue

            for it in items:
                # 제목 앞부분으로 중복 판단 (같은 뉴스 여러 키워드에 걸리는 것 방지)
                key = it["title"][:40]
                if key in seen_titles:
                    continue
                seen_titles.add(key)
                results[category].append(it)
                total += 1

    return {"results": results, "errors": errors, "total": total}
