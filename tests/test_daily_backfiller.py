from src.agents.daily_backfiller import DailyBackfillAgent
from src.core.vault import VaultManager


def test_daily_backfill_groups_timestamped_events_by_date():
    grouped, skipped = DailyBackfillAgent._group_events_by_date(
        [
            {
                "timestamp": "2026-08-27T23:30:00-02:00",
                "content": "first",
            },
            {"timestamp": "invalid", "content": "ignored"},
        ]
    )

    assert skipped == 1
    assert grouped == {
        "2026-08-28": [
            {
                "timestamp": "2026-08-27T23:30:00-02:00",
                "content": "first",
            }
        ]
    }


def test_daily_backfill_removes_only_marked_generated_notes(tmp_path):
    notes_dir = tmp_path / "daily_notes"
    notes_dir.mkdir()
    generated_note = notes_dir / "2026-08-27.md"
    generated_note.write_text(
        f"# Generated\n\n{DailyBackfillAgent.generated_marker}\n",
        encoding="utf-8",
    )
    manual_note = notes_dir / "2026-08-28.md"
    manual_note.write_text("# Manual note\n", encoding="utf-8")

    agent = DailyBackfillAgent.__new__(DailyBackfillAgent)
    agent.vault_manager = VaultManager(tmp_path)

    assert agent._remove_generated_notes() == 1
    assert not generated_note.exists()
    assert manual_note.exists()


def test_daily_backfill_keeps_existing_generated_notes_when_resuming(tmp_path):
    agent = DailyBackfillAgent.__new__(DailyBackfillAgent)
    agent.vault_manager = VaultManager(tmp_path)
    note_path = tmp_path / "daily_notes" / "2026-08-28.md"
    note_path.parent.mkdir()
    note_path.write_text(
        f"# Existing\n\n{DailyBackfillAgent.generated_marker}\n",
        encoding="utf-8",
    )

    wrote_note = agent._write_daily_note("2026-08-28", "Replacement")

    assert wrote_note is False
    assert note_path.read_text(encoding="utf-8").startswith("# Existing")


def test_daily_backfill_removes_only_requested_generated_date(tmp_path):
    agent = DailyBackfillAgent.__new__(DailyBackfillAgent)
    agent.vault_manager = VaultManager(tmp_path)
    notes_dir = tmp_path / "daily_notes"
    notes_dir.mkdir()
    for date in ("2026-08-26", "2026-08-27"):
        (notes_dir / f"{date}.md").write_text(
            f"# Generated\n\n{DailyBackfillAgent.generated_marker}\n",
            encoding="utf-8",
        )

    assert agent._remove_generated_notes(["2026-08-26"]) == 1
    assert not (notes_dir / "2026-08-26.md").exists()
    assert (notes_dir / "2026-08-27.md").exists()
