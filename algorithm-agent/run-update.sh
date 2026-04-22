#!/bin/bash
# =====================================================
# AlgoChiri 알고리즘 자동 업데이트 실행 스크립트
# LaunchAgent(com.longchiri.algochiri-update.plist)에 의해 매주 월요일 9시 자동 실행
# =====================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "======================================================"
echo "  🤖 AlgoChiri 자동 업데이트 시작: $(date '+%Y-%m-%d %H:%M:%S')"
echo "======================================================"

# .env에서 API 키 로드
if [ -f "$SCRIPT_DIR/.env" ]; then
  export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
fi

# python3 경로 (Homebrew 포함)
PYTHON_PATH=$(which python3 || echo "/usr/bin/python3")
echo "🐍 Python: $PYTHON_PATH"

# algochiri.py 실행
cd "$SCRIPT_DIR"
"$PYTHON_PATH" algochiri.py

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
  echo "✅ AlgoChiri 완료: $(date '+%Y-%m-%d %H:%M:%S')"
else
  echo "❌ AlgoChiri 오류 (exit $EXIT_CODE): $(date '+%Y-%m-%d %H:%M:%S')"
fi
