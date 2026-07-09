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
from datetime import datetime, date
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
    # 날짜(MMDD)를 붙여 같은 주에 여러 번 돌려도 덮어쓰지 않음
    return f'{app}_{now.month}월{week}주차_{now.strftime("%m%d")}_스크롤결과.xlsx'

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


def _is_net_err(msg):
    return any(k in str(msg) for k in ('Connection','timeout','Timeout','Max retries','NewConnection','Failed to establish','RemoteDisconnected','ConnectionError'))

def wait_for_internet():
    import urllib.request
    print('\n⚠️  인터넷 끊김 — 복구될 때까지 대기합니다.')
    n = 0
    while True:
        n += 1; time.sleep(10)
        try:
            urllib.request.urlopen('https://www.naver.com', timeout=8); print('✅ 연결 복구 — 이어서 진행'); return
        except Exception:
            if n % 3 == 0: print(f'   ({n}회째 대기 중... 복구되면 자동 재개)')


# ── 상세 페이지에서 '최근 활동일'(마지막 게시글 날짜) 수집 ──────────
#   소모임 노출의 진짜 동력 = 활동 최신성. 목록 API엔 없어서 상세(SSR HTML)를 긁는다.
#   상세 URL = https://www.somoim.co.kr/{id}  (저장 url 컬럼은 끝에 1이 더 붙어 깨져 있음)
_SM_BASE = 'https://www.somoim.co.kr'
_DATE_Y = re.compile(r'(20\d{2})년\s?(\d{1,2})월\s?(\d{1,2})일')
_DATE_N = re.compile(r'(?<!\d)(\d{1,2})월\s?(\d{1,2})일\s?(?:오전|오후)')

def _parse_last_activity(html: str, today: date):
    cands = []
    for y, m, d in _DATE_Y.findall(html):
        try: cands.append(date(int(y), int(m), int(d)))
        except ValueError: pass
    for m, d in _DATE_N.findall(html):
        try:
            dd = date(today.year, int(m), int(d))
            if dd > today:                      # 연도 없는데 미래면 작년 글
                dd = date(today.year - 1, int(m), int(d))
            cands.append(dd)
        except ValueError: pass
    cands = [c for c in cands if c <= today]     # 미래(예정 정모) 제외 = 실제 활동만
    return max(cands) if cands else None

def fetch_last_activity(session: requests.Session, gid: str, today: date):
    if not gid: return None
    url = f'{_SM_BASE}/{gid}'
    for _att in range(2):
        try:
            r = session.get(url, timeout=12)
            if r.status_code != 200: return None
            return _parse_last_activity(r.text, today)
        except Exception as e:
            if _att == 0 and _is_net_err(e):
                wait_for_internet(); continue
            return None
    return None


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
    session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.somoim.co.kr/'})
    rows = []
    _scope_n = 0
    for cat in cats_to_use:
        it = cat_codes.get(cat)
        if not it:
            print(f'  ⚠ 카테고리 코드 없음: {cat}'); continue
        for city in cities_to_use:
            loc = reg_codes.get(city)
            if not loc:
                print(f'  ⚠ 지역 코드 없음: {city}'); continue
            collected = None
            for _att in range(2):
                try:
                    collected = sm._collect_pass(session, it, loc, use_typ=True); break
                except Exception as e:
                    if _att == 0 and _is_net_err(e):
                        wait_for_internet(); continue
                    print(f'  ❌ {cat}×{city}: {str(e)[:60]}'); collected = []; break
            if not collected:
                continue
            for item, rank in collected:
                r = sm.parse_group(item, cat, city, rank)
                r['수집일자'] = today
                r['노출백분위'] = round(rank / max(len(collected), 1) * 100, 1)
                rows.append(r)
            print(f'[{cat} × {city}] {len(collected)}개')
            _scope_n += 1
            if _scope_n % 40 == 0:
                _save_week(rows); print(f'   💾 중간 저장 ({len(rows)}개)')

    _save_week(rows)
    print(f'   목록 수집 완료: {len(rows):,}개')

    # 2) 각 모임 상세에서 '최근 활동일' 수집 — 소모임 노출의 진짜 동력(활동 최신성)
    print(f'\n📅 최근 활동일 수집 시작 ({len(rows):,}개 모임 상세, 시간 걸려요)...')
    today_d = datetime.now().date()
    seen = {}
    for i, r in enumerate(rows, 1):
        gid = str(r.get('id', ''))
        if gid in seen:                          # 같은 모임이 여러 스코프에 있으면 재사용
            la = seen[gid]
        else:
            la = fetch_last_activity(session, gid, today_d)
            seen[gid] = la
            time.sleep(0.15)
        if la:
            r['최근활동일'] = la.strftime('%Y-%m-%d')
            r['최근활동_일'] = (today_d - la).days
        else:
            r['최근활동일'] = ''
            r['최근활동_일'] = ''
        if i % 100 == 0:
            print(f'   활동일 {i}/{len(rows)}')
            _save_week(rows)

    _save_week(rows)
    ok = sum(1 for r in rows if r.get('최근활동_일') != '')
    print(f'\n✅ 추적 완료 ({today}): {len(rows):,}개 (최근활동일 {ok}개 파싱) → {TRACK_FILE}')


if __name__ == '__main__':
    main()
