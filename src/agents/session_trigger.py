import os
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, List

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


class MultiRepositorySessionTriggerAgent:
    """Monitors the latest commit in every repository under a search directory."""

    def __init__(
        self,
        search_dir: Path,
        trigger_callback: Callable[[str, Path], None],
        interval_seconds: int = 5,
    ):
        self.search_dir = Path(search_dir)
        self.trigger_callback = trigger_callback
        self.interval_seconds = interval_seconds
        self._last_seen_commits = self._current_commits()
        self.is_running = False

    def _repositories(self) -> List[Path]:
        if not self.search_dir.exists():
            print(f"⚠️ [SessionTrigger] Search directory does not exist: {self.search_dir}")
            return []

        repositories = []
        for root, directories, _ in os.walk(self.search_dir):
            if ".git" in directories:
                repositories.append(Path(root))
                directories.remove(".git")
            directories[:] = [
                directory
                for directory in directories
                if directory not in {"node_modules", "__pycache__", ".venv"}
            ]
        return repositories

    @staticmethod
    def _current_commit(repository: Path) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(repository), "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""

    def _current_commits(self) -> Dict[Path, str]:
        return {
            repository: commit
            for repository in self._repositories()
            if (commit := self._current_commit(repository))
        }

    def start(self) -> None:
        self.is_running = True
        print(
            f"🚀 [SessionTrigger] Monitoring repositories under: {self.search_dir}"
        )
        while self.is_running:
            current_commits = self._current_commits()
            for repository, commit_hash in current_commits.items():
                if previous_hash := self._last_seen_commits.get(repository):
                    if commit_hash != previous_hash:
                        print(
                            f"🔔 [SessionTrigger] New commit in {repository.name}: "
                            f"{commit_hash}"
                        )
                        self.trigger_callback(commit_hash, repository)
            self._last_seen_commits = current_commits
            time.sleep(self.interval_seconds)

    def stop(self) -> None:
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
