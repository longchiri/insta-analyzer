#!/bin/bash
# 당근 노출순위 '주간 추적' 자동 실행 설치 (매주 월 새벽 3시)
# 사용법:  cd ~/Desktop/longchiri && bash install-tracker.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "📂 위치: $SCRIPT_DIR"

# 1) python3 경로 자동 감지 (크롤러를 돌리는 그 python)
PYTHON_PATH="$(which python3)"
if [ -z "$PYTHON_PATH" ]; then
  echo "❌ python3 을 찾을 수 없어요. 'which python3' 가 비어있어요."; exit 1
fi
echo "🐍 Python: $PYTHON_PATH"

# 2) plist 생성 (경로 자동 치환)
PLIST_SRC="$SCRIPT_DIR/com.longchiri.daangn-tracker.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.longchiri.daangn-tracker.plist"
mkdir -p "$HOME/Library/LaunchAgents"
sed -e "s|TRACKER_PATH|$SCRIPT_DIR|g" \
    -e "s|PYTHON_PATH|$PYTHON_PATH|g" \
    "$PLIST_SRC" > "$PLIST_DEST"
echo "📄 등록 파일: $PLIST_DEST"

# 3) launchd 등록
launchctl unload "$PLIST_DEST" 2>/dev/null || true
launchctl load "$PLIST_DEST"
echo "✅ 매주 월요일 새벽 3시 자동 실행 등록 완료"
echo ""
echo "──────────────────────────────────────────────"
echo "📌 밤에 맥을 자동으로 깨우려면 (한 번만, 비번 입력):"
echo "   sudo pmset repeat wakeorpoweron MTWRFSU 02:55:00"
echo "   (매일 2:55 기상 → 3:00 크롤 → 끝나면 다시 절전)"
echo ""
echo "🔌 노트북은 뚜껑 열어두거나 충전기 연결 권장 (뚜껑 닫으면 절전)"
echo ""
echo "▶ 지금 바로 한 번 테스트:"
echo "   cd $SCRIPT_DIR && python3 daangn_rank_tracker.py"
echo ""
echo "🗑 나중에 해제하려면:"
echo "   launchctl unload $PLIST_DEST && rm $PLIST_DEST"
echo "   sudo pmset repeat cancel"
echo "──────────────────────────────────────────────"
