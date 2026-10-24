import subprocess

from src.agents.vault_cleanup import VaultCleanupAgent

EVENT = (
    "# Historical Event\n\n"
    "**Source:** [Wed Aug 26 12:00:01 2026 +0200] Some One committed: {subject}\n\n"
    '## Extracted Data\n```json\n{{"entities": [{{"name": "Button"}}]}}\n```\n'
)


def repository(tmp_path, name, subject):
    repo = tmp_path / "code" / name
    repo.mkdir(parents=True)
    git = ["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "--no-verify", "-m", subject], check=True)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def agent(tmp_path):
    return VaultCleanupAgent(tmp_path / "vault", [tmp_path / "code"])


def test_removes_only_files_with_no_value(tmp_path):
    repository(tmp_path, "web", "feat: add Button")
    vault = tmp_path / "vault"
    gone = [
        write(vault / "2026-10-19.md", ""),
        write(vault / "Untitled.canvas", "{}"),
        write(vault / "Untitled.base", "views:\n  - type: table\n    name: View\n"),
        write(vault / "projects/web/events/a.md", EVENT.format(subject="feat: add Button")),
        write(
            vault / "projects/web/events/b.md",
            '# Historical Event\n\n```json\n{"entities": [], "narrative": "Old session"}\n```\n',
        ),
        write(vault / "projects/web/entities/Button.md", "\n- Observed in history on 2026-08-26\n"),
        write(vault / "projects/web/commits/abc.md", ""),
    ]
    kept = [
        write(vault / "notes.md", "A thought.\n"),
        write(vault / "Board.canvas", '{"nodes": [{"id": "1"}], "edges": []}'),
        write(vault / "Days.base", "filters:\n  - type == daily-note\nviews:\n  - type: table\n"),
        # Subject no longer in the repo, or no repo at all: the note is the only copy.
        write(vault / "projects/web/events/c.md", EVENT.format(subject="feat: lost commit")),
        write(vault / "projects/gone/events/d.md", EVENT.format(subject="feat: add Button")),
        write(vault / "projects/web/entities/Toast.md", "- Observed in history on 2026-08-26\nUses portals.\n"),
        write(vault / "wiki/empty.md", ""),
        write(vault / ".obsidian/empty.md", ""),
    ]
    (vault / "personal/events").mkdir(parents=True)
    (vault / ".obsidian/snippets").mkdir()
    folders = 3  # projects/web/commits, personal/events, personal

    assert agent(tmp_path).run(dry_run=True) == len(gone) + folders
    assert all(path.exists() for path in gone)

    assert agent(tmp_path).run(sync=False) == len(gone) + folders
    assert not any(path.exists() for path in gone)
    assert all(path.exists() for path in kept)
    # Emptied folders go too, but not one that still holds a kept note.
    assert not (vault / "projects/web/commits").exists()
    assert (vault / "projects/web/entities").exists()
    assert not (vault / "personal").exists()
    assert (vault / ".obsidian/snippets").exists()
    assert agent(tmp_path).run(sync=False) == 0
