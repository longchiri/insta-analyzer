# -*- coding: utf-8 -*-
"""
소모임 API 정렬(ran) + 원본 필드 확인 probe
────────────────────────────────────────────
목적 2가지:
  ① ran=1~6 중 어떤 게 앱의 '최신순'/'인기순'과 같은 순서인지 (눈으로 대조)
  ② 목록 응답 원본 아이템에 '최근활동 타임스탬프' 필드가 있는지
     → 있으면 상세 안 긁고 목록만으로 최근활동 수집 가능 (빠름)

실행:  cd ~/Desktop/longchiri && python3 소모임_정렬확인.py
"""
import json, time, os, datetime, requests

BASE = os.path.dirname(os.path.abspath(__file__))
API  = "https://www.somoim.co.kr/api/groups/category"
HDR  = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

def load_codes():
    reg = json.load(open(os.path.join(BASE, "somoim", "소모임_지역코드.json"), encoding="utf-8"))
    cat = json.load(open(os.path.join(BASE, "somoim", "소모임_카테고리코드.json"), encoding="utf-8"))
    def first(d):
        for v in d.values():
            if isinstance(v, str) and v.strip(): return v
        return None
    return reg, cat, first(reg), first(cat)

def call(loc, it, ran, n=8):
    payload = {"ver": 526, "os": "wl", "loc": loc, "loc2": "0",
               "it": it, "s_t": int(time.time()), "ran": ran, "vql": n, "typ": 2}
    r = requests.post(API, json=payload, headers=HDR, timeout=10)
    return r.json()

def ts_fields(item):
    """에폭(초/밀리초)로 보이는 필드 찾아 사람이 읽는 날짜로."""
    out = []
    for k, v in item.items():
        try:
            iv = float(v)
        except (TypeError, ValueError):
            continue
        for div, unit in ((1, "초"), (1000, "밀리초")):
            e = iv / div
            if 1_400_000_000 < e < 2_000_000_000:   # 2014~2033 사이
                out.append(f"{k}={v}  → {datetime.datetime.fromtimestamp(e)}  ({unit})")
                break
    return out

def main():
    reg, cat, loc, it = load_codes()
    loc = reg.get("서울특별시", loc)
    catname = next((k for k, v in cat.items() if v == it), it)
    print(f"조회 스코프 → 지역 서울({loc}) / 카테고리 {catname}({it})\n")

    print("═══ ① ran 값별 상위 순서 (앱의 최신순/인기순과 대조) ═══")
    for ran in [1, 2, 3, 4, 5, 6]:
        try:
            d = call(loc, it, ran); gs = d.get("l", [])
            print(f"── ran={ran} ──")
            for i, g in enumerate(gs[:6], 1):
                print(f"   {i}. {g.get('gn','?')}  (멤버 {g.get('gmc',0)})")
        except Exception as e:
            print(f"── ran={ran} ── 에러: {str(e)[:80]}")
        print()

    print("═══ ② 원본 아이템 전체 필드 + 타임스탬프 후보 (ran=3 기준) ═══")
    try:
        d = call(loc, it, 3); gs = d.get("l", [])
        if gs:
            print("전체 키:", sorted(gs[0].keys()))
            print("\n타임스탬프로 보이는 필드 (상위 3개 모임):")
            for g in gs[:3]:
                print(f"  [{g.get('gn','?')[:16]}]")
                tf = ts_fields(g)
                if tf:
                    for line in tf: print("     ", line)
                else:
                    print("      (에폭 타임스탬프 필드 없음)")
            print("\n응답 s_t(다음 커서):", d.get("s_t"))
    except Exception as e:
        print("에러:", str(e)[:100])

    print("\n👉 알려줄 것: (1) 위 ran 중 앱 '최신순'과 같은 번호,")
    print("   (2) ②에 '최근활동'으로 보이는 타임스탬프 필드가 있는지 (예: 상위 모임일수록 최근)")

if __name__ == "__main__":
    main()
