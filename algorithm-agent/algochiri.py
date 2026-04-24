"""
AlgoChiri — longchiri 알고리즘 업데이트 에이전트
=================================================
인스타·카카오·당근·소모임·문토 알고리즘 최신 정보를 검색하고
분석기 HTML 파일을 자동 업데이트합니다.

사용법:
  python algochiri.py
"""

import os
import json
import time
import anthropic
from datetime import datetime
from ddgs import DDGS
from dotenv import load_dotenv

# .env 파일에서 API 키 로드
load_dotenv()

# ── 설정 ──────────────────────────────────────────
API_KEY = os.getenv("ANTHROPIC_API_KEY")

# 파일 경로 (이 스크립트 기준 상대경로)
# 인스타그램 분석기는 GitHub에서 index.html로 배포됨
FILES = {
    "insta":   "../index.html",
    "kakao":   "../kakao-analyzer.html",
    "daangn":  "../daangn-analyzer.html",
    "moim":    "../moim-analyzer.html",
    "hub":     "../hub.html",
}

# 로컬 파일 → GitHub 파일명 매핑
# 인스타그램 분석기는 GitHub에서 index.html로 배포됨
GITHUB_FILE_MAP = {
    "../인스타 분석/insta-analyzer.html": "../index.html",
    "../카카오 분석/kakao-analyzer.html": "../kakao-analyzer.html",
    "../hub.html": "../hub.html",
}

# 검색할 플랫폼별 키워드 (연도 동적 생성 + 최신 강조)
_year = datetime.now().year
_month = datetime.now().month
SEARCH_QUERIES = [
    f"인스타그램 알고리즘 최신 업데이트 {_year}년 {_month}월",
    f"instagram algorithm update latest {_year}",
    f"카카오 당근 소모임 알고리즘 최신 변경 {_year}",
]

# ── 안전 제한 ─────────────────────────────────────
MAX_TURNS = 20          # 무한루프 방지: 최대 API 호출 횟수
FILE_READ_LIMIT = 5000  # 파일 읽기 최대 글자 수 (토큰 절약)

