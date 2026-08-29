#!/bin/bash

set -euo pipefail

launch_agents_dir="$HOME/Library/LaunchAgents"
user_id="$(id -u)"
domain="gui/$user_id"

for label in com.autograph.observer com.autograph.summary; do
    launchctl bootout "$domain/$label" 2>/dev/null || true
    rm -f "$launch_agents_dir/$label.plist"
done

echo "Autograph launch agents removed."
