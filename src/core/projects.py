"""Find repositories on disk and the folders whose repositories are one project."""
import os
import subprocess
from pathlib import Path
from typing import Dict, Iterable, List, Set

SKIPPED_DIRECTORIES = {"node_modules", "__pycache__", ".venv"}


def find_repositories(search_dirs: Iterable[Path]) -> List[Path]:
    if isinstance(search_dirs, Path):
        search_dirs = [search_dirs]
    repositories = []
    for search_dir in search_dirs:
        for root, directories, _ in os.walk(search_dir):
            if ".git" in directories:
                repositories.append(Path(root))
                directories.remove(".git")
            directories[:] = [
                directory for directory in directories if directory not in SKIPPED_DIRECTORIES
            ]
    return repositories


def _root_commits(repository: Path) -> Set[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), "rev-list", "--max-parents=0", "--all"],
        capture_output=True,
        text=True,
    )
    return set(result.stdout.split()) if result.returncode == 0 else set()


def project_groups(
    repositories: Iterable[Path], search_dirs: Iterable[Path], configured: Iterable[Path] = ()
) -> List[Path]:
    """Folders whose repositories form one project, named after the folder.

    A folder qualifies when it is neither a repository nor a search root and
    at least two of the repositories directly in it share a root commit:
    clones of one codebase, like a client's DEV/TEST/PROD checkouts. Folders
    of unrelated repositories never share history, so they stay apart.
    `configured` adds folders the history can't reveal.
    """
    roots = {Path(search_dir) for search_dir in search_dirs}
    children: Dict[Path, List[Path]] = {}
    for repository in repositories:
        children.setdefault(repository.parent, []).append(repository)
    groups = [Path(folder) for folder in configured]
    for folder, members in sorted(children.items()):
        if folder in roots or folder in groups or len(members) < 2 or (folder / ".git").exists():
            continue
        seen: Set[str] = set()
        for member in members:
            commits = _root_commits(member)
            if seen & commits:
                groups.append(folder)
                break
            seen |= commits
    return groups