# ── 공통 프롬프트 ─────────────────────────────────
SYSTEM_PROMPT = """
당신은 SNS·커뮤니티 알고리즘 전문 업데이트 에이전트 AlgoChiri입니다.
오늘 날짜: {today}

## 역할
1. 웹 검색(최대 3회)으로 각 플랫폼 최신 알고리즘 변경사항을 조사합니다.
2. 분석기 파일을 읽고 업데이트 필요 여부를 판단합니다.
3. 필요하면 patch_file로 수정하고, hub.html도 업데이트합니다.
4. report로 결과를 보고하고 즉시 종료합니다.

## 파일 설명
- insta:   인스타그램 분석기 (index.html)
- kakao:   카카오 오픈채팅 분석기 (kakao-analyzer.html)
- daangn:  당근 모임 분석기 (daangn-analyzer.html)
- moim:    소모임×문토 분석기 (moim-analyzer.html)
- hub:     메인 허브 페이지 (hub.html)

## ⚠️ 토큰 절약 — 필수 규칙
- 검색은 최대 3회만 합니다. 추가 검색 금지.
- read_file 결과는 앞 5000자만 참고합니다.
- patch_file 실패 시 **같은 파일에 재시도는 1회만** 허용. 2번 실패하면 그냥 넘어가세요.
- 불필요한 확인용 read_file 금지. 패치 전 1회만 읽으세요.
- 변화가 없으면 즉시 report하고 종료하세요.

## 파일 수정 방법
- insta·kakao·daangn·moim 파일은 매우 큽니다. **반드시 patch_file만 사용하세요.**
- hub.html은 write_file 사용 가능합니다.
- 분석기 수정 시 hub.html 버전 번호 + 로그도 업데이트하세요.

## 버전 번호 규칙 (X.Y.Z 시맨틱 버전)
- Z (패치): AlgoChiri 자동 업데이트로 내용 수정 시 +1 (예: 3.3.0 → 3.3.1)
- Y (마이너): 새 지표·기능 추가 시 +1, Z는 0으로 리셋 (예: 3.3.x → 3.4.0)
- X (메이저): 대형 개편 시 +1, Y·Z 모두 0 리셋 (예: 3.x.x → 4.0.0)
- Y 또는 Z가 9를 넘으면 상위 버전을 올리고 리셋 (예: 3.9.9 → 4.0.0)
- 현재 버전은 hub.html 내 <span class="ver">Ver X.Y.Z</span>에서 읽으세요

## hub.html 업데이트 형식
버전 번호: <span class="ver">Ver X.Y.Z</span>
로그 형식: <div class="log-row"><span class="log-date">{today}</span><span class="log-text"><span class="badge b-insta">인스타 Ver X.Y.Z</span>변경 내용 요약</span></div>
뱃지: b-insta / b-kakao / b-daangn / b-moim / b-all

## hub.html 로그 관리 규칙 (반드시 준수)
- **업데이트 현황**: 항상 최신 5개만 유지합니다. 새 항목을 맨 위에 추가하고, 6번째 이하 항목은 삭제합니다.
- **업데이트 예정**: 아래 고정 항목 1개만 유지하고 절대 변경·추가·삭제하지 마세요:
  <div class="log-row"><span class="log-date">매주 월</span><span class="log-text"><span class="badge b-all">전체</span>매주 월요일 10:00 알고리즘 정기 점검 — AlgoChiri 자동 실행</span></div>
- 완료(✅) 항목을 업데이트 예정에 추가하지 않습니다.

## 인스타그램 알고리즘 2026 확인된 변경사항 (분석기 업데이트 시 반영)
- 해시태그 최대 5개로 제한 (기존 30개 → 2026년 5개로 축소 공식화)
- Reels 최대 길이 20분으로 확대, 단 **최적 성과 구간은 20~40초** (5~7초 피로 구간, 90초↑ 배포 감소)
- **DM 공유(Sends)가 릴스 배포 최강 신호** — 좋아요·댓글보다 가중치 높음. Mosseri 2026년 4월 공식 확인
- 체류 시간(Watch Time) > 조회수 우선: DM공유 > 저장 > 댓글 > 좋아요 순서로 가중치
- 처음 5~7초 구간이 "피로 구간"으로 분류 — 빠른 Hook 필수, 인트로 없애야 함
- **"Your Algorithm" 토픽 대시보드 신규** — 설정 → 콘텐츠 환경설정에서 피드 추천 토픽 직접 추가·삭제 가능
- 도달(reach)보다 전환율·저장·공유가 실질 성과 지표로 이동 중
- 출처: 2026년 4월 기준 인스타그램 알고리즘 분석 리포트 종합

## 당근 알고리즘 2026 업데이트 (참고)
- 당근 추천 AI가 LLM/Foundation Model 기반으로 고도화 (SIGIR 2026 논문 채택, 2026.04 기준)
- 카페(온라인 커뮤니티) 신규 서비스 출시 (2026.01, 서울·수도권, 시·구 단위 노출, 17개 카테고리)
- 모임 노출 알고리즘: 위치·관심사·활동 품질 종합 반영 (추천 정확도 대폭 향상)

## 당근 모임 분석기 고정 사실 (절대 변경 금지)
- 당근 모임에는 **끌올(끌어올리기) 기능이 없습니다.** 당근 고객센터에서 공식 확인된 사항입니다.
  - 끌올은 중고거래 게시글에만 존재하며 모임에는 적용되지 않습니다.
  - daangn-analyzer.html에 끌올 관련 입력·분석·팁을 절대 추가하지 마세요.
- daangn-analyzer.html v3.6.0 현재 입력 항목 구성 (섹션 4 노출 최적화):
  - tagSet: 모임 태그 설정 (many/few/none)
  - responseSpeed: 호스트 응답 속도 (fast/same/slow/very_slow)
  - memberLimit: 멤버 상한 설정 (yes/no)
  - publicReview: 모임 공개 후기 수 (숫자)

## 현재 버전 현황 (2026.04.23 기준)
- 인스타그램 분석기: Ver 4.2.0
- 당근 모임 분석기: Ver 3.6.0
- 소모임×문토 분석기: Ver 2.2.0
- 카카오 오픈채팅 분석기: Ver 2.2.0

## 고정 UI 요소 (절대 제거·수정 금지)
아래 항목들은 운영자가 직접 추가한 고정 요소입니다. AlgoChiri가 절대 건드리지 마세요.

1. **참고 문구** — 모든 분석기 헤더 + hub.html에 다음 문구가 있습니다:
   `<p style="margin-top:8px; font-size:0.78rem; color:#bbb; font-weight:500;">⚠️ 해당 결과 값은 <b style="color:#aaa;">참고만</b> 부탁드립니다.</p>`
   - 절대 삭제하지 마세요. 내용 변경도 금지입니다.

2. **Cloudflare Web Analytics 스크립트** — 모든 HTML 파일 </body> 직전에 있습니다:
   `<script defer src='https://static.cloudflareinsights.com/beacon.min.js' data-cf-beacon='{"token": "8f8a4525d9ac4010bc4bd44ddb28b9aa"}'></script>`
   - 절대 삭제하지 마세요. 방문자 추적 스크립트입니다.

3. **인스타그램 분석기 헤더 아이콘** — index.html 헤더에 📸 아이콘이 있습니다.
   - 다른 분석기처럼 동일한 구조를 유지하세요.

4. **hub.html 배경 마키** — `By Longchiri` 텍스트가 seamless 무한 루프로 흐릅니다.
   - 마키 관련 JS·CSS를 수정하지 마세요.

## 주의사항
- 오래된 정보(6개월 이상)는 무시하세요.
- 큰 변화가 없으면 수정하지 말고 report에 이유를 적으세요.
- 파일 구조·CSS·기능을 절대 망가뜨리지 마세요.
""".strip()

