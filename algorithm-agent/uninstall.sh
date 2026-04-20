#!/bin/bash
# AlgoChiri 자동 시작 해제

PLIST="$HOME/Library/LaunchAgents/com.longchiri.algochiri.plist"

launchctl unload "$PLIST" 2>/dev/null
rm -f "$PLIST"

echo "✅ AlgoChiri 자동 시작이 해제됐어요."
