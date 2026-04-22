"""
AlgoChiri Web App — Flask 서버
버튼 클릭 → 에이전트 실행 → 실시간 로그 → GitHub 자동 푸시
"""

import os
import json
import threading
import subprocess
from datetime import datetime
from flask import Flask, render_template, Response, jsonify, request
from algochiri import run_agent_with_callback

app = Flask(__name__)

# 전역 상태
agent_status = {"running": False, "logs": [], "done": False, "error": None}
log_lock = threading.Lock()


def add_log(msg, type="info"):
    with log_lock:
        agent_status["logs"].append({
            "time": None,  # 브라우저에서 로컬 시간으로 표시
            "msg": msg,
            "type": type  # info / success / error / search / file
        })


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run():
    """에이전트 실행"""
    if agent_status["running"]:
        return jsonify({"ok": False, "msg": "이미 실행 중이에요"})

    # 상태 초기화
    with log_lock:
        agent_status["running"] = True
        agent_status["done"] = False
        agent_status["error"] = None
        agent_status["logs"] = []

    auto_push = request.json.get("auto_push", True)

    def run_in_background():
        try:
            add_log("🤖 AlgoChiri 시작!", "success")
            run_agent_with_callback(add_log)

            if auto_push:
                add_log("📤 GitHub 푸시 중...", "info")
                push_result = git_push()
                if push_result["ok"]:
                    add_log(f"✅ GitHub 푸시 완료!", "success")
                else:
                    add_log(f"⚠️ GitHub 푸시 실패: {push_result['msg']}", "error")
            else:
                add_log("ℹ️ GitHub 푸시 건너뜀", "info")

            add_log("🎉 모든 작업 완료!", "success")

        except Exception as e:
            add_log(f"❌ 오류 발생: {str(e)}", "error")
            with log_lock:
                agent_status["error"] = str(e)
        finally:
            with log_lock:
                agent_status["running"] = False
                agent_status["done"] = True

    thread = threading.Thread(target=run_in_background)
    thread.daemon = True
    thread.start()

    return jsonify({"ok": True})


@app.route("/logs")
def logs():
    """Server-Sent Events — 실시간 로그 스트리밍"""
    def stream():
        sent = 0
        while True:
            with log_lock:
                current_logs = agent_status["logs"]
                running = agent_status["running"]
                done = agent_status["done"]

            # 새 로그 전송
            while sent < len(current_logs):
                log = current_logs[sent]
                yield f"data: {json.dumps(log, ensure_ascii=False)}\n\n"
                sent += 1

            # 완료 시 종료 신호
            if done and sent >= len(current_logs):
                yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
                break

            import time
            time.sleep(0.3)

    return Response(stream(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/status")
def status():
    return jsonify({
        "running": agent_status["running"],
        "done": agent_status["done"],
        "log_count": len(agent_status["logs"])
    })


def git_push():
    """GitHub에 자동 푸시"""
    try:
        today = datetime.now().strftime("%Y.%m.%d %H:%M")

        # 경로 설정
        agent_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.dirname(agent_dir)  # 상위 폴더 (git 루트)

        # ── push 대상 파일 목록 (base 기준 상대경로) ──
        target_files = [
            "index.html",           # 인스타그램 분석기
            "kakao-analyzer.html",  # 카카오 오픈채팅 분석기
            "daangn-analyzer.html", # 당근 모임 분석기
            "moim-analyzer.html",   # 소모임×문토 분석기
            "hub.html",             # 허브 메인
        ]

        # 존재하는 파일만 add
        existing = [f for f in target_files if os.path.exists(os.path.join(base, f))]
        if not existing:
            return {"ok": False, "msg": "push할 파일이 없어요"}

        # git add
        add_result = subprocess.run(
            ["git", "-C", base, "add"] + existing,
            capture_output=True, text=True
        )
        if add_result.returncode != 0:
            return {"ok": False, "msg": f"git add 실패: {add_result.stderr.strip()}"}

        # git commit
        commit_result = subprocess.run(
            ["git", "-C", base, "commit", "-m", f"AlgoChiri 자동 업데이트 — {today}"],
            capture_output=True, text=True
        )
        if commit_result.returncode != 0:
            out = commit_result.stdout + commit_result.stderr
            if "nothing to commit" in out:
                return {"ok": True, "msg": "변경사항 없음 (커밋 건너뜀)"}
            return {"ok": False, "msg": f"git commit 실패: {commit_result.stderr.strip()}"}

        # git push
        push_result = subprocess.run(
            ["git", "-C", base, "push"],
            capture_output=True, text=True
        )
        if push_result.returncode != 0:
            return {"ok": False, "msg": f"git push 실패: {push_result.stderr.strip()}"}

        return {"ok": True, "pushed": existing}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


if __name__ == "__main__":
    print("\n" + "="*45)
    print("  🤖 AlgoChiri Web App 시작!")
    print("  브라우저에서 http://localhost:5001 열기")
    print("="*45 + "\n")
    app.run(debug=False, port=5001, threaded=True)
