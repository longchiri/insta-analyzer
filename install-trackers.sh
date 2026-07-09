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
echo "🔴 [필수 1단계] 전체 디스크 접근 권한 (안 하면 'Operation not permitted' 로 전부 실패):"
echo "   시스템 설정 → 개인정보 보호 및 보안 → 전체 디스크 접근"
echo "   → '+' 눌러서 아래 파일을 추가하고 켜기:"
echo "      $PYTHON_PATH"
echo "   (Finder에서 Cmd+Shift+G 로 위 경로 붙여넣어 선택)"
echo "   ※ Desktop 폴더는 macOS 보호구역이라, 이 권한이 없으면 launchd가 스크립트를 못 엽니다."
echo ""
echo "🔎 [자가진단] 지금 트래커가 열리는지 즉시 확인:"
echo "   $PYTHON_PATH -c \"open('$SCRIPT_DIR/daangn_rank_tracker.py'); print('✅ 접근 OK')\""
echo "   → 'Operation not permitted' 가 뜨면 위 1단계를 먼저 하세요."
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
