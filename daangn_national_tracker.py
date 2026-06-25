# -*- coding: utf-8 -*-
"""
당근 '전국' 노출순위 월간 크롤러  (밤 자동 실행 / 중간저장 + 이어하기)
────────────────────────────────────────────────────────────────
전국 57개 지역 × 12 카테고리를 매달 한 번 전부 크롤한다.
한 번에 ~28시간이라 한 밤에 못 끝나므로:
  · 월별 진행파일 + 체크포인트(방문 스코프)로 **중간저장 + 이어하기**
  · 매일 밤 자동 실행 → 남은 스코프만 이어받음 → 여러 밤에 걸쳐 그 달 스냅샷 완성
  · 그 달 다 끝나면 idle(아무것도 안 함), 다음 달이 되면 새 스냅샷 시작

기존 랭크 크롤러(daangn_rank_crawler.py)의 크롤 함수를 그대로 재사용.

출력: daangn/당근_전국_N월N주차_스크롤결과.xlsx   (그 달 완성 시점)
진행: daangn/당근_전국_YYYY-MM_진행.xlsx + _체크포인트.json
실행: python3 daangn_national_tracker.py   (launchd 로 매일 자동 권장)
"""
from __future__ import annotations
import os, re, sys, json, time, asyncio, tempfile, importlib.util
from datetime import datetime
import pandas as pd
from playwright.async_api import async_playwright

_BASE = os.path.dirname(os.path.abspath(__file__))
_RC_PATH = os.path.join(_BASE, 'daangn_rank_crawler.py')
_spec = importlib.util.spec_from_file_location('daangn_rank_crawler', _RC_PATH)
rc = importlib.util.module_from_spec(_spec)
sys.modules['daangn_rank_crawler'] = rc
_spec.loader.exec_module(rc)

APP_DIR = os.path.join(_BASE, 'daangn')
os.makedirs(APP_DIR, exist_ok=True)
SAVE_EVERY = 50

_now = datetime.now()
MONTH_TAG = _now.strftime('%Y-%m')
WEEK = (_now.day - 1) // 7 + 1
PROG_FILE  = os.path.join(APP_DIR, f'당근_전국_{MONTH_TAG}_진행.xlsx')
CKPT_FILE  = os.path.join(APP_DIR, f'당근_전국_{MONTH_TAG}_체크포인트.json')
FINAL_FILE = os.path.join(APP_DIR, f'당근_전국_{_now.month}월{WEEK}주차_스크롤결과.xlsx')


def _load():
    rows, visited = [], set()
    if os.path.exists(CKPT_FILE):
        try:
            visited = set(json.load(open(CKPT_FILE, encoding='utf-8')).get('visited', []))
        except Exception:
            visited = set()
    if os.path.exists(PROG_FILE):
        try:
            rows = pd.read_excel(PROG_FILE, sheet_name='노출순위_전체').to_dict('records')
        except Exception:
            rows = []
    return rows, visited


def _save(rows, visited, path):
    df = pd.DataFrame(rows)
    if df.empty:
        return
    for c in ['노출순위', '스코프총수', '게시글수', '일정수', '멤버수', '참여율_평균(%)']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    if '최근활동_분' in df.columns:
        df['최근활동_분'] = pd.to_numeric(df['최근활동_분'], errors='coerce')
    _ILL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
    for c in df.columns:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: _ILL.sub('', v) if isinstance(v, str) else v)
    for _t in range(5):
        fd, tmp = tempfile.mkstemp(suffix='.xlsx', dir=APP_DIR); os.close(fd)
        try:
            with pd.ExcelWriter(tmp, engine='openpyxl') as w:
                df.sort_values(['수집스코프', '노출순위']).to_excel(w, sheet_name='노출순위_전체', index=False)
            os.replace(tmp, path)
            break
        except Exception as e:
            try: os.remove(tmp)
            except OSError: pass
            print(f'  ⚠ 저장 실패({_t+1}/5): {str(e)[:70]}'); time.sleep(3)
    json.dump({'visited': sorted(visited), 'saved_at': datetime.now().strftime('%Y-%m-%d %H:%M')},
              open(CKPT_FILE, 'w', encoding='utf-8'), ensure_ascii=False)


