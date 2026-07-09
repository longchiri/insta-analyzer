# -*- coding: utf-8 -*-
"""
순위 추적 대시보드 생성기
────────────────────────────────────────────────────────────
trackers 가 매주 떨어뜨린 'N월N주차_스크롤결과.xlsx' 들을 모아
모임/클럽/소셜링의 노출순위 변화를 HTML 대시보드로 만든다.

· 1주차만 있으면 → 현재 순위표(스냅샷)
· 2주차 이상이면 → 급상승/급하락 + 순위 변화 라인차트

실행: python3 추적_대시보드.py   →  추적_대시보드.html 생성 (브라우저로 열기)
"""
import os, re, glob, json, unicodedata
from datetime import datetime
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))

# (표시이름, 폴더, 파일 glob, 제외 glob)
# (표시이름, 폴더, glob, 제외, noisy_rank) — noisy_rank=True면 순위가 셔플 노이즈라 '활동 최신성' 뷰로 대체
DATASETS = [
    ('🥕 당근 모임',   '',       '당근_노출순위_*.xlsx',              '분석리포트', False),  # rank 크롤러 출력(루트)
    ('🌿 소모임',      'somoim', '소모임_*주차*_스크롤결과.xlsx',     None,        True),   # 순위=셔플 → 활동뷰
    ('🔥 문토 클럽',   'munto',  '문토_*주차*_스크롤결과.xlsx',       '소셜링',    False),
    ('🎉 문토 소셜링', 'munto',  '문토_소셜링_*주차*_스크롤결과.xlsx', None,        True),
]

def _norm(df):
    df.columns = [unicodedata.normalize('NFC', str(c)) for c in df.columns]
    return df

def _pick(cols, *cands):
    for c in cands:
        if c in cols: return c
    return None

def _date_in(fname):
    d = re.search(r'_(\d{2})(\d{2})_스크롤결과', fname)      # 주차 파일: ..._MMDD_스크롤결과
    if d: return (int(d.group(1)), int(d.group(2)))
    d = re.search(r'_(20\d{2})(\d{2})(\d{2})[_.]', fname)     # 당근 rank: ..._YYYYMMDD_
    if d: return (int(d.group(2)), int(d.group(3)))
    return None

def week_key(fname):
    dt = _date_in(fname)          # 파일명에 날짜(MMDD) 있으면 날짜순 정렬
    if dt: return (dt[0], dt[1])
    m = re.search(r'(\d+)월(\d+)주차', fname)
    return (int(m.group(1)), int(m.group(2)) * 7) if m else (0, 0)

def week_label(fname):
    dt = _date_in(fname)
    if dt: return f'{dt[0]}/{dt[1]}'   # 예: 7/6
    m = re.search(r'(\d+)월(\d+)주차', fname)
    return f'{m.group(1)}월{m.group(2)}주' if m else fname

