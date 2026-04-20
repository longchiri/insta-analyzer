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
            "time": datetime.now().strftime("%H:%M:%S"),
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
    """GitHub에 자동 푸시 (로컬 파일 → GitHub 파일명 매핑 포함)"""
    import shutil
    try:
        today = datetime.now().strftime("%Y.%m.%d %H:%M")

        # 경로 설정
        agent_dir = os.path.dirname(os.path.abspath(__file__))
        base = os.path.dirname(agent_dir)  # 상위 폴더 (git 루트)

        # ── 로컬 → GitHub 파일명 매핑 ──────────────────
        # 인스타그램 분석기는 GitHub에서 index.html
        file_map = {
            os.path.join(base, "인스타 분석", "insta-analyzer.html"): os.path.join(base, "index.html"),
            os.path.join(base, "카카오 분석", "kakao-analyzer.html"): os.path.join(base, "kakao-analyzer.html"),
            os.path.join(base, "hub.html"): os.path.join(base, "hub.html"),
        }

        # 파일 복사 (로컬 원본 → GitHub용 위치)
        copied = []
        for src, dst in file_map.items():
            if os.path.exists(src) and src != dst:
                shutil.copy2(src, dst)
                copied.append(os.path.basename(dst))

        # git 명령 실행
        cmds = [
            ["git", "-C", base, "add",
             "index.html", "kakao-analyzer.html", "hub.html"],
            ["git", "-C", base, "commit", "-m",
             f"AlgoChiri 자동 업데이트 — {today}"],
            ["git", "-C", base, "push"],
        ]

        for cmd in cmds:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                if "nothing to commit" in result.stdout + result.stderr:
                    return {"ok": True, "msg": "변경사항 없음 (커밋 건너뜀)"}
                return {"ok": False, "msg": result.stderr.strip()}

        return {"ok": True, "copied": copied}
    except Exception as e:
        return {"ok": False, "msg": str(e)}


if __name__ == "__main__":
    print("\n" + "="*45)
    print("  🤖 AlgoChiri Web App 시작!")
    print("  브라우저에서 http://localhost:5000 열기")
    print("="*45 + "\n")
    app.run(debug=False, port=5000, threaded=True)
