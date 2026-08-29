from subprocess import CompletedProcess
from unittest.mock import patch

from src.agents.sync_agent import AutographSyncAgent


def test_sync_stages_only_markdown_then_commits_and_pushes(tmp_path):
    (tmp_path / ".git").mkdir()
    pull = CompletedProcess(["git", "pull"], 0)
    add = CompletedProcess(["git", "add"], 0)
    staged_changes = CompletedProcess(["git", "diff"], 1)
    commit = CompletedProcess(["git", "commit"], 0)
    push = CompletedProcess(["git", "push"], 0)

    with patch(
        "src.agents.sync_agent.subprocess.run",
        side_effect=[pull, add, staged_changes, commit, push],
    ) as run:
        assert AutographSyncAgent(tmp_path).sync() is True

    add_command = run.call_args_list[1].args[0]
    assert add_command[-1] == ":(glob)**/*.md"
    assert "--all" in add_command
    commit_command = run.call_args_list[3].args[0]
    assert commit_command[-1].startswith("chore(vault): sync Markdown")
    assert run.call_args_list[4].args[0][-1] == "push"


def test_sync_skips_commit_when_no_markdown_changes(tmp_path):
    (tmp_path / ".git").mkdir()
    pull = CompletedProcess(["git", "pull"], 0)
    add = CompletedProcess(["git", "add"], 0)
    staged_changes = CompletedProcess(["git", "diff"], 0)

    with patch(
        "src.agents.sync_agent.subprocess.run",
        side_effect=[pull, add, staged_changes],
    ) as run:
        assert AutographSyncAgent(tmp_path).sync() is True

    assert run.call_count == 3
