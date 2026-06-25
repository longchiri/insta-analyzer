# -*- coding: utf-8 -*-
"""
문토 '소셜링' 노출순위 주간 추적 크롤러  (밤 자동 실행용 / list API, 빠름)
────────────────────────────────────────────────────────────────
문토 크롤러(munto/문토_크롤러.py)의 collect_socialings_from_list() 재사용.
소셜링 노출 동력(좋아요·댓글·참가비/유료·승인제·참여수)을 list API로 한 번에 받아
매주 노출순위를 기록 → "별점·좋아요·유료 조정하면 순위 오르나" 인과 추적.

출력: munto/문토_소셜링_N월N주차_스크롤결과.xlsx
실행: python3 munto_socialing_tracker.py
"""
from __future__ import annotations
import os, re, sys, time, asyncio, tempfile, importlib.util
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

_BASE = os.path.dirname(os.path.abspath(__file__))
_MT_PATH = os.path.join(_BASE, 'munto', '문토_크롤러.py')
_spec = importlib.util.spec_from_file_location('munto_crawler', _MT_PATH)
mt = importlib.util.module_from_spec(_spec)
sys.modules['munto_crawler'] = mt
_spec.loader.exec_module(mt)


def week_filename(app: str) -> str:
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return f'{app}_{now.month}월{week}주차_스크롤결과.xlsx'

APP_DIR = os.path.join(_BASE, 'munto')
os.makedirs(APP_DIR, exist_ok=True)
TRACK_FILE = os.path.join(APP_DIR, week_filename('문토_소셜링'))


def _save_week(rows: list):
    df = pd.DataFrame(rows)
    if df.empty:
        print('수집된 행이 없습니다.'); return
    _ILLEGAL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: _ILLEGAL.sub('', v) if isinstance(v, str) else v)
    for _try in range(5):
        fd, tmp = tempfile.mkstemp(suffix='.xlsx', dir=APP_DIR); os.close(fd)
        try:
            with pd.ExcelWriter(tmp, engine='openpyxl') as w:
                df.to_excel(w, sheet_name='추적', index=False)
            os.replace(tmp, TRACK_FILE); return
        except Exception as e:
            try: os.remove(tmp)
            except OSError: pass
            print(f'  ⚠ 저장 실패({_try+1}/5): {str(e)[:80]}'); time.sleep(3)
    print('  ❌ 저장 5회 실패')


async def main():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f'🌙 문토 소셜링 노출순위 주간 추적 — {today}')

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=getattr(mt, 'HEADLESS', True))
        context = await browser.new_context(
            locale='ko-KR',
            user_agent=('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'),
            viewport={'width': 1280, 'height': 900},
        )
        page = await context.new_page()
        listed = await mt.collect_socialings_from_list(page)   # {sid: {노출순위, 좋아요수, ...}}
        await browser.close()

    rows = []
    for sid, rec in listed.items():
        r = dict(rec)
        r.setdefault('ID', sid)
        r['수집일자'] = today
        rows.append(r)

    _save_week(rows)
    print(f'\n✅ 추적 완료 ({today}): {len(rows):,}개 소셜링 → {TRACK_FILE}')


if __name__ == '__main__':
    asyncio.run(main())
