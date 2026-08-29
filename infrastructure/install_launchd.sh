#!/bin/bash

set -euo pipefail

label_prefix="com.autograph"
launch_agents_dir="$HOME/Library/LaunchAgents"
log_dir="$HOME/.autograph/logs"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_executable="$(command -v python3)"
user_id="$(id -u)"
domain="gui/$user_id"

if [ -z "$python_executable" ]; then
    echo "python3 is required but was not found on PATH." >&2
    exit 1
fi

mkdir -p "$launch_agents_dir" "$log_dir"

write_observer_plist() {
    cat > "$launch_agents_dir/$label_prefix.observer.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label_prefix.observer</string>
  <key>ProgramArguments</key>
  <array>
    <string>$python_executable</string>
    <string>-u</string>
    <string>-m</string>
    <string>src.agents.session_observer_daemon</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$repo_root</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>ThrottleInterval</key>
  <integer>30</integer>
  <key>StandardOutPath</key>
  <string>$log_dir/session_observer.out.log</string>
  <key>StandardErrorPath</key>
  <string>$log_dir/session_observer.err.log</string>
</dict>
</plist>
EOF
}

write_summary_plist() {
    cat > "$launch_agents_dir/$label_prefix.summary.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$label_prefix.summary</string>
  <key>ProgramArguments</key>
  <array>
    <string>$python_executable</string>
    <string>-u</string>
    <string>run_summary.py</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$repo_root</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>8</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>$log_dir/summary.out.log</string>
  <key>StandardErrorPath</key>
  <string>$log_dir/summary.err.log</string>
</dict>
</plist>
EOF
}

load_agent() {
    local label="$1"
    local plist_path="$launch_agents_dir/$label.plist"

    launchctl bootout "$domain/$label" 2>/dev/null || true
    launchctl bootstrap "$domain" "$plist_path"
}

write_observer_plist
write_summary_plist
plutil -lint "$launch_agents_dir/$label_prefix.observer.plist" >/dev/null
plutil -lint "$launch_agents_dir/$label_prefix.summary.plist" >/dev/null
load_agent "$label_prefix.observer"
load_agent "$label_prefix.summary"

echo "Autograph observer starts at login; the daily summary runs at 08:00."
echo "Logs: $log_dir"