async def main():
    today = datetime.now().strftime('%Y-%m-%d')
    scopes = [(rn, rp, cid, cn)
              for rn, rp in rc.MAJOR_REGIONS.items()
              for cid, cn in rc.CATEGORIES.items()]
    rows, visited = _load()
    done_ids = set(str(r.get('그룹ID', '')) for r in rows)
    remaining = [s for s in scopes if f'{s[0]}>{s[3]}' not in visited]

    print(f'🌙 당근 전국 월간 크롤 [{MONTH_TAG}] — {today}')
    print(f'   전체 {len(scopes)} 스코프 | 완료 {len(visited)} | 남은 {len(remaining)} | 수집 {len(rows):,}개')

    if not remaining:
        print('✅ 이번 달 전국 크롤 이미 완료 — 할 일 없음.')
        if not os.path.exists(FINAL_FILE) and rows:
            _save(rows, visited, FINAL_FILE)
            print(f'💾 최종 스냅샷 저장: {FINAL_FILE}')
        return

    processed = 0
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for si, (rn, rp, cid, cn) in enumerate(remaining, 1):
            tag = f'{rn}>{cn}'
            url = f'{rc.BASE}?categoryId={cid}&{rp}'
            listing, real_region = await rc.crawl_listing(page, url, tag)
            n = len(listing)
            visited.add(tag)
            if n == 0:
                continue
            print(f'[{si}/{len(remaining)}] {tag[:24]:24s} 실제:{real_region[:12]:12s} 노출 {n}개')
            for rank, item in enumerate(listing, 1):
                gid = str(item['그룹ID'])
                if gid in done_ids:
                    continue
                d = await rc.extract_with_retry(page, item['URL'])
                rows.append({
                    '노출순위': rank, '스코프총수': n, '노출백분위': round(rank/max(n,1)*100,1),
                    '수집스코프': tag, '실제지역': real_region, '그룹ID': gid,
                    '모임명': item['모임명'], '멤버수': item['멤버수'], '카테고리': item['카테고리'],
                    '위치': item['위치'], '소개': d['소개'], '게시글수': d['게시글수'], '일정수': d['일정수'],
                    '최근활동': d['최근활동'], '최근활동_분': d['최근활동_분'],
                    '참여율_평균(%)': d['참여율_평균'], '참여율_최고(%)': d['참여율_최고'],
                    '게시판카테고리수': d['게시판카테고리수'], '챌린지여부': 1 if d['챌린지여부'] else 0,
                    'URL': item['URL'], '수집일자': today,
                })
                done_ids.add(gid); processed += 1
                if processed % SAVE_EVERY == 0:
                    _save(rows, visited, PROG_FILE)
                    print(f'  💾 중간저장 (수집 {len(rows):,}개 / 스코프 {si}/{len(remaining)})')
                await page.wait_for_timeout(rc.DELAY_MS)
            _save(rows, visited, PROG_FILE)   # 스코프 끝날 때마다 저장
        await browser.close()

    _save(rows, visited, PROG_FILE)
    # 전체 스코프 다 방문했으면 최종 스냅샷 확정
    if len([s for s in scopes if f'{s[0]}>{s[3]}' not in visited]) == 0:
        _save(rows, visited, FINAL_FILE)
        print(f'\n🎉 {MONTH_TAG} 전국 완료! 최종: {FINAL_FILE} ({len(rows):,}개)')
    else:
        print(f'\n⏸  이번 밤 종료 — 다음 실행 때 이어서 (수집 {len(rows):,}개)')


if __name__ == '__main__':
    asyncio.run(main())
