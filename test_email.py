# -*- coding: utf-8 -*-
"""
Gmail 앱 비밀번호로 '자기 자신에게' 테스트 메일이 가는지 확인.
실행: python test_email.py
성공하면 yechanh4@gmail.com 받은편지함에 테스트 메일이 도착해.
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate
from dotenv import load_dotenv

load_dotenv()
GMAIL = os.getenv("GMAIL_ADDRESS")
APP_PW = os.getenv("GMAIL_APP_PASSWORD")
TO = os.getenv("RECIPIENT_EMAIL")

# 값 검증
if not APP_PW or "앱비밀번호" in APP_PW or "16자리" in APP_PW:
    print("❌ .env에 GMAIL_APP_PASSWORD가 아직 안 채워졌어. 저장 명령 먼저 실행해줘.")
    sys.exit(1)

print(f"📤 보내는 사람: {GMAIL}")
print(f"📥 받는 사람:   {TO}")
print(f"🔑 앱비번 길이: {len(APP_PW)}글자 (정상: 16)")

# 메일 내용 구성
msg = MIMEText("이건 Morning Brief 이메일 테스트야.\n이 메일이 보이면 Gmail 발송 성공! 🎉", "plain", "utf-8")
msg["Subject"] = "✅ Morning Brief 이메일 테스트"
msg["From"] = GMAIL
msg["To"] = TO
msg["Date"] = formatdate(localtime=True)

try:
    # Gmail SSL 서버(465 포트)에 접속해서 로그인 후 전송
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as server:
        server.login(GMAIL, APP_PW)
        server.send_message(msg)
    print("✅ 발송 성공! Gmail 받은편지함(또는 스팸함)을 확인해봐.")
    print("🎉 Step 2-B 통과.")

except smtplib.SMTPAuthenticationError:
    print("❌ 로그인 실패: 앱 비밀번호가 틀렸어.")
    print("   → 16자리가 맞는지, 일반 Gmail 비번을 넣은 건 아닌지 확인.")
    print("   → myaccount.google.com/apppasswords 에서 새로 만들어 저장해봐.")
    sys.exit(1)
except Exception as e:
    print(f"❌ 에러: {type(e).__name__}: {e}")
    sys.exit(1)
