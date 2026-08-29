import subprocess
from config.settings import Config
from src.agents.sync_agent import AutographSyncAgent
from src.core.vault import VaultManager

class AutographBackfillerAgent:
    def __init__(self):
        self.vault_manager = VaultManager()
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
                    print(f"    Processing: {message}")
                    self.vault_manager.write_project_note(git_root.name)
                    self.vault_manager.write_commit_note(
                        git_root.name, commit_hash, message, date_str[:10]
                    )
                    created_events += 1

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
