# -*- coding: utf-8 -*-
"""Excel 분석 워크북 생성 테스트. 실행: python test_excel.py"""
import warnings
warnings.filterwarnings("ignore")

from config import MARKET_TICKERS
from modules.excel_export import build_analysis_workbook, DEFAULT_PATH

print("📊 2년치 데이터 받아서 Excel 워크북 생성 중... (20~40초)\n")
path, err = build_analysis_workbook(MARKET_TICKERS)

if path:
    import os
    size_kb = os.path.getsize(path) / 1024
    print(f"✅ 생성 완료: {path}")
    print(f"   파일 크기: {size_kb:.0f} KB")
    print(f"   시트: Analysis / Prices / Returns / Correlation / 검증(Python)")
    if err:
        print(f"⚠️ 참고: {err}")
    print("\n👉 Excel로 열어서 Analysis 시트 확인 → '검증(Python)' 시트 값과 대조해봐.")
else:
    print(f"❌ 생성 실패: {err}")
