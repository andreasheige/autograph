from src.core.daily_note_renderer import render_daily_note, session_note_link
from src.core.vault import VaultManager


def test_render_daily_note_includes_technical_sections_and_links():
    content = render_daily_note(
        "2026-08-29",
        "Validated the note workflow.",
        [
            {
                "title": "Session ingestion",
                "work_done": "Added JSONL ingestion.",
                "went_well": "All drivers loaded.",
                "learned": "Cursor state avoids duplicates.",
                "remember": "Keep sources local.",
                "commits": ["abc123def456"],
            }
        ],
        [{"id": "abc123def456", "title": "Add ingestion", "project": "Autograph"}],
        ["2026-08-28"],
    )

    assert "## Day summary" in content
    assert "**What was done**" in content
    assert "**What we learned**" in content
    assert "Weather" not in content
    assert "[[projects/Autograph/commits/abc123def456|" in content
    assert "[[projects/Autograph|Autograph]]" in content
    assert "[[agents/Ollama|Ollama]]" in content
    assert "## Connected graph" in content
    assert "[[daily_notes/2026-08-28|2026-08-28]]" in content


def test_write_commit_note_links_back_to_daily_note(tmp_path):
    vault = VaultManager(tmp_path)

    vault.write_commit_note("Autograph", "abc123def456", "Add ingestion", "2026-08-29")

    content = (
        tmp_path / "projects" / "Autograph" / "commits" / "abc123def456.md"
    ).read_text(encoding="utf-8")
    assert "`abc123def456`" in content
    assert "[[daily_notes/2026-08-29|2026-08-29]]" in content


def test_render_daily_note_links_each_section_to_its_session():
    content = render_daily_note(
        "2026-08-29",
        "Validated the note workflow.",
        [
            {
                "title": "Session ingestion",
                "work_done": "Added JSONL ingestion.",
                "source": "claude",
                "session_id": "10a40d72-c7ec-4e33-8d64-af2eb61dd0c6",
                "models": ["claude-opus-5", "claude-sonnet-5"],
            },
            {
                "title": "Untracked history",
                "work_done": "Read the shared history log.",
                "source": "claude",
                "session_id": ".claude",
                "models": [],
            },
        ],
        [],
        [],
    )

    assert "**Agent source:** [[agents/Claude|Claude]]" in content
    assert "**Models:** `claude-opus-5`, `claude-sonnet-5`" in content
    assert (
        "**Session:** [[sessions/claude/10a40d72-c7ec-4e33-8d64-af2eb61dd0c6|10a40d72]]"
        in content
    )
    assert "[[sessions/claude/.claude" not in content


def test_session_note_link_rejects_ids_that_name_no_single_session():
    assert session_note_link("claude", "10a40d72") == (
        "[[sessions/claude/10a40d72|10a40d72]]"
    )
    assert session_note_link("git", "abc123def456") == ""
    assert session_note_link("claude", "unknown-session") == ""
    assert session_note_link("claude", ".codex") == ""
    assert session_note_link("pi", "--Users-andreas-Knowit-KX - work--") == ""
    assert session_note_link("claude", None) == ""


def test_write_session_note_creates_a_stub_once(tmp_path):
    vault = VaultManager(tmp_path)

    assert vault.write_session_note(
        "claude",
        "10a40d72-c7ec-4e33-8d64-af2eb61dd0c6",
        ["claude-opus-5"],
        "claude/projects/-Users-andreas-Dev/10a40d72.jsonl",
    )

    note_path = (
        tmp_path / "sessions" / "claude" / "10a40d72-c7ec-4e33-8d64-af2eb61dd0c6.md"
    )
    content = note_path.read_text(encoding="utf-8")
    assert "# Claude session 10a40d72" in content
    assert "[[agents/Claude|Claude]]" in content
    assert "`claude-opus-5`" in content
    assert "claude/projects/-Users-andreas-Dev/10a40d72.jsonl" in content
    assert not vault.write_session_note(
        "claude", "10a40d72-c7ec-4e33-8d64-af2eb61dd0c6", ["claude-opus-5"]
    )


def test_write_session_note_refuses_ids_that_escape_the_sessions_folder(tmp_path):
    vault = VaultManager(tmp_path)

    assert not vault.write_session_note("claude", "../../escaped")
    assert not vault.write_session_note("claude", "nested/id")
    assert not vault.write_session_note("../..", "10a40d72")
    assert not vault.write_session_note("claude", ".claude")
    assert list(tmp_path.rglob("*.md")) == []


def test_render_daily_note_starts_with_queryable_properties():
    content = render_daily_note(
        "2026-08-29",
        "Validated the note workflow.",
        [
            {
                "title": "Session ingestion",
                "project": "Autograph",
                "source": "claude",
                "models": ["claude-opus-5", "claude-sonnet-5"],
            },
            {"title": "Loose work", "project": "unassigned", "source": "codex"},
            {"title": "Commit only", "source": "git", "models": ["claude-opus-5"]},
        ],
        [{"id": "abc123def456", "title": "Add ingestion", "project": "Side: project"}],
        [],
    )

    assert content.startswith(
        "---\n"
        "type: \"daily-note\"\n"
        "date: 2026-08-29\n"
        "projects: [\"Autograph\", \"Side: project\"]\n"
        "agents: [\"Claude\", \"Codex\"]\n"
        "models: [\"claude-opus-5\", \"claude-sonnet-5\"]\n"
        "commits: 1\n"
        "tags: []\n"
        "generated_by: \"autograph\"\n"
        "---\n\n# Daily Journal: 2026-08-29\n"
    )
    assert content.endswith("---\n*Generated by Autograph Agent*\n")


def test_write_commit_note_keeps_session_context_under_properties(tmp_path):
    vault = VaultManager(tmp_path)
    vault.write_commit_note(
        "Autograph", "abc123def456", "Add ingestion", "2026-08-29", "Context."
    )
    vault.write_commit_note("Autograph", "abc123def456", "Add ingestion", "2026-08-29")

    content = (
        tmp_path / "projects" / "Autograph" / "commits" / "abc123def456.md"
    ).read_text(encoding="utf-8")
    assert content.startswith(
        "---\ntype: \"commit\"\ndate: 2026-08-29\nproject: \"Autograph\"\n"
        "commit: \"abc123def456\"\n---\n\n# abc123def456 Add ingestion\n"
    )
    assert content.count("---\n") == 2
    assert content.endswith("## Session context\n\nContext.\n")


def test_render_daily_note_tags_the_day_and_links_related_wiki_pages():
    content = render_daily_note(
        "2026-08-29",
        "Validated the note workflow.",
        [
            {
                "title": "Login",
                "terms": ["bff", "entra"],
                "wiki_pages": [("wiki/concepts/bff-login", "BFF [login] | proxy")],
            },
            {"title": "Tests", "terms": ["bff", "testing"], "wiki_pages": []},
        ],
        [],
        [],
    )

    assert 'tags: ["bff", "entra", "testing"]\n' in content
    assert "**Related wiki:** [[wiki/concepts/bff-login|BFF login - proxy]]" in content
    assert content.count("**Related wiki:**") == 1