USER_PROMPT = """
오늘({today}) 알고리즘 업데이트 점검을 시작해주세요.

순서 (최대한 빠르고 간결하게):
1. 아래 키워드로 웹 검색 (최대 3회)
2. insta 파일 읽기 → 업데이트 필요 여부 판단
3. 필요하면 patch_file로 수정 (실패 시 1회만 재시도, 그 이상은 건너뜀)
4. hub.html 업데이트
5. report 후 종료

검색 키워드:
{queries}

⚠️ patch_file이 2번 연속 실패하면 해당 파일은 포기하고 다음 단계로 넘어가세요.
""".strip()

# ── 도구 정의 ──────────────────────────────────────
tools = [
    {
        "name": "web_search",
        "description": "플랫폼 알고리즘 최신 업데이트 정보를 웹에서 검색합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "검색어"
                },
                "max_results": {
                    "type": "integer",
                    "description": "검색 결과 수 (기본 5)",
                    "default": 5
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "read_file",
        "description": "HTML 파일 내용을 읽어옵니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_key": {
                    "type": "string",
                    "description": "파일 키 (insta / kakao / daangn / moim / hub)",
                    "enum": ["insta", "kakao", "daangn", "moim", "hub"]
                }
            },
            "required": ["file_key"]
        }
    },
    {
        "name": "patch_file",
        "description": "HTML 파일에서 특정 텍스트를 찾아 교체합니다. 파일이 크므로 전체를 다시 쓰지 말고 이 도구로 부분 수정하세요.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_key": {
                    "type": "string",
                    "description": "파일 키 (insta / kakao / daangn / moim / hub)",
                    "enum": ["insta", "kakao", "daangn", "moim", "hub"]
                },
                "old_text": {
                    "type": "string",
                    "description": "찾을 기존 텍스트 (정확히 일치해야 함)"
                },
                "new_text": {
                    "type": "string",
                    "description": "대체할 새 텍스트"
                },
                "reason": {
                    "type": "string",
                    "description": "수정 이유 (로그용)"
                }
            },
            "required": ["file_key", "old_text", "new_text", "reason"]
        }
    },
    {
        "name": "write_file",
        "description": "⚠️ 파일이 매우 크므로 이 도구 대신 patch_file을 사용하세요. hub.html처럼 작은 파일만 write_file로 전체 교체하세요.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_key": {
                    "type": "string",
                    "description": "파일 키 (hub 만 권장)",
                    "enum": ["insta", "kakao", "daangn", "moim", "hub"]
                },
                "content": {
                    "type": "string",
                    "description": "저장할 전체 HTML 내용"
                },
                "reason": {
                    "type": "string",
                    "description": "업데이트 이유 (로그용)"
                }
            },
            "required": ["file_key", "content", "reason"]
        }
    },
    {
        "name": "report",
        "description": "작업 완료 후 결과를 보고합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "오늘 업데이트 요약"
                },
                "updated_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "수정된 파일 목록"
                },
                "no_update_reason": {
                    "type": "string",
                    "description": "업데이트 없을 경우 이유"
                }
            },
            "required": ["summary"]
        }
    }
]


