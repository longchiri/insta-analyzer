#!/bin/bash
# 당근·소모임·문토 '주간 추적' 자동 실행 일괄 설치
# 매주 월요일 새벽 시간차 실행 (소모임 1:00 · 문토 1:30 · 당근 3:00)
# 사용법:  cd ~/Desktop/longchiri && bash install-trackers.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "📂 위치: $SCRIPT_DIR"

PYTHON_PATH="$(which python3)"
if [ -z "$PYTHON_PATH" ]; then
  echo "❌ python3 을 찾을 수 없어요 ('which python3' 가 비어있음)"; exit 1
fi
echo "🐍 Python: $PYTHON_PATH"

mkdir -p "$HOME/Library/LaunchAgents"

install_one () {
  local NAME="$1"           # com.longchiri.xxx-tracker
  local SRC="$SCRIPT_DIR/$NAME.plist"
  local DEST="$HOME/Library/LaunchAgents/$NAME.plist"
  if [ ! -f "$SRC" ]; then
    echo "  ⚠ plist 없음: $SRC (건너뜀)"; return
  fi
  sed -e "s|TRACKER_PATH|$SCRIPT_DIR|g" -e "s|PYTHON_PATH|$PYTHON_PATH|g" "$SRC" > "$DEST"
  launchctl unload "$DEST" 2>/dev/null || true
  launchctl load "$DEST"
  echo "  ✅ 등록: $NAME"
}

echo ""
echo "── launchd 등록 ──"
install_one "com.longchiri.somoim-tracker"
install_one "com.longchiri.munto-tracker"
install_one "com.longchiri.munto-socialing-tracker"
install_one "com.longchiri.daangn-tracker"
install_one "com.longchiri.daangn-national"

echo ""
echo "──────────────────────────────────────────────"
echo "📌 밤에 맥을 자동으로 깨우려면 (한 번만, 비번 입력):"
echo "   sudo pmset repeat wakeorpoweron MTWRFSU 00:55:00"
echo "   (매일 0:55 기상 → 소모임 1:00 · 문토 1:30 · 당근 3:00 순서로 실행)"
echo ""
echo "🔌 노트북 뚜껑 열어두거나 충전기 연결 권장 (뚜껑 닫으면 절전)"
echo ""
echo "▶ 지금 수동 테스트:"
echo "   python3 somoim_tracker.py   (빠름)"
echo "   python3 munto_tracker.py    (빠름)"
echo "   python3 daangn_rank_tracker.py  (~3시간)"
echo ""
echo "🗑 해제하려면:"
echo "   for n in somoim munto daangn; do"
echo "     launchctl unload \$HOME/Library/LaunchAgents/com.longchiri.\$n-tracker.plist"
echo "     rm \$HOME/Library/LaunchAgents/com.longchiri.\$n-tracker.plist; done"
echo "   sudo pmset repeat cancel"
echo "──────────────────────────────────────────────"
