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
    f"인스타그램 릴스 피드 알고리즘 변경 최신 {_year}",
    f"instagram algorithm update latest {_year}",
    f"카카오톡 오픈채팅 알고리즘 최신 변경 {_year}",
    f"당근마켓 소모임 문토 알고리즘 최신 {_year}",
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
- insta:   인스타그램 분석기 (index.html)
- kakao:   카카오 오픈채팅 분석기 (kakao-analyzer.html)
- daangn:  당근 모임 분석기 (daangn-analyzer.html)
- moim:    소모임×문토 분석기 (moim-analyzer.html)
- hub:     메인 허브 페이지 (hub.html)

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

## 파일 수정 방법 — 중요!
- insta·kakao 파일은 매우 큽니다 (100KB+). **절대 write_file로 전체를 다시 쓰지 마세요.**
- 반드시 **patch_file**을 사용해 수정이 필요한 부분만 교체하세요.
- 예: 점수 계산식 한 줄, 팁 텍스트 한 문단, 버전 번호 한 곳만 바꾸기
- hub.html은 작으므로 write_file 사용 가능합니다.

## 주의사항
- 오늘은 {today}입니다. 반드시 이 날짜 기준 최신 정보를 사용하세요.
- 검색 결과의 날짜를 반드시 확인하세요. 오래된 정보(6개월 이상)는 무시하세요.
- 같은 주제 검색 결과 중 가장 최근 날짜 기준으로 판단하세요.
- 검색 결과가 부족하면 영어 키워드로 추가 검색하세요 (예: "instagram algorithm {today} latest").
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
        max_results = inputs.get("max_results", 5)
        print(f"  🔍 검색 중: {query}")
        try:
            results = []
            with DDGS() as ddgs:
                # timelimit='m' = 최근 1개월 이내 결과만
                for r in ddgs.text(query, max_results=max_results, timelimit='m'):
                    results.append({
                        "title": r.get("title", ""),
                        "body":  r.get("body", ""),
                        "href":  r.get("href", ""),
                        "date":  r.get("published", "")
                    })
            # 최근 1개월 결과가 없으면 3개월로 재시도
            if not results:
                with DDGS() as ddgs:
                    for r in ddgs.text(query, max_results=max_results, timelimit='m3'):
                        results.append({
                            "title": r.get("title", ""),
                            "body":  r.get("body", ""),
                            "href":  r.get("href", ""),
                            "date":  r.get("published", "")
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
        print()


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
        while True:
            response = call_api_with_retry(
                client,
                log_fn=log_fn,
                model="claude-sonnet-4-6",
                max_tokens=8192,
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