def week_bucket(fname):
    """같은 '주차'는 하나로 묶는 키 (하루에 여러 번 돌려도 같은 버킷)."""
    m = re.search(r'(\d+)월(\d+)주차', fname)
    if m: return (int(m.group(1)), int(m.group(2)))
    dt = _date_in(fname)
    if dt: return (dt[0], (dt[1] - 1) // 7 + 1)
    return (0, 0)

def load_dataset(folder, pat, exclude):
    files = sorted(glob.glob(os.path.join(BASE, folder, pat)), key=lambda f: week_key(os.path.basename(f)))
    if exclude:
        files = [f for f in files if exclude not in os.path.basename(f)]
    by_bucket = {}
    meta = {'unit': '%', 'drvlabel': '', 'drvunit': '', 'drvdir': -1}
    for f in files:
        try:
            df = _norm(pd.read_excel(f))
        except Exception:
            continue
        cols = list(df.columns)
        idc   = _pick(cols, '그룹ID', 'ID', 'id', 'clubId')
        rankc = _pick(cols, '노출순위', 'listing_rank')
        pctc  = _pick(cols, '노출백분위')
        namec = _pick(cols, '모임명', '제목', 'name')
        if not idc or not rankc:
            continue
        d = pd.DataFrame({
            'id':   df[idc].astype(str),
            'rank': pd.to_numeric(df[rankc], errors='coerce'),
            'name': df[namec].astype(str) if namec else df[idc].astype(str),
        })
        if pctc:
            d['pct'] = pd.to_numeric(df[pctc], errors='coerce'); meta['unit'] = '%'
        else:
            d['pct'] = d['rank']; meta['unit'] = '위'      # 백분위 없으면 노출순위(위)로 표시
        # 움직임 원인(드라이버): 최신성 우선, 없으면 참여 지표
        # 원인(드라이버)은 '검증된 최신성'만 사용 — 참여수 등 미검증 지표는 원인으로 표시하지 않음
        recc = _pick(cols, '최근활동_분', '최근대화(분)')   # 분 단위(문토·당근)
        recd = _pick(cols, '최근활동_일')                   # 일 단위(소모임 신규)
        engc = _pick(cols, '현재참여수')                    # 소셜링: 참여자수가 노출 동력(rho -0.55, 검증됨)
        if recc:
            d['drv'] = pd.to_numeric(df[recc], errors='coerce') / 1440.0
            meta.update(drvlabel='최근활동', drvunit='일 전', drvdir=-1)
        elif recd:
            d['drv'] = pd.to_numeric(df[recd], errors='coerce')            # 이미 일 단위
            meta.update(drvlabel='최근활동', drvunit='일 전', drvdir=-1)
        elif engc:
            d['drv'] = pd.to_numeric(df[engc], errors='coerce')            # 참여자 수(높을수록 상위)
            meta.update(drvlabel='참여', drvunit='명', drvdir=1)
        d = d.dropna(subset=['rank'])
        d = d.drop_duplicates(subset=['id'], keep='first')
        bkt = week_bucket(os.path.basename(f))
        lbl = week_label(os.path.basename(f))
        # 같은 주차 파일이 여러 개면 '가장 완전한(행 많은)' 것만 사용
        prev = by_bucket.get(bkt)
        if prev is None or len(d) > prev[1]:
            by_bucket[bkt] = (lbl, len(d), d)
    weeks = [(lbl, d) for _, (lbl, _n, d) in sorted(by_bucket.items())]
    # 부분수집(덜 걷힌 주) 제외 — 가장 완전한 주의 60% 미만이면 신뢰 못 하므로 분석에서 뺌
    if len(weeks) >= 2:
        mx = max(len(d) for _, d in weeks)
        kept = [(lbl, d) for (lbl, d) in weeks if len(d) >= mx * 0.6]
        dropped = [lbl for (lbl, d) in weeks if len(d) < mx * 0.6]
        if dropped:
            print(f'   ⚠ 부분수집 제외: {folder} → {", ".join(dropped)} (완전수집 대비 60% 미만)')
        weeks = kept
    return weeks, meta

def _render_activity(title, weeks, meta):
    """순위가 노이즈인 플랫폼 → 검증된 동력(소모임=활동최신성, 소셜링=참여수) 뷰로 대체."""
    last = weeks[-1][1].copy()
    last['drv'] = pd.to_numeric(last['drv'], errors='coerce')
    d = last.dropna(subset=['drv'])
    n = last['id'].nunique()
    lab = weeks[-1][0]
    dl = meta.get('drvlabel', '활동'); du = meta.get('drvunit', '')
    recency = meta.get('drvdir', -1) < 0     # True=최신성(낮을수록↑), False=참여수(높을수록↑)
    def fmt(v):
        v = int(round(v))
        return ('오늘 활동' if v <= 0 else f'{v}일 전') if recency else f'{v}{du}'
    def rows(dd, good):
        c = '#16a34a' if good else '#ef4444'
        return ''.join(f'<tr><td class="nm">{_esc(x.name)[:30]}</td>'
                       f'<td style="text-align:right;color:{c};font-weight:800;white-space:nowrap;">{fmt(x.drv)}</td></tr>'
                       for x in dd.itertuples())
    best  = d.sort_values('drv', ascending=recency).head(6)
    worst = d.sort_values('drv', ascending=not recency).head(6)
    if recency:
        h1, h2 = '🔥 가장 활발한 모임', '💤 휴면 위험 (오래 조용)'
        note = ('소모임 노출순위는 앱 알고리즘 셔플이라 <b>순위 변동은 노이즈</b>예요. 그래서 유일하게 믿을 수 있는 '
                '<b>"활동 최신성(마지막 게시글일)"</b>으로 보여드려요 — 소모임 노출의 실제 동력입니다.')
        s1 = (d['drv'] <= 1).mean() * 100; s2 = (d['drv'] >= 30).mean() * 100
        summ = (f'전체의 <b>{s1:.0f}%</b>가 최근 1일 내 활동 · <b>{s2:.0f}%</b>는 30일+ 휴면. '
                f'상위 노출은 "오늘 활동"한 모임 몫 — 매일 사진첩·게시판·채팅으로 활동일을 오늘로 유지하세요.')
    else:
        h1, h2 = f'🔥 인기 소셜링 (참여 많은 순)', '📉 참여 저조'
        note = ('문토 소셜링 노출은 <b>현재 참여자 수</b>가 핵심 동력이에요(상관 -0.55로 가장 강함). '
                '순위 변동은 노이즈라, 실제 동력인 <b>참여 규모</b>로 보여드려요.')
        summ = (f'상위 소셜링일수록 참여자가 많아요(참여 중앙값 상위 {int(best["drv"].median())}명). '
                f'참여 유도(초기 신청·좋아요)가 노출의 핵심이에요.')
    return (f'<div class="ds"><h2>{title} <span class="meta">{lab} · {n:,}개</span></h2>'
            f'<p class="hint">ℹ️ {note}</p>'
            f'<div class="grid2">'
            f'<div class="box"><h3>{h1}</h3><table>{rows(best, True)}</table></div>'
            f'<div class="box"><h3>{h2}</h3><table>{rows(worst, False)}</table></div></div>'
            f'<div class="box" style="background:#f0fdf4;border-color:#bbf7d0;"><h3>💡 요약</h3>'
            f'<div style="font-size:0.86rem;color:#166534;line-height:1.6;">{summ}</div></div></div>')

def render_dataset(title, weeks, meta, noisy=False):
    if not weeks:
        return ''
    # 순위가 노이즈인 플랫폼 + 검증된 동력데이터 있으면 → 동력 기반 뷰
    if noisy and 'drv' in weeks[-1][1].columns and pd.to_numeric(weeks[-1][1]['drv'], errors='coerce').notna().sum() >= 5:
        return _render_activity(title, weeks, meta)
    U = meta['unit']
    unit_help = ('노출백분위 = 전체 중 상위 몇 %인지 (낮을수록 상위노출, 예: 3%=상위 3%)'
                 if U == '%' else '노출순위 = 목록에서 몇 번째로 보이는지 (낮을수록 상위노출)')
    labels = [w[0] for w in weeks]
    n_entities = weeks[-1][1]['id'].nunique()
    has_drv = 'drv' in weeks[-1][1].columns
    dl = meta.get('drvlabel', '')

    if len(weeks) == 1:
        d = weeks[-1][1].sort_values('rank').head(20)
        rows = ''.join(
            f'<tr><td class="r">{int(x.rank)}</td><td class="nm">{_esc(x.name)[:34]}</td>'
            f'<td class="p">{x.pct:.0f}{U}</td></tr>' for x in d.itertuples())
        head = '백분위' if U == '%' else '노출순위'
        return (f'<div class="ds"><h2>{title} <span class="meta">{labels[0]} · {n_entities:,}개</span></h2>'
                f'<p class="hint">📸 1주차 스냅샷 ({unit_help}). 다음 주가 쌓이면 변화·원인이 표시돼요.</p>'
                f'<table><thead><tr><th>순위</th><th>이름</th><th>{head}</th></tr></thead><tbody>{rows}</tbody></table></div>')

    first, last = weeks[0][1].copy(), weeks[-1][1].copy()
    # drv(최신성)가 한쪽에만 있어도 병합 후 항상 drv_f·drv_l 이 생기도록 강제
    if 'drv' not in first.columns: first['drv'] = pd.NA
    if 'drv' not in last.columns:  last['drv'] = pd.NA
    m = pd.merge(first[['id', 'name', 'pct', 'drv']], last[['id', 'pct', 'drv']],
                 on='id', suffixes=('_f', '_l'))
    m['delta'] = m['pct_l'] - m['pct_f']
    up   = m.sort_values('delta').head(5)
    down = m.sort_values('delta', ascending=False).head(5)

    # ⚠️ 신뢰도 경고 — 수집 규모 차이/한 방향 쏠림이면 비교가 착시일 수 있음
    n_f, n_l = len(first), len(last)
    ratio = max(n_f, n_l) / max(min(n_f, n_l), 1)
    up_c = int((m['delta'] < 0).sum()); dn_c = int((m['delta'] > 0).sum()); tot = up_c + dn_c
    umetric = '백분위' if U == '%' else '순위'
    warn = ''
    if ratio >= 1.5:
        warn += (f'<div class="box" style="background:#fff7ed;border-color:#fed7aa;margin-bottom:12px;">'
                 f'<h3 style="color:#c2410c;">⚠️ 비교 주의 — 수집 규모가 달라요</h3>'
                 f'<div style="font-size:0.83rem;color:#9a3412;line-height:1.6;">두 시점 수집량이 <b>{n_f:,}개 vs {n_l:,}개</b>로 달라, '
                 f'노출{umetric} 변화가 실제가 아니라 <b>수집 범위 차이(착시)</b>일 수 있어요. 같은 규모로 수집된 주끼리 비교해야 정확합니다.</div></div>')
    if tot >= 10 and (up_c / tot >= 0.85 or dn_c / tot >= 0.85):
        side = '상승' if up_c > dn_c else '하락'
        warn += (f'<div class="box" style="background:#fff7ed;border-color:#fed7aa;margin-bottom:12px;">'
                 f'<h3 style="color:#c2410c;">⚠️ 한 방향 쏠림 ({side} {max(up_c, dn_c)}/{tot})</h3>'
                 f'<div style="font-size:0.83rem;color:#9a3412;">거의 다 {side}으로 몰린 건 실제 움직임보다 수집 시점·범위 차이일 가능성이 커요.</div></div>')

    def why_of(x):
        if not has_drv:
            return ''
        l = getattr(x, 'drv_l', None); f = getattr(x, 'drv_f', None)
        if l is None or (isinstance(l, float) and pd.isna(l)):
            return ''
        if dl == '최근활동':
            if f is not None and pd.notna(f):
                return f'최근활동 {f:.0f}일→<b>{l:.0f}일</b> 전'
            return f'최근활동 {l:.0f}일 전'
        if f is not None and pd.notna(f):
            return f'{dl} {f:.0f}→<b>{l:.0f}</b>'
        return f'{dl} {l:.0f}'

    def chg_rows(dd):
        out = ''
        for x in dd.itertuples():
            arrow = '🔺' if x.delta < 0 else ('🔻' if x.delta > 0 else '➖')
            col = '#16a34a' if x.delta < 0 else ('#ef4444' if x.delta > 0 else '#888')
            w = why_of(x)
            wl = f'<div style="font-size:0.74rem;color:#8a8a8a;margin-top:2px;">↳ {w}</div>' if w else ''
            unit_d = '%p' if U == '%' else '위'
            out += (f'<tr><td class="nm">{_esc(x.name)[:26]}{wl}</td>'
                    f'<td class="p">{x.pct_f:.0f}{U} → {x.pct_l:.0f}{U}</td>'
                    f'<td style="color:{col};font-weight:800;white-space:nowrap;">{arrow} {abs(x.delta):.0f}{unit_d}</td></tr>')
        return out

    why = ''
    if has_drv and dl == '최근활동':
        ris = m[m['delta'] < -5]; fal = m[m['delta'] > 5]
        if len(ris) >= 3 and len(fal) >= 3 and ris['drv_l'].notna().sum() and fal['drv_l'].notna().sum():
            r_d, f_d = ris['drv_l'].median(), fal['drv_l'].median()
            verd = '최근에 활동한 모임이 상위로 올라갔어요' if r_d < f_d else '이번엔 최신성 외 요인이 컸어요'
            why = (f'<div class="box" style="background:#f0fdf4;border-color:#bbf7d0;margin-bottom:14px;">'
                   f'<h3>💡 왜 움직였나 — 최신성</h3>'
                   f'<div style="font-size:0.86rem;color:#166534;line-height:1.6;">'
                   f'노출 <b>상승</b> 모임은 최근활동 <b>{r_d:.0f}일 전</b>, <b>하락</b>은 <b>{f_d:.0f}일 전</b>. {verd}. '
                   f'각 항목 밑 ↳ 에 개별 변화가 있어요.</div></div>')
    elif not has_drv:
        why = ('<div class="box" style="background:#f8fafc;border-color:#e2e8f0;margin-bottom:14px;">'
               '<h3>ℹ️ 왜 움직였는지 — 지금 데이터로는 알 수 없어요</h3>'
               '<div style="font-size:0.83rem;color:#475569;line-height:1.6;">'
               '이 플랫폼은 움직임은 실제지만, <b>수집하는 필드(멤버·정모·활동레벨)가 상승·하락과 무관</b>했어요 '
               '— 즉 원인은 우리가 아직 안 걷는 신호(예: <b>최근 게시글·정모 개최 날짜</b>)예요. '
               '원인까지 보려면 트래커가 "실제 최근 활동 날짜"를 추가로 수집해야 해요.</div></div>')

    # 막대차트: 급상승·급하락 한눈에 (막대 길수록 크게 움직임)
    movers = pd.concat([up, down]).drop_duplicates('id').sort_values('delta')
    bl = [_esc(str(n))[:12] for n in movers['name']]
    bv = [int(round(-x)) for x in movers['delta']]          # 양수=상승(개선), 음수=하락
    bc = ['#16a34a' if v > 0 else ('#ef4444' if v < 0 else '#9ca3af') for v in bv]
    cid = re.sub(r'\W', '', title)
    chart_js = json.dumps({'labels': bl, 'values': bv, 'colors': bc, 'unit': U}, ensure_ascii=False)
    ud = '%p' if U == '%' else '위'
    return (f'<div class="ds"><h2>{title} <span class="meta">{labels[0]}~{labels[-1]} · {n_entities:,}개</span></h2>'
            f'<p class="hint">📖 {unit_help}<br>🔺=상위로 올라감, 🔻=밀림 · 각 항목 밑 <b>↳</b> 는 왜 그랬는지(원인 지표) 변화예요.</p>'
            f'{warn}'
            f'<div class="grid2">'
            f'<div class="box"><h3>🔺 급상승 TOP 5</h3><table>{chg_rows(up)}</table></div>'
            f'<div class="box"><h3>🔻 급하락 TOP 5</h3><table>{chg_rows(down)}</table></div></div>'
            f'{why}'
            f'<div class="box"><h3>📊 급상승·급하락 한눈에 <span class="meta">막대 위=상승({ud}), 아래=하락</span></h3>'
            f'<div style="position:relative;height:230px;"><canvas id="c{cid}"></canvas></div></div>'
            f'<script>window.CHARTS=window.CHARTS||[];window.CHARTS.push(["c{cid}",{chart_js}]);</script></div>')

def _esc(s):
    return (str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))

