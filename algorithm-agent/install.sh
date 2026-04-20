#!/bin/bash
# =====================================================
# AlgoChiri 자동 시작 설치 스크립트
# 실행: bash install.sh
# =====================================================

echo ""
echo "======================================================"
echo "  🤖 AlgoChiri 자동 시작 설치"
echo "======================================================"
echo ""

# 현재 폴더 경로 자동 감지
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "📁 AlgoChiri 폴더: $SCRIPT_DIR"

# .env에서 API 키 읽기
ENV_FILE="$SCRIPT_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
  echo "❌ .env 파일이 없어요. API 키를 먼저 설정해주세요."
  exit 1
fi

API_KEY=$(grep "ANTHROPIC_API_KEY" "$ENV_FILE" | cut -d'=' -f2 | tr -d ' ')
if [ -z "$API_KEY" ]; then
  echo "❌ API 키가 .env 파일에 없어요."
  exit 1
fi
echo "✅ API 키 확인됨"

# python3 경로 확인
PYTHON_PATH=$(which python3)
echo "🐍 Python 경로: $PYTHON_PATH"

# plist 파일 생성 (경로 자동 치환)
PLIST_SRC="$SCRIPT_DIR/com.longchiri.algochiri.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.longchiri.algochiri.plist"

sed \
  -e "s|ALGOCHIRI_PATH|$SCRIPT_DIR|g" \
  -e "s|ALGOCHIRI_API_KEY|$API_KEY|g" \
  -e "s|/usr/bin/python3|$PYTHON_PATH|g" \
  "$PLIST_SRC" > "$PLIST_DEST"

echo "✅ plist 파일 설치됨: $PLIST_DEST"

# 기존 서비스 중지 후 재등록
launchctl unload "$PLIST_DEST" 2>/dev/null
launchctl load "$PLIST_DEST"

echo ""
echo "======================================================"
echo "  ✅ 설치 완료!"
echo ""
echo "  이제 맥을 켤 때마다 AlgoChiri가 자동으로 실행돼요."
echo "  브라우저에서 http://localhost:5000 으로 접속하세요."
echo ""
echo "  🛑 자동 시작 해제하려면:"
echo "  bash uninstall.sh"
echo "======================================================"
echo ""

# 브라우저 자동 열기
sleep 2
open http://localhost:5000
