import subprocess
import json
from config.settings import Config
from core.synthesizer import AutographSynthesizer
from core.vault import VaultManager

class AutographBackfillerAgent:
    def __init__(self):
        self.vault_manager = VaultManager()
        self.synthesizer = AutographSynthesizer()

    def run(self, search_dir, days=7):
        git_roots = self.vault_manager.find_all_git_roots(search_dir)
        
        if not git_roots:
            print(f"❌ No Git repositories found under {search_dir}")
            return

        print(f"\n✅ Total repositories identified: {len(git_roots)}")

        for git_root in git_roots:
            print(f"\n🚀 Processing Repository: {git_root.name}")
            
            git_cmd = [
                "git", "-C", str(git_root), 
                "log", f"--since={days} days ago", 
                "--pretty=format:%ad | %an | %s"
            ]
            
            try:
                result = subprocess.run(git_cmd, capture_output=True, text=True, check=True)
                logs = result.stdout.strip().split('\n')
                
                if not logs or (len(logs) == 1 and logs[0] == ''):
                    print(f"  ℹ️ No git logs found for {git_root.name} in this period.")
                    continue

                print(f"  Found {len(logs)} commits. Processing...")

                for line in logs:
                    if not line: continue
                    parts = line.split(" | ")
                    if len(parts) < 3: continue
                    
                    date_str, author, message = parts[0], parts[1], parts[2]
                    event_text = f"[{date_str}] {author} committed: {message}"
                    
                    print(f"    Processing: {message}")
                    
                    try:
                        knowledge_json_str = self.synthesizer.synthesize(event_text)
                        knowledge_data = json.loads(knowledge_json_str)
                        self.vault_manager.write_event(git_root.name, event_text, knowledge_data)
                    except Exception as e:
                        print(f"      Error during synthesis: {e}")

                print(f"  ✅ Done with {git_root.name}")

            except subprocess.CalledProcessError as e:
                print(f"  ❌ Error reading git logs for {git_root.name}: {e.stderr}")
            except Exception as e:
                print(f"  ❌ Unexpected error for {git_root.name}: {e}")

        print(f"\n✨ All tasks complete! Check your Obsidian Vault.")

if __name__ == "__main__":
    import sys
    search_path = sys.argv[1] if len(sys.argv) > 1 else Config.SEARCH_DIR
    agent = AutographBackfillerAgent()
    agent.run(search_path)
