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
import anthropic
from datetime import datetime
from ddgs import DDGS
from dotenv import load_dotenv

# .env 파일에서 API 키 로드
load_dotenv()

# ── 설정 ──────────────────────────────────────────
API_KEY = os.getenv("ANTHROPIC_API_KEY")

# 파일 경로 (이 스크립트 기준 상대경로)
FILES = {
    "insta": "../인스타 분석/insta-analyzer.html",
    "kakao": "../카카오 분석/kakao-analyzer.html",
    "hub":   "../hub.html",
}

# 로컬 파일 → GitHub 파일명 매핑
# 인스타그램 분석기는 GitHub에서 index.html로 배포됨
GITHUB_FILE_MAP = {
    "../인스타 분석/insta-analyzer.html": "../index.html",
    "../카카오 분석/kakao-analyzer.html": "../kakao-analyzer.html",
    "../hub.html": "../hub.html",
}

# 검색할 플랫폼별 키워드
SEARCH_QUERIES = [
    "인스타그램 알고리즘 업데이트 2025 2026",
    "카카오톡 오픈채팅 알고리즘 변경 2025",
    "당근마켓 모임 알고리즘 노출 2025",
    "소모임 문토 알고리즘 업데이트 2025",
]

# ── 공통 프롬프트 ─────────────────────────────────
SYSTEM_PROMPT = """
당신은 SNS·커뮤니티 알고리즘 전문 업데이트 에이전트 AlgoChiri입니다.
오늘 날짜: {today}

## 역할
1. 웹 검색으로 인스타그램·카카오톡 오픈채팅·당근마켓·소모임·문토의 최신 알고리즘 변경사항을 조사합니다.
2. 기존 HTML 분석기 파일을 읽고, 새로운 알고리즘 정보가 반영이 필요한지 판단합니다.
3. 업데이트가 필요하면 해당 분석기 파일을 수정합니다 (점수 로직, 팁 박스, 버전 번호 등).
4. 분석기 파일을 수정했으면 반드시 hub.html도 함께 수정합니다.
5. 작업 결과를 report 도구로 보고합니다.

## 파일 설명
- insta: 인스타그램 분석기 (insta-analyzer.html)
- kakao: 카카오 오픈채팅 분석기 (kakao-analyzer.html)
- hub: 메인 허브 페이지 (hub.html)

## ⚠️ hub.html 업데이트 현황 — 필수 규칙
분석기 파일(insta 또는 kakao)을 수정할 때마다 반드시 hub 파일도 수정해야 합니다.
hub.html 안에 아래 두 곳을 업데이트하세요:

1. 해당 카드의 버전 번호 (예: Ver 3.7 → Ver 3.8)
   - 인스타 카드: <span class="ver">Ver X.X</span>
   - 카카오 카드: <span class="ver">Ver X.X</span>

2. 업데이트 현황 로그 맨 위에 새 항목 추가:
   형식: <div class="log-row">
           <span class="log-date">{today}</span>
           <span class="log-text">
             <span class="badge b-insta">인스타 Ver X.X</span>변경 내용 요약
           </span>
         </div>
   - 인스타 뱃지: <span class="badge b-insta">인스타 Ver X.X</span>
   - 카카오 뱃지: <span class="badge b-kakao">카카오 Ver X.X</span>
   - 당근 뱃지:   <span class="badge b-daangn">당근 Ver X.X</span>
   - 전체 뱃지:   <span class="badge b-all">전체</span>

## 주의사항
- 검증된 최신 정보만 반영하세요 (루머 X).
- 파일 수정 시 기존 HTML 구조·CSS·기능을 절대 망가뜨리지 마세요.
- 큰 변화가 없으면 수정하지 않고 이유를 report에 적으세요.
""".strip()

USER_PROMPT = """
오늘({today}) 알고리즘 업데이트 점검을 시작해주세요.

순서:
1. 각 플랫폼 알고리즘 최신 정보 웹 검색
2. 기존 분석기 파일(insta, kakao) 내용 확인
3. 새 정보가 있으면 해당 분석기 파일 업데이트 (버전 올리기 포함)
4. 분석기를 수정했으면 hub 파일도 반드시 업데이트 (버전 번호 + 업데이트 현황 로그)
5. 결과 report

검색 키워드:
{queries}
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
                    "description": "파일 키 (insta / kakao / hub)",
                    "enum": ["insta", "kakao", "hub"]
                }
            },
            "required": ["file_key"]
        }
    },
    {
        "name": "write_file",
        "description": "HTML 파일을 업데이트합니다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_key": {
                    "type": "string",
                    "description": "파일 키 (insta / kakao / hub)",
                    "enum": ["insta", "kakao", "hub"]
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


# ── 도구 실행 함수 ──────────────────────────────────
def execute_tool(name: str, inputs: dict) -> str:

    if name == "web_search":
        query = inputs["query"]
        max_results = inputs.get("max_results", 5)
        print(f"  🔍 검색 중: {query}")
        try:
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "body":  r.get("body", ""),
                        "href":  r.get("href", "")
                    })
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
            # 너무 길면 앞부분만 전달 (토큰 절약)
            if len(content) > 12000:
                return content[:12000] + "\n\n... (이하 생략, 필요시 특정 섹션 요청)"
            return content
        except FileNotFoundError:
            return f"파일 없음: {path}"

    elif name == "write_file":
        file_key = inputs["file_key"]
        content  = inputs["content"]
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
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"저장 완료: {path}"

    elif name == "report":
        return "보고 완료"

    return f"알 수 없는 도구: {name}"


# ── 에이전트 메인 루프 ──────────────────────────────
def run_agent():
    if not API_KEY:
        print("❌ ANTHROPIC_API_KEY가 없어요. .env 파일을 확인해주세요.")
        return

    client = anthropic.Anthropic(api_key=API_KEY)
    today  = datetime.now().strftime("%m.%d")

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
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        # assistant 응답 저장
        messages.append({
            "role": "assistant",
            "content": response.content
        })

        # 텍스트 출력
        for block in response.content:
            if hasattr(block, "text") and block.text:
                print(f"\n🤖 {block.text}\n")

        # 종료 조건
        if response.stop_reason == "end_turn":
            print("\n✅ 에이전트 작업 완료!")
            break

        # 도구 실행
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"\n⚙️  도구 실행: {block.name}")
                    result = execute_tool(block.name, block.input)

                    # report 도구면 결과 저장
                    if block.name == "report":
                        final_report = block.input

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })

            messages.append({
                "role": "user",
                "content": tool_results
            })

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
        print()


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
    today  = datetime.now().strftime("%m.%d")

    # execute_tool에 log 연결
    def execute_tool_logged(name, inputs):
        if name == "web_search":
            log(f"🔍 검색: {inputs['query']}", "search")
        elif name == "read_file":
            log(f"📖 파일 읽기: {inputs['file_key']}", "file")
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

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8192,
            system=system_prompt,
            tools=tools,
            messages=messages
        )

        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if hasattr(block, "text") and block.text:
                log(f"💬 {block.text[:200]}{'...' if len(block.text) > 200 else ''}", "info")

        if response.stop_reason == "end_turn":
            log("✅ 에이전트 작업 완료!", "success")
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool_logged(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result)
                    })
            messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    run_agent()
