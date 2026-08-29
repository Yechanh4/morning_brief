# -*- coding: utf-8 -*-
"""
🤖 브리핑 생성 모듈 — 모은 시장/뉴스 데이터를 Claude에게 주고 브리핑을 받는다.

핵심 함수: generate_brief(market_data, news_data, today_str) -> (브리핑텍스트, 에러 or None)
"""

import os
import warnings
warnings.filterwarnings("ignore")

from dotenv import load_dotenv
import anthropic

from modules.market import format_price

load_dotenv()


def _market_to_text(market_data) -> str:
    """시장 데이터를 Claude가 읽기 좋은 텍스트로 변환."""
    if not market_data or not market_data.get("results"):
        return "(시장 데이터 없음)"
    lines = []
    for m in market_data["results"]:
        price = format_price(m["price"], m["unit"])
        sign = "+" if m["change_pct"] >= 0 else ""
        lines.append(f"- {m['name']}: {price} ({sign}{m['change_pct']:.2f}%)")
    return "\n".join(lines)


def _news_to_text(news_data) -> str:
    """뉴스 데이터를 카테고리별 텍스트로 변환."""
    if not news_data or not news_data.get("results"):
        return "(뉴스 없음)"
    blocks = []
    for category, items in news_data["results"].items():
        if not items:
            continue
        headlines = [f"  - {it['title']} ({it['source']})" for it in items]
        blocks.append(f"[{category}]\n" + "\n".join(headlines))
    return "\n\n".join(blocks)


def generate_brief(market_data, news_data, today_str: str):
    """
    Claude를 호출해서 브리핑 마크다운 텍스트를 생성.
    반환: (브리핑문자열, 에러메시지 or None)
    """
    from config import CLAUDE_MODEL, CLAUDE_MAX_TOKENS, BRIEF_INSTRUCTIONS

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None, "ANTHROPIC_API_KEY 없음"

    # 실패한 부분 요약 (브리핑에 참고용으로 알려줌)
    fail_notes = []
    if market_data and market_data.get("errors"):
        fail_notes.append(f"시장 수집 실패: {len(market_data['errors'])}건")
    if news_data and news_data.get("errors"):
        fail_notes.append(f"뉴스 수집 실패: {len(news_data['errors'])}건")
    fail_line = ("\n[수집 참고] " + ", ".join(fail_notes)) if fail_notes else ""

    # Claude에게 줄 데이터 묶음
    user_content = f"""오늘 날짜: {today_str}

=== 시장 데이터 ===
{_market_to_text(market_data)}

=== 오늘의 뉴스 헤드라인 ===
{_news_to_text(news_data)}
{fail_line}

위 데이터를 바탕으로 아침 브리핑을 작성해줘."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=CLAUDE_MAX_TOKENS,
            system=BRIEF_INSTRUCTIONS,
            messages=[{"role": "user", "content": user_content}],
        )
        text = resp.content[0].text.strip()
        return text, None

    except anthropic.AuthenticationError:
        return None, "인증 실패: ANTHROPIC_API_KEY 확인 필요"
    except anthropic.PermissionDeniedError:
        return None, "크레딧 부족 가능성: console.anthropic.com Billing 확인"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
