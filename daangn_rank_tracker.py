# -*- coding: utf-8 -*-
"""
당근 노출순위 '주간 추적' 크롤러  (밤 자동 실행용 / API 전혀 안 씀)
────────────────────────────────────────────────────────────────
고정된 '추적 패널'(대표 지역 × 전체 카테고리)을 매주 다시 크롤해서,
같은 모임의 노출순위가 시간에 따라 어떻게 변하는지 누적 기록한다.
→ "무엇을 바꾸면 순위가 실제로 오르는가"(인과)를 검증하는 시계열 데이터.

기존 랭크 크롤러(daangn_rank_crawler.py)의 함수를 그대로 재사용한다
(import 해도 main 은 실행되지 않음 — __main__ 가드 있음).

출력: daangn_rank_tracking.xlsx  ('수집일자' 컬럼으로 매주 누적, 덮어쓰지 않고 append)
실행: python3 daangn_rank_tracker.py   (launchd 로 매주 자동 실행 권장)
"""
from __future__ import annotations
import asyncio, os, re, time, tempfile
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

import daangn_rank_crawler as rc   # 크롤 함수/지역/카테고리 재사용 (main 실행 안 됨)

# ── 주차별 파일명: 어플명_N월N주차_스크롤결과.xlsx (daangn 폴더에 저장) ──
def week_filename(app: str) -> str:
    now = datetime.now()
    week = (now.day - 1) // 7 + 1
    return f'{app}_{now.month}월{week}주차_스크롤결과.xlsx'

APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'daangn')
os.makedirs(APP_DIR, exist_ok=True)
TRACK_FILE = os.path.join(APP_DIR, week_filename('당근'))

# ── 추적 패널: 매주 동일하게 추적할 대표 지역 (전체 카테고리와 조합) ──
# 도시 규모가 다양하게 섞이도록 4곳. 필요하면 자유롭게 추가/삭제.
PANEL_REGIONS = [
    '서울 역삼동',   # 초대형 (강남)
    '경기 정자동',   # 대형 (분당)
    '부산 광안동',   # 지방 광역시
    '대전 둔산동',   # 중간 규모
]


def _save_week(new_rows: list):
    """이번 주 스냅샷을 주차 파일로 저장 (제어문자 제거 + 원자적 교체)."""
    df = pd.DataFrame(new_rows)
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
            os.replace(tmp, TRACK_FILE)
            return
        except Exception as e:
            try: os.remove(tmp)
            except OSError: pass
            print(f'  ⚠ 저장 실패({_try+1}/5): {str(e)[:80]} → 3초 후 재시도'); time.sleep(3)
    print('  ❌ 저장 5회 실패')


async def main():
    today = datetime.now().strftime('%Y-%m-%d')
    print(f'🌙 당근 노출순위 주간 추적 — {today}')
    print(f'   패널: {len(PANEL_REGIONS)}개 지역 × {len(rc.CATEGORIES)}개 카테고리\n')
    rows = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for rn in PANEL_REGIONS:
            rparam = rc.MAJOR_REGIONS.get(rn)
            if not rparam:
                print(f'  ⚠ 지역 미정의: {rn}'); continue
            for cid, cname in rc.CATEGORIES.items():
                url = f'{rc.BASE}?categoryId={cid}&{rparam}'
                tag = f'{rn}>{cname}'
                listing, real_region = await rc.crawl_listing(page, url, tag)
                n = len(listing)
                if n == 0:
                    continue
                print(f'[{tag[:26]:26s}] 실제:{real_region[:12]:12s} 노출 {n}개')
                for rank, item in enumerate(listing, 1):
                    detail = await rc.extract_with_retry(page, item['URL'])
                    rows.append({
                        '수집일자':       today,
                        '노출순위':       rank,
                        '스코프총수':     n,
                        '노출백분위':     round(rank / max(n, 1) * 100, 1),
                        '수집스코프':     tag,
                        '실제지역':       real_region,
                        '그룹ID':         item['그룹ID'],
                        '모임명':         item['모임명'],
                        '멤버수':         item['멤버수'],
                        '카테고리':       item['카테고리'],
                        '게시글수':       detail['게시글수'],
                        '일정수':         detail['일정수'],
                        '최근활동':       detail['최근활동'],
                        '최근활동_분':    detail['최근활동_분'],
                        '참여율_평균(%)': detail['참여율_평균'],
                        'URL':            item['URL'],
                    })
                    await page.wait_for_timeout(rc.DELAY_MS)
        await browser.close()

    _save_week(rows)
    print(f'\n✅ 추적 완료 ({today}): {len(rows):,}개 기록 → {TRACK_FILE}')


if __name__ == '__main__':
    asyncio.run(main())
