import datetime
import hashlib
import os
import json
from pathlib import Path
from config.settings import Config

class VaultManager:
    def __init__(self, vault_root=None):
        self.vault_root = vault_root or Config.VAULT_ROOT

    def _extract_entity_string(self, ent):
        """Helper to convert any entity type (str, dict, etc.) to a string."""
        if isinstance(ent, str):
            return ent
        elif isinstance(ent, dict):
            return ent.get('name') or ent.get('id') or str(ent)
        else:
            return str(ent)

    def find_all_git_roots(self, start_path):
        """Deep scan for Git repositories."""
        git_roots = []
        start_path_root = Path(start_path).resolve()
        print(f"🔍 Deep Scanning for Git repositories starting from: {start_path_root}")
        
        for root, dirs, files in os.walk(start_path_root):
            if ".git" in dirs:
                repo_path = Path(root)
                print(f"  ✨ Found Git Repository: {repo_path}")
                git_roots.append(repo_path)
                if ".git" in dirs:
                    dirs.remove(".git")
            
            if "node_modules" in dirs:
                dirs.remove("node_modules")
            if "__pycache__" in dirs:
                dirs.remove("__pycache__")

        return git_roots

    def write_event(self, project_name, message, data):
        """Writes a single historical event to the vault."""
        safe_project_name = project_name.replace(' ', '_').replace('/', '_').replace(':', '')
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        event_digest = hashlib.sha256(
            f"{message}{timestamp}".encode("utf-8")
        ).hexdigest()[:10]
        
        event_dir = self.vault_root / "projects" / safe_project_name / "events"
        event_dir.mkdir(parents=True, exist_ok=True)
        
        event_file = event_dir / f"backfill_{timestamp}_{event_digest}.md"
        
        content = f"# Historical Event\n\n**Source:** {message}\n\n## Extracted Data\n```json\n{json.dumps(data, indent=2)}\n```\n\n## Links\n"
        
        if "entities" in data and isinstance(data["entities"], list):
            for ent in data["entities"]:
                ent_str = self._extract_entity_string(ent)
                if ent_str:
                    content += f"- [[{ent_str}]]\n"

        with open(event_file, "w") as f:
            f.write(content)

        # Update Entity Files
        if "entities" in data and isinstance(data["entities"], list):
            entity_dir = self.vault_root / "projects" / safe_project_name / "entities"
            entity_dir.mkdir(parents=True, exist_ok=True)
            for ent in data["entities"]:
                ent_str = self._extract_entity_string(ent)
                    
                if ent_str:
                    safe_ent_name = ent_str.replace(' ', '_').replace('/', '_').replace(' .', '').replace(':', '').replace(' ', '_')
                    # Clean up name for filename
                    safe_ent_name = "".join(c for c in safe_ent_name if c.isalnum() or c in ('_', '-'))
                    
                    ent_file = entity_dir / f"{safe_ent_name}.md"
                    with open(ent_file, "a") as f:
                        f.write(f"\n- Observed in history on {datetime.datetime.now().strftime('%Y-%m-%d')}")
        return True

    def write_commit_note(self, project_name, commit_id, title, date):
        """Create or update a stable note for a Git commit."""
        safe_project_name = project_name.replace(" ", "_").replace("/", "_").replace(":", "")
        safe_commit_id = "".join(
            character for character in commit_id if character.isalnum()
        )
        commit_dir = self.vault_root / "projects" / safe_project_name / "commits"
        commit_dir.mkdir(parents=True, exist_ok=True)
        commit_file = commit_dir / f"{safe_commit_id}.md"
        commit_file.write_text(
            f"# {safe_commit_id[:12]} {title}\n\n"
            f"- **Commit:** `{safe_commit_id}`\n"
            f"- **Date:** {date}\n"
            f"- **Project:** [[projects/{safe_project_name}|{project_name}]]\n"
            f"- **Related daily note:** [[daily_notes/{date}|{date}]]\n",
            encoding="utf-8",
        )

    def write_project_note(self, project_name):
        """Create a stable project hub for daily and commit note links."""
        safe_project_name = project_name.replace(" ", "_").replace("/", "_").replace(":", "")
        project_file = self.vault_root / "projects" / f"{safe_project_name}.md"
        if project_file.exists():
            return
        project_file.write_text(
            f"# {project_name}\n\n"
            f"- **Commits:** [[projects/{safe_project_name}/commits]]\n"
            f"- **Events:** [[projects/{safe_project_name}/events]]\n",
            encoding="utf-8",
        )

    def find_recent_events(self):
        """Helper for Daily Summary Agent to find events from the last 24 hours."""
        recent_events = []
        now = datetime.datetime.now()
        yesterday = now - datetime.timedelta(days=1)

        projects_path = self.vault_root / "projects"
        if not projects_path.exists():
            return []

        for project_dir in projects_path.iterdir():
            if project_dir.is_dir():
                event_dir = project_dir / "events"
                if event_dir.exists():
                    for event_file in event_dir.glob("*.md"):
                        mtime = datetime.datetime.fromtimestamp(event_file.stat().st_mtime)
                        if mtime > yesterday:
                            try:
                                with open(event_file, 'r') as f:
                                    content = f.read()
                                    recent_events.append(f"File: {event_file.name}\nContent: {content}")
                            except Exception:
                                pass
        return recent_events
