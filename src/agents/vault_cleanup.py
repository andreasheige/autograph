import json
import re
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from config.settings import Config
from src.agents.daily_backfiller import DailyBackfillAgent
from src.agents.sync_agent import AutographSyncAgent

# Never looked into: Obsidian's own state, the wiki (its own repo and owner),
# and generated graph output, which is ignored rather than deleted.
SKIPPED_DIRS = {".git", ".obsidian", ".trash", "wiki", "graphify-out"}
PLACEHOLDER_SUFFIXES = {".md", ".canvas", ".base"}
# What Obsidian writes for "New base" before anything is configured.
DEFAULT_BASE = "views:\n  - type: table\n    name: View"
SOURCE_PATTERN = re.compile(r"^\*\*Source:\*\* \[[^\]]*\] .+? committed: (.+)$", re.M)
OBSERVED_LINE = "- Observed in history on "


class VaultCleanupAgent:
    """Remove vault files that hold nothing a person would miss.

    A file goes only when a rule can say why it has no value: it is empty, it
    is an untouched Obsidian placeholder, or everything in it still exists
    elsewhere (a commit subject in its repository's history, a session
    fragment the daily notes replaced). An empty folder goes too. Anything else stays, and the vault's
    git history keeps every removed file recoverable.
    """

    def __init__(self, vault_root: Path = None, search_dirs: Iterable[Path] = None):
        self.vault_root = Path(vault_root or Config.VAULT_ROOT)
        self.search_dirs = search_dirs if search_dirs is not None else Config.SEARCH_DIRS
        self.sync_agent = AutographSyncAgent(self.vault_root)
        self._subjects: Dict[str, Optional[Set[str]]] = {}
        self._repositories: Optional[Dict[str, Path]] = None

    def _paths(self) -> Iterable[Path]:
        for path in sorted(self.vault_root.rglob("*")):
            if not SKIPPED_DIRS.intersection(path.relative_to(self.vault_root).parts):
                yield path

    def _empty_folders(self, removed: Set[Path]) -> List[Path]:
        """Folders holding nothing once `removed` is gone, deepest first."""
        empty: Set[Path] = set()
        folders = [path for path in self._paths() if path.is_dir()]
        for folder in sorted(folders, key=lambda path: len(path.parts), reverse=True):
            if all(child in removed or child in empty for child in folder.iterdir()):
                empty.add(folder)
        return sorted(empty, key=lambda path: len(path.parts), reverse=True)

    @staticmethod
    def _placeholder(path: Path, text: str) -> Optional[str]:
        if path.suffix not in PLACEHOLDER_SUFFIXES:
            return None
        if not text.strip():
            return "empty file"
        if path.suffix == ".canvas":
            try:
                canvas = json.loads(text)
            except json.JSONDecodeError:
                return None
            if isinstance(canvas, dict) and not any(canvas.values()) and set(canvas) <= {"nodes", "edges"}:
                return "empty canvas"
        if path.suffix == ".base" and text.strip() == DEFAULT_BASE:
            return "unconfigured base"
        return None

    def _commit_subjects(self, project: str) -> Optional[Set[str]]:
        if self._repositories is None:
            self._repositories = {
                repository.name: repository
                for repository in DailyBackfillAgent._repositories(self.search_dirs)
            }
        if project not in self._subjects:
            repository = self._repositories.get(project)
            subjects = None
            if repository is not None:
                result = subprocess.run(
                    ["git", "-C", str(repository), "log", "--all", "--format=%s"],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    subjects = set(result.stdout.splitlines())
            self._subjects[project] = subjects
        return self._subjects[project]

    def _legacy_event(self, path: Path, text: str) -> Optional[str]:
        try:
            data = json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])
        except (IndexError, json.JSONDecodeError):
            return None
        if isinstance(data.get("narrative"), str) and data.get("entities") == []:
            return "session fragment replaced by daily notes"
        source = SOURCE_PATTERN.search(text)
        project = path.parent.parent.name
        subjects = self._commit_subjects(project)
        if source and subjects is not None and source.group(1).strip() in subjects:
            return f"commit still in {project} history"
        return None

    @staticmethod
    def _legacy_entity(text: str) -> Optional[str]:
        lines = [line for line in text.splitlines() if line.strip()]
        if all(line.startswith(OBSERVED_LINE) for line in lines):
            return "entity note with only observation dates"
        return None

    def candidates(self) -> List[Tuple[Path, str]]:
        """Every file with no value, and why."""
        found = []
        for path in self._paths():
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            parts = path.relative_to(self.vault_root).parts
            reason = self._placeholder(path, text)
            if reason is None and len(parts) == 4 and parts[0] == "projects" and path.suffix == ".md":
                if parts[2] == "events":
                    reason = self._legacy_event(path, text)
                elif parts[2] == "entities":
                    reason = self._legacy_entity(text)
            if reason:
                found.append((path, reason))
        return found

    def run(self, dry_run: bool = False, sync: bool = True) -> int:
        files = self.candidates()
        removed = files + [
            (folder, "empty folder")
            for folder in self._empty_folders({path for path, _ in files})
        ]
        for path, reason in removed:
            print(f"{'Would remove' if dry_run else '🧹 Removed'} {path.relative_to(self.vault_root)} ({reason})")
            if dry_run:
                continue
            if path.is_dir():
                path.rmdir()
            else:
                path.unlink()
        print(f"🧹 {'Found' if dry_run else 'Removed'} {len(removed)} files and folders with no value.")
        if removed and sync and not dry_run:
            self.sync_agent.sync()
        return len(removed)
