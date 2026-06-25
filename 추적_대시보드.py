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
DATASETS = [
    ('🥕 당근 모임',   'daangn', '당근_*주차_스크롤결과.xlsx',      None),
    ('🌿 소모임',      'somoim', '소모임_*주차_스크롤결과.xlsx',     None),
    ('🔥 문토 클럽',   'munto',  '문토_*주차_스크롤결과.xlsx',       '소셜링'),
    ('🎉 문토 소셜링', 'munto',  '문토_소셜링_*주차_스크롤결과.xlsx', None),
]

def _norm(df):
    df.columns = [unicodedata.normalize('NFC', str(c)) for c in df.columns]
    return df

def _pick(cols, *cands):
    for c in cands:
        if c in cols: return c
    return None

def week_key(fname):
    m = re.search(r'(\d+)월(\d+)주차', fname)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)

def week_label(fname):
    m = re.search(r'(\d+)월(\d+)주차', fname)
    return f'{m.group(1)}월{m.group(2)}주' if m else fname

def load_dataset(folder, pat, exclude):
    files = sorted(glob.glob(os.path.join(BASE, folder, pat)), key=lambda f: week_key(os.path.basename(f)))
    if exclude:
        files = [f for f in files if exclude not in os.path.basename(f)]
    weeks = []
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
        d['pct'] = pd.to_numeric(df[pctc], errors='coerce') if pctc else d['rank']
        d = d.dropna(subset=['rank'])
        weeks.append((week_label(os.path.basename(f)), d))
    return weeks

def render_dataset(title, weeks):
    if not weeks:
        return f'<div class="ds"><h2>{title}</h2><p class="empty">아직 수집된 주차 파일이 없어요.</p></div>'
    labels = [w[0] for w in weeks]
    n_entities = weeks[-1][1]['id'].nunique()

    if len(weeks) == 1:
        # 스냅샷 — 현재 순위 TOP 20
        d = weeks[-1][1].sort_values('rank').head(20)
        rows = ''.join(
            f'<tr><td class="r">{int(x.rank)}</td><td class="nm">{_esc(x.name)[:34]}</td>'
            f'<td class="p">{x.pct:.0f}%</td></tr>' for x in d.itertuples())
        return (f'<div class="ds"><h2>{title} <span class="meta">{labels[0]} · {n_entities:,}개</span></h2>'
                f'<p class="hint">📸 1주차 스냅샷이에요. 다음 주가 쌓이면 순위 변화·급상승이 표시돼요.</p>'
                f'<table><thead><tr><th>순위</th><th>이름</th><th>백분위</th></tr></thead><tbody>{rows}</tbody></table></div>')

    # 2주차 이상 — 변화 분석
    first, last = weeks[0][1], weeks[-1][1]
    m = pd.merge(first[['id','name','pct']], last[['id','pct']], on='id', suffixes=('_f','_l'))
    m['delta'] = m['pct_l'] - m['pct_f']           # 음수 = 백분위 낮아짐 = 상승
    up   = m.sort_values('delta').head(5)
    down = m.sort_values('delta', ascending=False).head(5)
    def chg_rows(dd, up=True):
        out=''
        for x in dd.itertuples():
            arrow = '🔺' if x.delta < 0 else ('🔻' if x.delta > 0 else '➖')
            col = '#16a34a' if x.delta < 0 else ('#ef4444' if x.delta > 0 else '#888')
            out += (f'<tr><td class="nm">{_esc(x.name)[:30]}</td>'
                    f'<td class="p">{x.pct_f:.0f}% → {x.pct_l:.0f}%</td>'
                    f'<td style="color:{col};font-weight:800;">{arrow} {abs(x.delta):.0f}%p</td></tr>')
        return out
    # 라인차트 데이터: 마지막 주 상위 8개 엔티티의 주차별 백분위
    top_ids = last.sort_values('rank').head(8)['id'].tolist()
    series = []
    for tid in top_ids:
        nm = last[last['id']==tid]['name'].iloc[0]
        pts = []
        for _, d in weeks:
            row = d[d['id']==tid]
            pts.append(round(float(row['pct'].iloc[0]),1) if len(row) else None)
        series.append({'label': _esc(nm)[:18], 'data': pts})
    cid = re.sub(r'\W','',title)
    chart_js = json.dumps({'labels':labels,'series':series}, ensure_ascii=False)
    return (f'<div class="ds"><h2>{title} <span class="meta">{labels[0]}~{labels[-1]} · {n_entities:,}개</span></h2>'
            f'<div class="grid2">'
            f'<div class="box"><h3>🔺 급상승 TOP 5</h3><table>{chg_rows(up)}</table></div>'
            f'<div class="box"><h3>🔻 급하락 TOP 5</h3><table>{chg_rows(down,False)}</table></div></div>'
            f'<div class="box"><h3>📈 상위 클럽 노출백분위 추이 <span class="meta">낮을수록 상위노출</span></h3>'
            f'<canvas id="c{cid}" height="120"></canvas></div>'
            f'<script>window.CHARTS=window.CHARTS||[];window.CHARTS.push(["c{cid}",{chart_js}]);</script></div>')

def _esc(s):
    return (str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;'))

def main():
    blocks = [render_dataset(name, load_dataset(folder, pat, exc)) for name, folder, pat, exc in DATASETS]
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
.grid2{display:grid;gap:14px;margin-bottom:14px;}@media(min-width:600px){.grid2{grid-template-columns:1fr 1fr;}}
.box{background:#fafbfc;border:1px solid #eef1f4;border-radius:12px;padding:14px 15px;}
</style></head><body><div class="wrap">
<h1>📊 순위 추적 대시보드</h1>
<div class="subt">생성: ''' + datetime.now().strftime('%Y-%m-%d %H:%M') + '''</div>
''' + ''.join(blocks) + '''
</div><script>
(window.CHARTS||[]).forEach(function(c){
  var ctx=document.getElementById(c[0]); if(!ctx)return; var d=c[1];
  var palette=['#ff4628','#16a34a','#2563eb','#c0146a','#f59e0b','#8b5cf6','#0ea5e9','#ef4444'];
  new Chart(ctx,{type:'line',data:{labels:d.labels,datasets:d.series.map(function(s,i){
    return {label:s.label,data:s.data,borderColor:palette[i%8],backgroundColor:'transparent',tension:0.3,spanGaps:true,pointRadius:3};
  })},options:{plugins:{legend:{labels:{boxWidth:12,font:{size:10}}}},scales:{y:{reverse:true,title:{display:true,text:'노출백분위(낮을수록 상위)'}}}}});
});
</script></body></html>'''
    out = os.path.join(BASE, '추적_대시보드.html')
    open(out, 'w', encoding='utf-8').write(html)
    print(f'✅ 대시보드 생성: {out}')
    print('   브라우저로 열면 돼요. 매주 데이터 쌓인 뒤 다시 실행하면 변화가 보여요.')

if __name__ == '__main__':
    main()
