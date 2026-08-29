#!/bin/bash
# Morning Brief 환경 세팅 (동료 Mac용) — 압축 푼 폴더 안에서 실행: bash setup.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "=== 1) Python 가상환경 생성 ==="
/usr/bin/python3 -m venv venv

echo "=== 2) 패키지 설치 (1~3분) ==="
./venv/bin/python -m pip install --quiet --upgrade pip
./venv/bin/pip install -r requirements.txt

echo "=== 3) .env 준비 ==="
[ -f .env ] || cp .env.example .env
mkdir -p logs credentials

echo ""
echo "✅ 세팅 완료!"
echo "다음: .env 파일을 열어서 본인 API 키를 채워 → open -e \"$DIR/.env\""
echo "  - ANTHROPIC_API_KEY (console.anthropic.com)"
echo "  - GMAIL_ADDRESS / GMAIL_APP_PASSWORD (본인 Gmail 앱 비밀번호)"
echo "  - RECIPIENT_EMAIL (받을 이메일)"
echo "그다음 테스트:  ./venv/bin/python main.py"
