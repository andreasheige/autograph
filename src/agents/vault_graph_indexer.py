from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

from config.settings import Config
from src.agents.sync_agent import AutographSyncAgent
from src.core.daily_note_renderer import (
    agent_label,
    agent_note_link,
    daily_note_link,
)
from src.core.vault import VaultManager


class VaultGraphIndexer:
    """Create stable vault hubs and indexes without changing note bodies."""

    marker = "<!-- Autograph managed links -->"

    def __init__(self):
        self.vault_manager = VaultManager(Config.VAULT_ROOT)
        self.sync_agent = AutographSyncAgent(self.vault_manager.vault_root)

    @staticmethod
    def _wiki_link(path: Path, label: str) -> str:
        return f"[[{path.as_posix()}|{label}]]"

    def _write_managed_note(self, path: Path, title: str, body: str) -> bool:
        content = f"# {title}\n\n{body.strip()}\n\n{self.marker}\n"
        if path.exists() and path.read_text(encoding="utf-8", errors="replace") == content:
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True

    def _ensure_project_hub(self, project: str) -> bool:
        hub_path = Path("projects") / f"{project}.md"
        absolute_path = self.vault_manager.vault_root / hub_path
        index_path = Path("projects") / project / "Index"
        index_link = self._wiki_link(index_path, "Project index")
        if not absolute_path.exists():
            return self._write_managed_note(
                absolute_path,
                project,
                f"## Navigation\n\n- {index_link}",
            )

        content = absolute_path.read_text(encoding="utf-8", errors="replace")
        if index_link in content:
            return False
        absolute_path.write_text(
            content.rstrip() + f"\n\n## Navigation\n\n- {index_link}\n",
            encoding="utf-8",
        )
        return True

    @staticmethod
    def _project_leaf_notes(project_path: Path) -> List[Path]:
        return [
            note_path
            for note_path in project_path.rglob("*.md")
            if note_path.name != "Index.md"
        ]

    def _prune_empty_managed_project_indexes(self, projects_dir: Path) -> int:
        """Remove only index/hub notes that Autograph created for empty folders."""
        removed = 0
        for project_path in projects_dir.iterdir():
            if not project_path.is_dir() or self._project_leaf_notes(project_path):
                continue

            index_path = project_path / "Index.md"
            if index_path.exists() and self.marker in index_path.read_text(
                encoding="utf-8", errors="replace"
            ):
                index_path.unlink()
                removed += 1

            hub_path = projects_dir / f"{project_path.name}.md"
            if hub_path.exists() and self.marker in hub_path.read_text(
                encoding="utf-8", errors="replace"
            ):
                hub_path.unlink()
                removed += 1
        return removed

    def _normalize_legacy_entity_filenames(self) -> int:
        """Remove an accidental duplicate .md suffix from legacy entity files."""
        renamed = 0
        for note_path in self.vault_manager.vault_root.glob(
            "projects/*/entities/*.md.md"
        ):
            normalized_path = note_path.with_suffix("")
            if normalized_path.exists():
                continue
            note_path.rename(normalized_path)
            renamed += 1
        return renamed

    def _project_index(self, project_path: Path) -> bool:
        project = project_path.name
        files_by_kind: Dict[str, List[Path]] = defaultdict(list)
        for note_path in self._project_leaf_notes(project_path):
            relative_path = note_path.relative_to(self.vault_manager.vault_root).with_suffix("")
            kind = note_path.relative_to(project_path).parts[0]
            files_by_kind[kind].append(relative_path)

        sections = [
            "## Navigation",
            "",
            f"- {self._wiki_link(Path('Autograph'), 'Autograph knowledge graph')}",
            f"- {self._wiki_link(Path('projects') / project, project)}",
        ]
        labels = {
            "commits": "Commits",
            "entities": "Entity notes",
            "events": "Historical events",
        }
        for kind in sorted(files_by_kind):
            sections.extend(["", f"## {labels.get(kind, kind.title())}"])
            sections.extend(
                f"- {self._wiki_link(path, path.name)}"
                for path in sorted(files_by_kind[kind])
            )
        return self._write_managed_note(
            project_path / "Index.md", f"{project} index", "\n".join(sections)
        )

    def _daily_index(self, daily_notes: Iterable[Path]) -> bool:
        links = [
            f"- {daily_note_link(note_path.stem)}"
            for note_path in sorted(daily_notes)
        ]
        return self._write_managed_note(
            self.vault_manager.vault_root / "daily_notes" / "Index.md",
            "Daily notes",
            "## Generated daily notes\n\n" + "\n".join(links),
        )

    def _agent_index(self, agent_notes: Iterable[Path]) -> bool:
        links = [
            f"- {agent_note_link(note_path.stem)}"
            for note_path in sorted(agent_notes)
            if note_path.stem != "Index"
        ]
        return self._write_managed_note(
            self.vault_manager.vault_root / "agents" / "Index.md",
            "Agent sources",
            "## Local agent hubs\n\n" + "\n".join(links),
        )

    def _session_index(self, sessions_dir: Path) -> bool:
        sections = ["## Recorded agent sessions"]
        source_dirs = sorted(
            path for path in sessions_dir.iterdir() if path.is_dir()
        )
        for source_dir in source_dirs:
            notes = sorted(
                note_path
                for note_path in source_dir.glob("*.md")
                if note_path.stem != "Index"
            )
            if not notes:
                continue
            sections.extend(["", f"### {agent_label(source_dir.name)}"])
            for note_path in notes:
                relative_path = note_path.relative_to(
                    self.vault_manager.vault_root
                ).with_suffix("")
                sections.append(
                    f"- {self._wiki_link(relative_path, note_path.stem[:8])}"
                )
        return self._write_managed_note(
            sessions_dir / "Index.md", "Agent sessions", "\n".join(sections)
        )

    def _root_index(self, projects: Iterable[str]) -> bool:
        project_links = [
            f"- {self._wiki_link(Path('projects') / project, project)}"
            for project in sorted(projects)
        ]
        navigation = [
            f"- {self._wiki_link(Path('daily_notes') / 'Index', 'Daily notes')}",
            f"- {self._wiki_link(Path('agents') / 'Index', 'Agent sources')}",
        ]
        # Only link the session index once sessions exist, or the root hub would
        # carry an unresolved link for every vault with no recorded session yet.
        if (self.vault_manager.vault_root / "sessions").exists():
            navigation.append(
                f"- {self._wiki_link(Path('sessions') / 'Index', 'Agent sessions')}"
            )
        navigation.append(
            f"- {self._wiki_link(Path('projects') / 'Index', 'Projects')}"
        )
        return self._write_managed_note(
            self.vault_manager.vault_root / "Autograph.md",
            "Autograph knowledge graph",
            "\n".join(
                [
                    "## Navigation",
                    "",
                    *navigation,
                    "",
                    "## Projects",
                    "",
                    *project_links,
                ]
            ),
        )

    def _projects_index(self, projects: Iterable[str]) -> bool:
        links = [
            f"- {self._wiki_link(Path('projects') / project, project)}"
            for project in sorted(projects)
        ]
        return self._write_managed_note(
            self.vault_manager.vault_root / "projects" / "Index.md",
            "Projects",
            "## Project hubs\n\n"
            + "\n".join(links)
            + "\n\n## Related\n\n"
            + f"- {self._wiki_link(Path('Autograph'), 'Autograph knowledge graph')}",
        )

    def run(self) -> int:
        projects_dir = self.vault_manager.vault_root / "projects"
        changes = self._normalize_legacy_entity_filenames()
        changes += self._prune_empty_managed_project_indexes(projects_dir)
        project_paths = sorted(
            path
            for path in projects_dir.iterdir()
            if path.is_dir() and self._project_leaf_notes(path)
        )
        projects = [path.name for path in project_paths]
        changes += sum(self._ensure_project_hub(project) for project in projects)
        changes += sum(self._project_index(project_path) for project_path in project_paths)
        changes += self._daily_index(
            (self.vault_manager.vault_root / "daily_notes").glob("*.md")
        )
        changes += self._agent_index(
            (self.vault_manager.vault_root / "agents").glob("*.md")
        )
        sessions_dir = self.vault_manager.vault_root / "sessions"
        if sessions_dir.exists():
            changes += self._session_index(sessions_dir)
        changes += self._projects_index(projects)
        changes += self._root_index(projects)
        print(f"🕸️ Updated {changes} vault graph hub and index notes.")
        if changes:
            self.sync_agent.sync()
        return changes
