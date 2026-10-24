from datetime import datetime, timezone

from src.agents.vault_graph_indexer import VaultGraphIndexer
from src.core.vault import VaultManager
from src.core.work_units import normalize_events, project_name, project_roots


def test_a_group_folder_is_one_project_and_its_siblings_stay_apart(tmp_path):
    platform = tmp_path / "Knowit" / "capio-plattfrom"
    group = platform / "cmks"
    clones = [group / "DEV_Backend", group / "PROD_Frontend"]
    frontend = platform / "capio-frontend"
    for folder in [*clones, frontend]:
        folder.mkdir(parents=True)
    repositories = [frontend, *clones]

    assert [project_name(repository, [group]) for repository in repositories] == [
        "capio-frontend",
        "cmks",
        "cmks",
    ]
    assert project_roots(repositories, [group]) == [frontend, group]
    assert project_roots(repositories) == repositories

    def event(cwd, content):
        return {
            "timestamp": datetime(2026, 10, 24, 9, tzinfo=timezone.utc).isoformat(),
            "source": "claude",
            "session_id": "s1",
            "role": "user",
            "cwd": str(cwd),
            "content": content,
        }

    events = normalize_events(
        [
            event(group, "Plan the cmks release."),
            event(clones[0] / "src", "Fix the backend build."),
            event(frontend, "Style the header."),
        ],
        project_roots(repositories, [group]),
        lambda value: datetime.fromisoformat(value),
    )
    assert [item["project"] for item in events] == ["cmks", "cmks", "capio-frontend"]


def test_project_hub_has_no_folder_links_and_is_written_once(tmp_path):
    vault = VaultManager(tmp_path)
    (tmp_path / "projects").mkdir()

    assert vault.write_project_note("cmks") is True
    assert vault.write_project_note("cmks") is False
    content = (tmp_path / "projects" / "cmks.md").read_text(encoding="utf-8")
    assert "[[projects/cmks/commits]]" not in content
    assert "/events]]" not in content


def test_projects_index_lists_hubs_without_notes_of_their_own(tmp_path):
    vault = VaultManager(tmp_path)
    (tmp_path / "projects").mkdir()
    vault.write_project_note("site-checker-tool")
    commit = tmp_path / "projects" / "blog" / "commits" / "abc.md"
    commit.parent.mkdir(parents=True)
    commit.write_text("# Commit\n", encoding="utf-8")

    VaultGraphIndexer(tmp_path).run(sync=False)

    index = (tmp_path / "projects" / "Index.md").read_text(encoding="utf-8")
    assert "[[projects/blog|blog]]" in index
    assert "[[projects/site-checker-tool|site-checker-tool]]" in index
    assert "[[projects/Index|" not in index


def test_a_repository_keeps_its_hub_when_its_folder_empties(tmp_path):
    (tmp_path / "projects" / "kxse").mkdir(parents=True)
    managed = "\n\n<!-- Autograph managed links -->\n"
    (tmp_path / "projects" / "kxse" / "Index.md").write_text("# kxse index" + managed, encoding="utf-8")
    (tmp_path / "projects" / "kxse.md").write_text(
        "# kxse\n\n- [[projects/kxse/Index|Project index]]" + managed, encoding="utf-8"
    )

    VaultGraphIndexer(tmp_path).run(sync=False, keep=["kxse"])

    hub = (tmp_path / "projects" / "kxse.md").read_text(encoding="utf-8")
    assert "Index" not in hub
    assert "[[projects/kxse|kxse]]" in (tmp_path / "projects" / "Index.md").read_text(encoding="utf-8")
