#!/bin/bash
# 매일 오전 7시 자동 실행 등록 (동료 Mac용) — 실행: bash install_autorun.sh
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
LABEL="com.morningbrief.daily"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$DIR/venv/bin/python3</string>
    <string>$DIR/main.py</string>
  </array>
  <key>WorkingDirectory</key><string>$DIR</string>
  <key>StartCalendarInterval</key>
  <dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>0</integer></dict>
  <key>RunAtLoad</key><false/>
  <key>StandardOutPath</key><string>$DIR/logs/launchd_out.log</string>
  <key>StandardErrorPath</key><string>$DIR/logs/launchd_err.log</string>
</dict>
</plist>
EOF

launchctl bootout gui/$(id -u)/$LABEL 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$PLIST"
echo "✅ 등록 완료 (매일 오전 7시). 확인:  launchctl list | grep morningbrief"
echo "지금 강제 테스트:  launchctl kickstart -k gui/$(id -u)/$LABEL"