def main():
    import sys
    exclude = [a for a in sys.argv[1:] if not a.startswith('-')]   # 예: python3 추적_대시보드.py 당근
    blocks = []
    for name, folder, pat, exc, noisy in DATASETS:
        if exclude and any(x in name for x in exclude):
            print(f'   ⏭  {name}: 명령어로 제외'); continue
        weeks, meta = load_dataset(folder, pat, exc)
        if not weeks:                                # 데이터 없는 플랫폼은 자동 제외
            print(f'   ⏭  {name}: 수집 파일 없음 → 제외'); continue
        blocks.append(render_dataset(name, weeks, meta, noisy))
    if not blocks:
        blocks = ['<div class="ds"><p class="empty">표시할 데이터가 없어요.</p></div>']
    html = '''<!DOCTYPE html><html lang="ko"><head><meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>순위 추적 대시보드 | Longchiri</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box;}body{font-family:'Apple SD Gothic Neo','Segoe UI',sans-serif;background:#f7f9fb;color:#202020;padding:32px 16px 70px;word-break:keep-all;}
.wrap{max-width:900px;margin:0 auto;}h1{font-size:1.4rem;font-weight:900;text-align:center;margin-bottom:4px;}
.subt{text-align:center;color:#7a9bba;font-size:0.85rem;margin-bottom:26px;}
.ds{background:#fff;border:1.5px solid #e8ecef;border-radius:16px;padding:20px 22px;margin-bottom:18px;}
.ds h2{font-size:1.1rem;font-weight:900;margin-bottom:12px;}.meta{font-size:0.72rem;font-weight:500;color:#94a3b8;}
.ds h3{font-size:0.86rem;font-weight:800;margin-bottom:8px;color:#475569;}
.hint{font-size:0.82rem;color:#64748b;background:#f8fafc;border-radius:10px;padding:10px 12px;margin-bottom:12px;}
.empty{color:#aaa;font-size:0.85rem;}
table{width:100%;border-collapse:collapse;font-size:0.82rem;}
th{text-align:left;color:#94a3b8;font-size:0.72rem;font-weight:700;padding:5px 6px;border-bottom:1px solid #eef1f4;}
td{padding:7px 6px;border-bottom:1px solid #f4f6f8;}
td.r{font-weight:800;color:#ff4628;width:42px;}td.nm{font-weight:600;}td.p{color:#64748b;white-space:nowrap;}
td.why{color:#475569;font-size:0.79rem;line-height:1.5;}
.grid2{display:grid;gap:14px;margin-bottom:14px;}@media(min-width:600px){.grid2{grid-template-columns:1fr 1fr;}}
.box{background:#fafbfc;border:1px solid #eef1f4;border-radius:12px;padding:14px 15px;}
</style></head><body><div class="wrap">
<h1>📊 순위 추적 대시보드</h1>
<div class="subt">생성: ''' + datetime.now().strftime('%Y-%m-%d %H:%M') + '''</div>
''' + ''.join(blocks) + '''
</div><script>
(window.CHARTS||[]).forEach(function(c){
  var ctx=document.getElementById(c[0]); if(!ctx)return; var d=c[1];
  new Chart(ctx,{type:'bar',
    data:{labels:d.labels,datasets:[{data:d.values,backgroundColor:d.colors,borderRadius:4,barPercentage:0.75}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{display:false},
        tooltip:{callbacks:{label:function(t){var v=t.raw;var u=(d.unit==='%'?'%p':'위');return (v>=0?'▲ 상승 ':'▼ 하락 ')+Math.abs(v)+u;}}}},
      scales:{
        x:{ticks:{font:{size:11},maxRotation:60,minRotation:45},grid:{display:false}},
        y:{title:{display:true,text:(d.unit==='%'?'노출 개선(%p)':'노출 개선(위)')+'  ↑상승 / ↓하락'},
           grid:{color:function(g){return g.tick.value===0?'#94a3b8':'#eef1f4';},lineWidth:function(g){return g.tick.value===0?1.5:1;}}}
      }}});
});
</script></body></html>'''
    out_dir = os.path.join(BASE, '전체분석')
    os.makedirs(out_dir, exist_ok=True)
    today = datetime.now().strftime('%Y%m%d')
    out = os.path.join(out_dir, f'전체분석_{today}.html')
    open(out, 'w', encoding='utf-8').write(html)
    # 항상 최신본도 같은 폴더에 (덮어쓰기 — 바로 열기용)
    latest = os.path.join(out_dir, '전체분석_최신.html')
    open(latest, 'w', encoding='utf-8').write(html)
    print(f'✅ 대시보드 생성: {out}')
    print(f'   (최신본: {latest})')
    # 생성 후 폴더(Finder) + HTML(브라우저) 자동 열기 (맥 전용, --no-open 으로 끔)
    if sys.platform == 'darwin' and '--no-open' not in sys.argv:
        try:
            import subprocess
            subprocess.run(['open', out_dir])   # 전체분석 폴더 → Finder
            subprocess.run(['open', out])       # 오늘자 대시보드 → 브라우저
            print('   🪟 폴더와 대시보드를 열었어요.')
        except Exception:
            print('   (자동 열기 실패 — 위 경로를 직접 열어주세요.)')
    else:
        print('   브라우저로 열면 돼요. 매주 데이터 쌓인 뒤 다시 실행하면 변화가 보여요.')

if __name__ == '__main__':
    main()
