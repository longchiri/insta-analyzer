# -*- coding: utf-8 -*-
"""
소모임 노출순위 '주간 추적' 크롤러  (밤 자동 실행용 / API 기반, 빠름)
────────────────────────────────────────────────────────────────
기존 소모임 크롤러(somoim/소모임_크롤러.py)의 함수를 그대로 재사용.
고정 패널(대표 카테고리 × 대표 시/도)을 매주 다시 받아 노출순위를 누적 기록한다.

출력: 소모임_N월N주차_스크롤결과.xlsx   (매주 새 파일)
실행: python3 somoim_tracker.py
"""
from __future__ import annotations
import os, re, sys, time, asyncio, tempfile, importlib.util
from datetime import datetime
import requests
import pandas as pd

# ── 소모임 크롤러 모듈 import (main 실행 안 됨 — __main__ 가드 있음) ──
_SM_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'somoim', '소모임_크롤러.py')
_spec = importlib.util.spec_from_file_location('somoim_crawler', _SM_PATH)
sm = importlib.util.module_from_spec(_spec)
sys.modules['somoim_crawler'] = sm
_spec.loader.exec_module(sm)

# ── 추적 패널 (빈 리스트 = 전체 카테고리·전체 시/도 다 수집) ──
PANEL_CATEGORIES = []   # [] = 전체 18개 카테고리
PANEL_CITIES     = []   # [] = 전국 17개 시/도 전체


def week_filename(app: str) -> str:
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return f'{app}_{now.month}월{week}주차_스크롤결과.xlsx'

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'somoim')
os.makedirs(APP_DIR, exist_ok=True)
TRACK_FILE = os.path.join(APP_DIR, week_filename('소모임'))


def _save_week(rows: list):
    df = pd.DataFrame(rows)
    if df.empty:
        print('수집된 행이 없습니다.'); return
    _ILLEGAL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: _ILLEGAL.sub('', v) if isinstance(v, str) else v)
    _dir = os.path.dirname(os.path.abspath(TRACK_FILE)) or '.'
    for _try in range(5):
        fd, tmp = tempfile.mkstemp(suffix='.xlsx', dir=_dir); os.close(fd)
        try:
            with pd.ExcelWriter(tmp, engine='openpyxl') as w:
                df.to_excel(w, sheet_name='추적', index=False)
            os.replace(tmp, TRACK_FILE); return
        except Exception as e:
            try: os.remove(tmp)
            except OSError: pass
            print(f'  ⚠ 저장 실패({_try+1}/5): {str(e)[:80]}'); time.sleep(3)
    print('  ❌ 저장 5회 실패')


def main():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f'🌙 소모임 노출순위 주간 추적 — {today}')

    # 1) 카테고리/지역 코드 확보 (소모임 크롤러 함수 재사용)
    cat_codes = asyncio.run(sm.discover_category_codes())   # {카테고리명: it코드}
    if not cat_codes:
        print('❌ 카테고리 코드 수집 실패'); return
    first_it = next(iter(cat_codes.values()))
    reg_codes = sm.discover_region_codes(first_it)          # {시도명: loc코드}
    print(f'   카테고리 {len(cat_codes)} · 지역 {len(reg_codes)} 코드 확보')

    # 빈 패널이면 발견된 전체 카테고리/지역을 모두 사용
    cats_to_use   = PANEL_CATEGORIES if PANEL_CATEGORIES else list(cat_codes.keys())
    cities_to_use = PANEL_CITIES     if PANEL_CITIES     else list(reg_codes.keys())
    print(f'   수집 대상: 카테고리 {len(cats_to_use)} × 지역 {len(cities_to_use)} = {len(cats_to_use)*len(cities_to_use)} 조합')

    session = requests.Session()
    rows = []
    for cat in cats_to_use:
        it = cat_codes.get(cat)
        if not it:
            print(f'  ⚠ 카테고리 코드 없음: {cat}'); continue
        for city in cities_to_use:
            loc = reg_codes.get(city)
            if not loc:
                print(f'  ⚠ 지역 코드 없음: {city}'); continue
            try:
                collected = sm._collect_pass(session, it, loc, use_typ=True)
            except Exception as e:
                print(f'  ❌ {cat}×{city}: {str(e)[:60]}'); continue
            for item, rank in collected:
                r = sm.parse_group(item, cat, city, rank)
                r['수집일자'] = today
                r['노출백분위'] = round(rank / max(len(collected), 1) * 100, 1)
                rows.append(r)
            print(f'[{cat} × {city}] {len(collected)}개')

    _save_week(rows)
    print(f'\n✅ 추적 완료 ({today}): {len(rows):,}개 → {TRACK_FILE}')


if __name__ == '__main__':
    main()
