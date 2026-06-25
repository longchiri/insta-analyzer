# -*- coding: utf-8 -*-
"""
문토 클럽 노출순위 '주간 추적' 크롤러  (상세 포함 / 밤 자동 실행용)
────────────────────────────────────────────────────────────────
기존 문토 크롤러(munto/문토_크롤러.py)의 함수를 재사용.
① collect_clubs_from_list() 로 전체 클럽을 '노출순위 순서'대로 받고
② parse_club() 으로 각 클럽의 소셜링·피드·최근대화(노출 핵심 동력)까지 보충.
→ "무엇을 바꾸면 순위가 오르나" 인과 추적용 시계열.

출력: munto/문토_N월N주차_스크롤결과.xlsx   (매주 새 파일, munto 폴더에 저장)
실행: python3 munto_tracker.py
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
TRACK_FILE = os.path.join(APP_DIR, week_filename('문토'))


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
    print(f'🌙 문토 클럽 노출순위 주간 추적 (상세 포함) — {today}')

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=getattr(mt, 'HEADLESS', True))
        context = await browser.new_context(
            locale='ko-KR',
            user_agent=('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36'),
            viewport={'width': 1280, 'height': 900},
        )
        page = await context.new_page()

        # ① 전체 클럽 노출순위 + 멤버·충족률 (list API, 빠름)
        listed = await mt.collect_clubs_from_list(page)
        cids = list(listed.keys())
        print(f'   목록 {len(cids)}개 — 이제 상세(소셜링·피드·최근대화) 보충\n')

        # ② 각 클럽 상세 보충 (노출 핵심 동력)
        rows = []
        for i, cid in enumerate(cids, 1):
            rec = dict(listed[cid]); rec['ID'] = cid; rec['수집일자'] = today
            try:
                detail = await mt.parse_club(page, cid)
                for k in ('카테고리', '지역(구)', '소셜링수', '피드수', '최근대화', '최근대화(분)'):
                    rec[k] = detail.get(k, '')
                if not rec.get('현재멤버'):
                    rec['현재멤버'] = detail.get('현재멤버', 0)
            except Exception as e:
                rec['상세오류'] = str(e)[:50]
            rows.append(rec)
            if i % 50 == 0:
                print(f'   상세 {i}/{len(cids)}')

        await browser.close()

    _save_week(rows)
    print(f'\n✅ 추적 완료 ({today}): {len(rows):,}개 클럽 → {TRACK_FILE}')


if __name__ == '__main__':
    asyncio.run(main())
