from src.core.daily_note_renderer import render_daily_note
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
    assert "[[daily_notes/2026-08-28|2026-08-28]]" in content


def test_write_commit_note_links_back_to_daily_note(tmp_path):
    vault = VaultManager(tmp_path)

    vault.write_commit_note("Autograph", "abc123def456", "Add ingestion", "2026-08-29")

    content = (
        tmp_path / "projects" / "Autograph" / "commits" / "abc123def456.md"
    ).read_text(encoding="utf-8")
    assert "`abc123def456`" in content
    assert "[[daily_notes/2026-08-29|2026-08-29]]" in content
