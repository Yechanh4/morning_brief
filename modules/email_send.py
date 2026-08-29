# -*- coding: utf-8 -*-
"""
📧 이메일 발송 모듈 — 브리핑을 예쁜 HTML 이메일로 만들어 자기 자신에게 보낸다.

핵심 함수:
- build_html(...)  : 브리핑+시장데이터를 반응형 HTML로 조립
- send_email(...)  : Gmail SSL로 발송
"""

import os
import smtplib
import warnings
warnings.filterwarnings("ignore")
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate

import markdown as md
from dotenv import load_dotenv

from modules.market import format_price

load_dotenv()


def _session_ctx() -> str:
    """지금 국장/미장 세션 상태 한 줄 (실패해도 이메일은 나가게)."""
    try:
        from modules.quote import session_context
        return session_context()
    except Exception:
        return "정규장 종가"


def _market_rows_html(market_data) -> str:
    """시장 데이터를 색깔 있는 표 행(HTML)으로 변환. 상승=초록, 하락=빨강. USD자산은 원화환산 병기."""
    from modules.market import format_krw
    if not market_data or not market_data.get("results"):
        return '<tr><td style="padding:10px;color:#888;">시장 데이터 없음</td></tr>'
    rows = []
    for m in market_data["results"]:
        up = m["change_pct"] >= 0
        color = "#16a34a" if up else "#dc2626"        # 초록 / 빨강
        arrow = "▲" if up else "▼"
        sign = "+" if up else ""
        price = format_price(m["price"], m["unit"])
        # 원화 환산 (USD 자산만)
        krw = m.get("krw_price")
        krw_txt = f'<div style="font-size:11px;color:#888;">≈ {format_krw(krw)}</div>' if krw else ""
        live = ' <span style="font-size:10px;color:#f59e0b;">●LIVE</span>' if m.get("is_open") else ""
        rows.append(f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;font-size:14px;color:#333;">{m['name']}{live}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;font-size:14px;color:#111;text-align:right;font-weight:600;">{price}{krw_txt}</td>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;font-size:14px;color:{color};text-align:right;font-weight:600;white-space:nowrap;">{arrow} {sign}{m['change_pct']:.2f}%</td>
        </tr>""")
    return "".join(rows)


def _failure_banner_html(market_data, news_data) -> str:
    """수집 실패한 부분이 있으면 노란 경고 배너를 만든다."""
    notes = []
    if market_data and market_data.get("errors"):
        notes.append(f"시장 {len(market_data['errors'])}건")
    if news_data and news_data.get("errors"):
        notes.append(f"뉴스 {len(news_data['errors'])}건")
    if not notes:
        return ""
    return f"""
    <div style="margin:0 0 20px;padding:12px 16px;background:#fff7ed;border-left:4px solid #f59e0b;border-radius:6px;font-size:13px;color:#92400e;">
      ⚠️ 일부 데이터 수집 실패: {", ".join(notes)} — 나머지는 정상 반영됨.
    </div>"""


def _alerts_html(alerts, causes_text: str) -> str:
    """이상변동 알림 박스. FLAG 있으면 빨간 박스 + 원인분석, 없으면 초록 배너."""
    if not alerts:
        return ""
    flagged = [a for a in alerts if a.get("flagged")]
    if not flagged:
        return """
    <div style="margin:0 0 20px;padding:12px 16px;background:#ecfdf5;border-left:4px solid #10b981;border-radius:6px;font-size:14px;color:#065f46;">
      ✅ 오늘 임계치를 초과한 이상변동 없음 (전 자산 정상 범위)
    </div>"""
    rows = []
    for a in flagged:
        sign = "+" if a["ret_1d"] >= 0 else ""
        color = "#dc2626" if a["ret_1d"] >= 0 else "#2563eb"
        rows.append(f"""
        <tr>
          <td style="padding:6px 10px;font-size:13px;font-weight:700;">{a['direction']} {a['name']}</td>
          <td style="padding:6px 10px;font-size:13px;color:{color};font-weight:700;text-align:right;">{sign}{a['ret_1d']*100:.2f}%</td>
          <td style="padding:6px 10px;font-size:13px;text-align:right;">Z={a['z']:.2f}</td>
        </tr>""")
    cause_html = md.markdown(causes_text or "", extensions=["extra", "nl2br"]) if causes_text else ""
    return f"""
    <div style="margin:0 0 22px;padding:16px;background:#fef2f2;border:1px solid #fecaca;border-radius:10px;">
      <div style="font-size:16px;font-weight:800;color:#b91c1c;margin-bottom:10px;">🚨 오늘 이상변동 {len(flagged)}건</div>
      <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:6px;">{''.join(rows)}</table>
      <div style="margin-top:12px;font-size:14px;line-height:1.65;color:#333;">{cause_html}</div>
    </div>"""


def build_html(brief_markdown: str, market_data, news_data, today_str: str,
               alerts=None, causes_text: str = "", analysis_text: str = "") -> str:
    """전체 이메일 HTML을 조립해서 문자열로 반환."""
    # 브리핑 마크다운 → HTML 변환
    brief_html = md.markdown(brief_markdown, extensions=["extra", "nl2br", "sane_lists"])
    market_rows = _market_rows_html(market_data)
    fail_banner = _failure_banner_html(market_data, news_data)
    alerts_box = _alerts_html(alerts, causes_text)

    # 심층 애널리스트 분석 박스
    analysis_box = ""
    if analysis_text:
        analysis_html = md.markdown(analysis_text, extensions=["extra", "nl2br", "sane_lists"])
        analysis_box = f"""
    <div style="margin:0 0 22px;padding:18px;background:#f5f3ff;border:1px solid #ddd6fe;border-radius:10px;">
      <div style="font-size:17px;font-weight:800;color:#5b21b6;margin-bottom:8px;">🧠 심층 애널리스트 분석</div>
      <div style="font-size:14px;line-height:1.7;color:#222;">{analysis_html}</div>
    </div>"""

    # 이메일 클라이언트 호환을 위해 인라인 스타일 위주로 작성
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Apple SD Gothic Neo',sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:16px;">

  <!-- 헤더 (그라데이션) -->
  <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:14px;padding:28px 24px;text-align:center;">
    <div style="font-size:26px;font-weight:700;color:#ffffff;">☀️ 예찬's Morning Brief</div>
    <div style="font-size:14px;color:#e0e7ff;margin-top:6px;">{today_str}</div>
  </div>

  <!-- 본문 카드 -->
  <div style="background:#ffffff;border-radius:14px;padding:24px;margin-top:16px;box-shadow:0 1px 3px rgba(0,0,0,0.08);">

    {fail_banner}
    {alerts_box}
    {analysis_box}

    <!-- 시장 데이터 표 -->
    <div style="font-size:16px;font-weight:700;color:#111;margin:0 0 4px;">📊 마켓 스냅샷 <span style="font-size:11px;font-weight:400;color:#888;">(정규장 종가 기준)</span></div>
    <div style="font-size:11px;color:#888;margin:0 0 12px;">{_session_ctx()} · 적용환율 USD/KRW {(f"{market_data.get('krw_rate'):,.1f}원" if market_data and market_data.get('krw_rate') else "-")}</div>
    <table style="width:100%;border-collapse:collapse;background:#fafafa;border-radius:8px;overflow:hidden;">
      {market_rows}
    </table>

    <!-- 브리핑 본문 -->
    <div style="margin-top:24px;font-size:15px;line-height:1.7;color:#222;">
      {brief_html}
    </div>
  </div>

  <!-- 푸터 -->
  <div style="text-align:center;padding:18px 10px;color:#9ca3af;font-size:12px;">
    자동 생성된 브리핑 · Morning Brief 시스템
  </div>

</div>
</body>
</html>"""


def send_email(subject: str, html_body: str, attachment_path: str = None):
    """
    HTML 이메일을 Gmail로 발송. attachment_path 주면 파일 첨부(예: Excel).
    반환: (성공여부 bool, 에러메시지 or None)
    """
    gmail = os.getenv("GMAIL_ADDRESS")
    app_pw = os.getenv("GMAIL_APP_PASSWORD")
    to = os.getenv("RECIPIENT_EMAIL") or gmail

    if not app_pw:
        return False, "GMAIL_APP_PASSWORD 없음"

    # 첨부가 있으면 mixed, 없으면 alternative
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = gmail
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)

    # 본문 (텍스트 대체본 + HTML본)
    body = MIMEMultipart("alternative")
    body.attach(MIMEText("HTML 이메일이야. HTML 보기를 지원하는 앱에서 열어줘.", "plain", "utf-8"))
    body.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(body)

    # 파일 첨부 (있고, 실제로 존재할 때만)
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application",
                            "vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        fname = os.path.basename(attachment_path)
        part.add_header("Content-Disposition", f'attachment; filename="{fname}"')
        msg.attach(part)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(gmail, app_pw)
            server.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, "Gmail 로그인 실패: 앱 비밀번호 확인"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