# ── API 호출 재시도 헬퍼 ────────────────────────────
def call_api_with_retry(client, log_fn=None, **kwargs):
    """Rate limit(429) 발생 시 최대 3번 재시도합니다."""
    def log(msg):
        print(msg)
        if log_fn:
            log_fn(msg, "info")

    max_retries = 3
    wait_time   = 60  # 첫 대기: 60초

    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError as e:
            if attempt >= max_retries:
                raise
            log(f"⏳ API 속도 제한 도달 — {wait_time}초 후 재시도... ({attempt+1}/{max_retries})")
            time.sleep(wait_time)
            wait_time = min(wait_time * 2, 300)  # 최대 5분 대기
        except anthropic.APIStatusError as e:
            if e.status_code == 429:
                if attempt >= max_retries:
                    raise
                log(f"⏳ API 속도 제한 도달 — {wait_time}초 후 재시도... ({attempt+1}/{max_retries})")
                time.sleep(wait_time)
                wait_time = min(wait_time * 2, 300)
            else:
                raise


# ── 도구 실행 함수 ──────────────────────────────────
def execute_tool(name: str, inputs: dict) -> str:

    if name == "web_search":
        query = inputs["query"]
        max_results = min(inputs.get("max_results", 3), 3)  # 최대 3개로 제한
        print(f"  🔍 검색 중: {query}")

        def _ddgs_search(q, mr, timelimit=None):
            """DuckDuckGo 검색 — 실패 시 재시도"""
            for attempt in range(3):
                try:
                    time.sleep(2 + attempt * 2)  # 2초, 4초, 6초 간격
                    results = []
                    kwargs = {"max_results": mr}
                    if timelimit:
                        kwargs["timelimit"] = timelimit
                    with DDGS() as ddgs:
                        for r in ddgs.text(q, **kwargs):
                            results.append({
                                "title": r.get("title", ""),
                                "body":  r.get("body", ""),
                                "href":  r.get("href", ""),
                                "date":  r.get("published", "")
                            })
                    if results:
                        return results
                except Exception as e:
                    print(f"    검색 재시도 {attempt+1}/3: {e}")
                    if attempt == 2:
                        raise
            return []

        try:
            # 최근 1개월 시도
            results = _ddgs_search(query, max_results, timelimit='m')
            # 결과 없으면 3개월로 재시도
            if not results:
                results = _ddgs_search(query, max_results, timelimit='m3')
            # 그래도 없으면 timelimit 없이
            if not results:
                results = _ddgs_search(query, max_results)
            return json.dumps(results, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"검색 실패: {str(e)}"

    elif name == "read_file":
        file_key = inputs["file_key"]
        path = FILES.get(file_key)
        print(f"  📖 파일 읽기: {path}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            # 토큰 절약: 앞 5000자만 전달
            if len(content) > FILE_READ_LIMIT:
                return content[:FILE_READ_LIMIT] + "\n\n... (이하 생략. patch_file 사용 시 정확한 텍스트를 이 앞부분에서 찾으세요)"
            return content
        except FileNotFoundError:
            return f"파일 없음: {path}"
        except Exception as e:
            return f"파일 읽기 오류: {str(e)}"

    elif name == "patch_file":
        file_key = inputs["file_key"]
        old_text = inputs["old_text"]
        new_text = inputs["new_text"]
        reason   = inputs.get("reason", "알고리즘 업데이트 반영")
        path = FILES.get(file_key)
        print(f"  🔧 파일 패치: {path}")
        print(f"     이유: {reason}")
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if old_text not in content:
                return f"패치 실패: 찾는 텍스트가 없어요. 파일에서 정확한 텍스트를 확인 후 다시 시도하세요."
            # 백업
            with open(path + ".bak", "w", encoding="utf-8") as f:
                f.write(content)
            # 교체
            new_content = content.replace(old_text, new_text, 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            return f"패치 완료: {path} ({len(old_text)}자 → {len(new_text)}자)"
        except FileNotFoundError:
            return f"파일 없음: {path}"
        except Exception as e:
            return f"패치 오류: {str(e)}"

    elif name == "write_file":
        file_key = inputs["file_key"]
        content  = inputs.get("content", "")
        if not content:
            return "오류: content가 비어있어요. 큰 파일은 write_file 대신 patch_file을 사용하세요."
        reason   = inputs.get("reason", "알고리즘 업데이트 반영")
        path = FILES.get(file_key)
        print(f"  ✏️  파일 수정: {path}")
        print(f"     이유: {reason}")

        # 백업 먼저
        backup_path = path + ".bak"
        try:
            with open(path, "r", encoding="utf-8") as f:
                original = f.read()
            with open(backup_path, "w", encoding="utf-8") as f:
                f.write(original)
        except Exception:
            pass

        # 저장
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"저장 완료: {path}"
        except Exception as e:
            return f"파일 저장 오류: {str(e)}"

    elif name == "report":
        return "보고 완료"

    return f"알 수 없는 도구: {name}"


# ── 에이전트 메인 루프 ──────────────────────────────
def run_agent():
    if not API_KEY:
        print("❌ ANTHROPIC_API_KEY가 없어요. .env 파일을 확인해주세요.")
        return

    client = anthropic.Anthropic(api_key=API_KEY)
    today  = datetime.now().strftime("%Y.%m.%d")

    system_prompt = SYSTEM_PROMPT.format(today=today)

    messages = [{
        "role": "user",
        "content": USER_PROMPT.format(today=today, queries=chr(10).join('- ' + q for q in SEARCH_QUERIES))
    }]

    print(f"\n{'='*50}")
    print(f"  🤖 AlgoChiri 시작 — {today}")
    print(f"{'='*50}\n")

    final_report = None

    # 에이전트 루프
    while True:
        response = call_api_with_retry(
            client,
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        content_blocks = list(response.content)

        # assistant 메시지 dict 직렬화 후 저장
        assistant_blocks = []
        for block in content_blocks:
            if block.type == "text":
                assistant_blocks.append({"type": "text", "text": block.text})
                print(f"\n🤖 {block.text}\n")
            elif block.type == "tool_use":
                assistant_blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input
                })
        messages.append({"role": "assistant", "content": assistant_blocks})

        # tool_use 블록만 추출 (stop_reason 대신 직접 판단)
        tool_use_blocks = [b for b in content_blocks if b.type == "tool_use"]

        if tool_use_blocks:
            tool_results = []
            for block in tool_use_blocks:
                print(f"\n⚙️  도구 실행: {block.name}")
                try:
                    result = execute_tool(block.name, block.input)
                    if block.name == "report":
                        final_report = block.input
                except Exception as e:
                    result = f"도구 실행 오류: {str(e)}"
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result)
                })
            messages.append({"role": "user", "content": tool_results})
        else:
            print("\n✅ 에이전트 작업 완료!")
            break

    # 최종 리포트 출력
    if final_report:
        print(f"\n{'='*50}")
        print("  📋 오늘의 업데이트 리포트")
        print(f"{'='*50}")
        print(f"\n{final_report.get('summary', '')}")
        updated = final_report.get("updated_files", [])
        if updated:
            print(f"\n수정된 파일: {', '.join(updated)}")
        no_update = final_report.get("no_update_reason", "")
        if no_update:
            print(f"\n업데이트 없음 이유: {no_update}")
        print(f"\n{'─'*50}")
        print("  ⚠️  해당 결과 값은 참고만 부탁드립니다.")
        print(f"{'─'*50}\n")


