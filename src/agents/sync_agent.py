import subprocess
from datetime import datetime
from pathlib import Path

class AutographSyncAgent:
    def __init__(self, vault_root: Path):
        self.vault_root = vault_root

    def sync(self):
        """
        Commits and pushes Markdown changes without staging unrelated vault files.
        """
        print(f"🔄 Starting Vault synchronization in: {self.vault_root}")

        if not (self.vault_root / ".git").exists():
            print(f"❌ Error: {self.vault_root} is not a Git repository. Please run 'git init' in your vault.")
            return False

        try:
            print("  📥 Pulling latest changes from remote...")
            subprocess.run(
                ["git", "-C", str(self.vault_root), "pull", "--rebase"],
                check=True,
                capture_output=True,
                text=True,
            )

            print("  ➕ Staging Markdown changes...")
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.vault_root),
                    "add",
                    "--all",
                    "--",
                    ":(glob)**/*.md",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            staged_changes = subprocess.run(
                ["git", "-C", str(self.vault_root), "diff", "--cached", "--quiet"],
                capture_output=True,
                text=True,
            )
            if staged_changes.returncode == 0:
                print("  ℹ️ No Markdown changes to commit in the vault.")
                return True
            if staged_changes.returncode != 1:
                raise subprocess.CalledProcessError(
                    staged_changes.returncode,
                    staged_changes.args,
                    staged_changes.stdout,
                    staged_changes.stderr,
                )

            commit_msg = (
                "Autograph: sync Markdown "
                f"({datetime.now().astimezone().isoformat(timespec='seconds')})"
            )
            subprocess.run(
                ["git", "-C", str(self.vault_root), "commit", "-m", commit_msg],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"  ✅ Committed: {commit_msg}")

            print("  📤 Pushing changes to remote...")
            subprocess.run(
                ["git", "-C", str(self.vault_root), "push"],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"✨ Vault sync successful!")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Git Error during sync: {e.stderr}")
            return False
        except OSError as error:
            print(f"❌ Could not run Git during sync: {error}")
            return False

if __name__ == "__main__":
    # Testing the sync agent manually
    from config.settings import Config
    agent = AutographSyncAgent(Config.VAULT_ROOT)
    agent.sync()
