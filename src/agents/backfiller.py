import subprocess
import json
from config.settings import Config
from src.agents.sync_agent import AutographSyncAgent
from src.core.synthesizer import Synthesizer
from src.core.vault import VaultManager

class AutographBackfillerAgent:
    def __init__(self):
        self.vault_manager = VaultManager()
        self.synthesizer = Synthesizer()
        self.sync_agent = AutographSyncAgent(self.vault_manager.vault_root)

    def run(self, search_dir, days=7):
        git_roots = self.vault_manager.find_all_git_roots(search_dir)
        
        if not git_roots:
            print(f"❌ No Git repositories found under {search_dir}")
            return

        print(f"\n✅ Total repositories identified: {len(git_roots)}")

        created_events = 0
        for git_root in git_roots:
            print(f"\n🚀 Processing Repository: {git_root.name}")
            
            git_log_cmd = [
                "git", "-C", str(git_root),
                "log", f"--since={days} days ago",
                "--date=iso-strict",
                "--pretty=format:%H%x00%ad%x00%an%x00%s%x00",
            ]

            try:
                result = subprocess.run(git_log_cmd, capture_output=True, text=True, check=True)
                fields = result.stdout.split("\0")
                commits = [
                    fields[index:index + 4]
                    for index in range(0, len(fields) - 1, 4)
                    if len(fields[index:index + 4]) == 4
                ]

                if not commits:
                    print(f"  ℹ️ No git logs found for {git_root.name} in this period.")
                    continue

                print(f"  Found {len(commits)} commits. Processing...")

                for commit_hash, date_str, author, message in commits:
                    git_show_cmd = ["git", "-C", str(git_root), "show", "--name-only", "--format=", commit_hash]
                    files_result = subprocess.run(
                        git_show_cmd, capture_output=True, text=True, check=True
                    )
                    changed_files = [
                        path for path in files_result.stdout.splitlines() if path.strip()
                    ]
                    event_text = (
                        f"[{date_str}] {author} committed {commit_hash[:12]}: {message}\n"
                        f"Changed files:\n" + "\n".join(f"- {path}" for path in changed_files)
                    )

                    print(f"    Processing: {message}")
                    try:
                        knowledge_data = json.loads(self.synthesizer.synthesize(event_text))
                        self.vault_manager.write_event(git_root.name, event_text, knowledge_data)
                        created_events += 1
                    except (json.JSONDecodeError, RuntimeError) as error:
                        print(f"      ❌ Synthesis failed: {error}")

            except subprocess.CalledProcessError as e:
                print(f"  ❌ Error reading git logs for {git_root.name}: {e.stderr}")

        print(f"\n✨ All tasks complete! Check your Obsidian Vault.")
        if created_events:
            self.sync_agent.sync()

if __name__ == "__main__":
    import sys
    search_path = sys.argv[1] if len(sys.argv) > 1 else Config.SEARCH_DIR
    agent = AutographBackfillerAgent()
    agent.run(search_path)
