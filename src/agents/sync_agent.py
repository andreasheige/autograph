import subprocess
from pathlib import Path
import os

class AutographSyncAgent:
    def __init__(self, vault_root: Path):
        self.vault_root = vault_root

    def sync(self):
        """
        Performs a safe git sync: pull, add, commit, and push.
        """
        print(f"🔄 Starting Vault synchronization in: {self.vault_root}")
        
        if not (self.vault_root / ".git").exists():
            print(f"❌ Error: {self.vault_root} is not a Git repository. Please run 'git init' in your vault.")
            return False

        try:
            # 1. Git Pull (to prevent conflicts from other devices)
            print("  📥 Pulling latest changes from remote...")
            subprocess.run(["git", "-C", str(self.vault_root), "pull", "--rebase"], 
                           check=True, capture_output=True, text=True)

            # 2. Git Add
            print("  ➕ Staging changes...")
            subprocess.run(["git", "-C", str(self.vault_root), "add", "."], 
                           check=True, capture_output=True, text=True)

            # 3. Git Commit
            # We use a custom message. We check if there are changes to avoid error on empty commit.
            print("  📝 Checking for new changes to commit...")
            status = subprocess.run(["git", "-C", str(self.vault_root), "status", "--porcelain"], 
                                    check=True, capture_output=True, text=True).stdout
            
            if not status.strip():
                print("  ℹ️ No new changes to commit in the vault.")
                return True

            commit_msg = f"Autograph: Automated daily sync ({subprocess.run(['date'] , capture_output=True, text=True).stdout.strip()})"
            subprocess.run(["git", "-C", str(self.vault_root), "commit", "-m", commit_msg], 
                           check=True, capture_output=True, text=True)
            print(f"  ✅ Committed: {commit_msg}")

            # 4. Git Push
            print("  📤 Pushing changes to remote...")
            subprocess.run(["git", "-C", str(self.vault_root), "push"], 
                           check=True, capture_output=True, text=True)
            
            print(f"✨ Vault sync successful!")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Git Error during sync: {e.stderr}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during sync: {e}")
            return False

if __name__ == "__main__":
    # Testing the sync agent manually
    from config.settings import Config
    agent = AutographSyncAgent(Config.VAULT_ROOT)
    agent.sync()
