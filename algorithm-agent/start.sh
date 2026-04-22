#!/bin/bash
# AlgoChiri 시작 스크립트 — launchd용 환경 설정 포함

# 스크립트 위치로 이동
cd "$(dirname "$0")"

# Python 패키지 경로 설정
export PYTHONPATH=/Users/kongsun-ikeompyuteo/Library/Python/3.9/lib/python/site-packages
export HOME=/Users/kongsun-ikeompyuteo

# .env에서 API 키 읽기
if [ -f ".env" ]; then
  export $(grep -v '^#' .env | xargs)
fi

# 포트가 사용 중이면 재시도 (launchd가 78 코드로 포기하지 않도록)
while true; do
  /usr/bin/python3 app.py
  EXIT_CODE=$?
  if [ $EXIT_CODE -eq 78 ] || [ $EXIT_CODE -eq 1 ]; then
    echo "포트 충돌 또는 오류 — 5초 후 재시도..."
    sleep 5
  else
    break
  fi
done
