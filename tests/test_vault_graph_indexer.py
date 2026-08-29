from src.agents.vault_graph_indexer import VaultGraphIndexer
from src.core.vault import VaultManager


def test_graph_indexer_creates_a_connected_navigation_spine(tmp_path):
    vault_manager = VaultManager(tmp_path)
    (tmp_path / "daily_notes").mkdir()
    (tmp_path / "daily_notes" / "2026-08-29.md").write_text(
        "# Daily\n", encoding="utf-8"
    )
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "Copilot.md").write_text("# Copilot\n", encoding="utf-8")
    commit_path = tmp_path / "projects" / "project" / "commits" / "abc.md"
    commit_path.parent.mkdir(parents=True)
    commit_path.write_text("# Commit\n", encoding="utf-8")

    indexer = VaultGraphIndexer.__new__(VaultGraphIndexer)
    indexer.vault_manager = vault_manager

    project_path = tmp_path / "projects" / "project"
    assert indexer._ensure_project_hub("project")
    assert indexer._project_index(project_path)
    assert indexer._daily_index((tmp_path / "daily_notes").glob("*.md"))
    assert indexer._agent_index((tmp_path / "agents").glob("*.md"))
    assert indexer._projects_index(["project"])
    assert indexer._root_index(["project"])

    root = (tmp_path / "Autograph.md").read_text(encoding="utf-8")
    project_index = (project_path / "Index.md").read_text(encoding="utf-8")
    assert "[[daily_notes/Index|Daily notes]]" in root
    assert "[[projects/project|project]]" in root
    assert "[[projects/project/commits/abc|abc]]" in project_index


def test_graph_indexer_removes_only_managed_hubs_for_empty_projects(tmp_path):
    vault_manager = VaultManager(tmp_path)
    empty_project = tmp_path / "projects" / "empty_sessions"
    empty_project.mkdir(parents=True)
    index_path = empty_project / "Index.md"
    index_path.write_text(
        "# Empty\n\n<!-- Autograph managed links -->\n", encoding="utf-8"
    )
    hub_path = tmp_path / "projects" / "empty_sessions.md"
    hub_path.write_text(
        "# Empty\n\n<!-- Autograph managed links -->\n", encoding="utf-8"
    )
    manual_project = tmp_path / "projects" / "manual"
    manual_project.mkdir()
    manual_index = manual_project / "Index.md"
    manual_index.write_text("# Manual\n", encoding="utf-8")

    indexer = VaultGraphIndexer.__new__(VaultGraphIndexer)
    indexer.vault_manager = vault_manager

    assert indexer._prune_empty_managed_project_indexes(tmp_path / "projects") == 2
    assert not index_path.exists()
    assert not hub_path.exists()
    assert manual_index.exists()


def test_graph_indexer_normalizes_legacy_double_entity_extensions(tmp_path):
    vault_manager = VaultManager(tmp_path)
    entity_path = tmp_path / "projects" / "project" / "entities" / "CLAUDE.md.md"
    entity_path.parent.mkdir(parents=True)
    entity_path.write_text("# Claude\n", encoding="utf-8")
    indexer = VaultGraphIndexer.__new__(VaultGraphIndexer)
    indexer.vault_manager = vault_manager

    assert indexer._normalize_legacy_entity_filenames() == 1
    assert not entity_path.exists()
    assert (entity_path.parent / "CLAUDE.md").exists()
