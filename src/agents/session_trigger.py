import os
import subprocess
import time
from pathlib import Path

class SessionTriggerAgent:
    """
    An agent that monitors the Git repository for 'commit' events.
    When a commit is detected, it triggers the SessionObserver to 
    synthesize the accumulated buffer.
    """
    def __init__(self, repo_path: str, trigger_callback):
        self.repo_path = Path(repo_path)
        self.trigger_callback = trigger_callback
        self._last_seen_commit = self._get_current_commit()
        self.is_running = False

    def _get_current_commit(self) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(self.repo_path), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception as e:
            print(f"❌ [SessionTrigger] Error getting current commit: {e}")
            return ""

    def start(self):
        self.is_running = True
        print(f"🚀 [SessionTrigger] Monitoring Git repository: {self.repo_path}")
        self._run_loop()

    def _run_loop(self):
        while self.is_running:
            current_commit = self._get_current_commit()
            if current_commit and current_commit != self._last_seen_commit:
                print(f"🔔 [SessionTrigger] New commit detected: {current_commit}")
                # Trigger the synthesis!
                self.trigger_callback(current_commit)
                self._last_seen_commit = current_commit
            
            time.sleep(5) # Check every 5 seconds

    def stop(self):
        self.is_running = False
        print("🛑 [SessionTrigger] Stopped.")

if __name__ == "__main__":
    # For testing purposes
    import sys
    def dummy_callback(commit_hash):
        print(f"🎉 [Test] Callback triggered for commit: {commit_hash}")
    
    # Assume we are in the repo root
    trigger = SessionTriggerAgent(repo_path=".", trigger_callback=dummy_callback)
    trigger.start()
    
try:
    pass
except KeyboardInterrupt:
    pass