def _backup_all_files(log_fn=None):
    """실행 전 모든 대상 파일을 타임스탬프 백업으로 저장. 백업 경로 dict 반환."""
    import shutil
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backups = {}
    for key, path in FILES.items():
        if os.path.exists(path):
            bak_path = path + f".backup_{stamp}"
            shutil.copy2(path, bak_path)
            backups[key] = bak_path
            if log_fn:
                log_fn(f"💾 백업 완료: {os.path.basename(path)} → .backup_{stamp}", "info")
    return backups


def _restore_from_backup(backups, log_fn=None):
    """백업에서 원본 파일 복구."""
    import shutil
    for key, bak_path in backups.items():
        if os.path.exists(bak_path):
            original = FILES[key]
            shutil.copy2(bak_path, original)
            if log_fn:
                log_fn(f"♻️ 복구 완료: {os.path.basename(original)}", "info")


def _cleanup_backups(backups, log_fn=None):
    """성공 시 타임스탬프 백업 파일 삭제."""
    for key, bak_path in backups.items():
        if os.path.exists(bak_path):
            os.remove(bak_path)
    if log_fn and backups:
        log_fn("🗑️ 임시 백업 정리 완료", "info")


def run_agent_with_callback(log_fn=None):
    """웹앱에서 호출 — log_fn(msg, type)으로 실시간 로그 전달"""

    def log(msg, type="info"):
        print(msg)
        if log_fn:
            log_fn(msg, type)

    if not API_KEY:
        log("❌ ANTHROPIC_API_KEY가 없어요. .env 파일을 확인해주세요.", "error")
        return

    client = anthropic.Anthropic(api_key=API_KEY)
    today  = datetime.now().strftime("%Y.%m.%d")

    # ── 실행 전 전체 백업 ──────────────────────────
    log("💾 파일 백업 중...", "info")
    backups = _backup_all_files(log_fn)
    success = False

    # execute_tool에 log 연결
    def execute_tool_logged(name, inputs):
        if name == "web_search":
            log(f"🔍 검색: {inputs['query']}", "search")
        elif name == "read_file":
            log(f"📖 파일 읽기: {inputs['file_key']}", "file")
        elif name == "patch_file":
            log(f"🔧 파일 패치: {inputs['file_key']} — {inputs.get('reason','')}", "file")
        elif name == "write_file":
            log(f"✏️ 파일 수정: {inputs['file_key']} — {inputs.get('reason','')}", "file")
        elif name == "report":
            log(f"📋 리포트: {inputs.get('summary','')}", "success")
        return execute_tool(name, inputs)

    system_prompt = SYSTEM_PROMPT.format(today=today)

    messages = [{
        "role": "user",
        "content": USER_PROMPT.format(today=today, queries=chr(10).join('- ' + q for q in SEARCH_QUERIES))
    }]

    log(f"🤖 AlgoChiri 시작 — {today}", "success")

    try:
        turn = 0
        while turn < MAX_TURNS:
            turn += 1
            if turn >= MAX_TURNS:
                log(f"⚠️ 최대 턴({MAX_TURNS}회) 도달 — 강제 종료합니다.", "error")
                break
            response = call_api_with_retry(
                client,
                log_fn=log_fn,
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages
            )

            # content를 리스트로 확정 (SDK 객체 방지)
            content_blocks = list(response.content)

            # 텍스트 로그 출력
            for block in content_blocks:
                if block.type == "text" and block.text:
                    log(f"💬 {block.text[:200]}{'...' if len(block.text) > 200 else ''}", "info")

            # assistant 메시지 dict 직렬화 후 저장
            assistant_blocks = []
            for block in content_blocks:
                if block.type == "text":
                    assistant_blocks.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    assistant_blocks.append({
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })
            messages.append({"role": "assistant", "content": assistant_blocks})

            # tool_use 블록만 추출 (stop_reason 대신 직접 판단)
            tool_use_blocks = [b for b in content_blocks if b.type == "tool_use"]

            if tool_use_blocks:
                # tool_use 있으면 반드시 tool_result 추가 (짝 안 맞으면 API 400)
                tool_results = []
                for block in tool_use_blocks:
                    try:
                        result = execute_tool_logged(block.name, block.input)
                    except Exception as e:
                        log(f"⚠️ 도구 오류 ({block.name}): {str(e)}", "error")
                        result = f"도구 실행 오류: {str(e)}"
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })
                messages.append({"role": "user", "content": tool_results})
            else:
                # tool_use 없으면 작업 완료
                log("✅ 에이전트 작업 완료!", "success")
                log("─" * 50, "info")
                log("⚠️  해당 결과 값은 참고만 부탁드립니다.", "info")
                log("─" * 50, "info")
                success = True
                break

    except Exception as e:
        log(f"❌ 에이전트 오류 발생: {str(e)}", "error")
        # 실패 시 백업에서 복구
        if backups:
            log("♻️ 장애 감지 — 기존 버전으로 복구 중...", "error")
            _restore_from_backup(backups, log_fn)
            log("✅ 기존 버전 복구 완료! 파일이 손상되지 않았어요.", "success")
        raise  # app.py가 에러를 받을 수 있도록 다시 던지기
    finally:
        if success:
            # 성공 시 임시 백업 삭제
            _cleanup_backups(backups, log_fn)


if __name__ == "__main__":
    run_agent()
