# -*- coding: utf-8 -*-
"""
Anthropic(Claude) API 키가 제대로 작동하는지 확인하는 테스트 스크립트.
실행: (venv 켠 상태에서)  python test_anthropic.py

이 테스트는 아주 짧은 질문 1개만 Claude한테 보내서 답이 오는지 확인해.
비용은 0.01원 수준(거의 공짜). 성공하면 키+크레딧 둘 다 정상이라는 뜻.
"""

import os
import sys
from dotenv import load_dotenv   # .env 파일에서 키를 읽어오는 도구

# 1) .env 파일 불러오기
load_dotenv()
api_key = os.getenv("ANTHROPIC_API_KEY")

# 2) 키가 비어있거나 아직 예시값이면 친절하게 알려주고 종료
if not api_key or "여기에" in api_key:
    print("❌ .env 파일에 ANTHROPIC_API_KEY가 아직 안 채워졌어.")
    print("   → 아래 명령으로 키를 저장한 뒤 다시 실행해:")
    print('   read -s "KEY?Anthropic 키 붙여넣고 Enter: " && echo "" && '
          'sed -i "" "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$KEY|" .env && '
          'echo 저장완료 && unset KEY')
    sys.exit(1)

print(f"🔑 키 감지됨: {api_key[:14]}...(뒷부분 숨김)")

# 3) 실제로 Claude를 호출해본다
try:
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    # 테스트용으로 제일 싼 모델(Haiku) 사용
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=20,
        messages=[{"role": "user", "content": "'테스트 성공'이라고만 답해줘."}],
    )
    answer = resp.content[0].text.strip()
    print(f"✅ Claude 응답: {answer}")
    print("🎉 Anthropic API 키 정상 작동! Step 2-A 통과.")

except anthropic.AuthenticationError:
    print("❌ 인증 실패: 키가 틀렸어. 복사할 때 앞뒤 공백이 섞였거나 키가 잘못됨.")
    print("   → console.anthropic.com 에서 키를 다시 만들어서 저장해봐.")
    sys.exit(1)
except anthropic.PermissionDeniedError:
    print("❌ 권한/크레딧 문제: 키는 맞는데 크레딧이 없을 수 있어.")
    print("   → console.anthropic.com → Billing 에서 크레딧을 충전해줘.")
    sys.exit(1)
except Exception as e:
    print(f"❌ 예상 못한 에러: {type(e).__name__}: {e}")
    sys.exit(1)
