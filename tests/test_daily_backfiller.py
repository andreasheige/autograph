from datetime import datetime, timedelta, timezone

from src.agents.daily_backfiller import DailyBackfillAgent
from src.core.daily_note_state import DailyNoteState
from src.core.vault import VaultManager
from src.core.work_units import (
    MAX_DAILY_WORK_UNITS,
    Commit,
    WorkUnit,
    build_work_units,
    normalize_events,
)


def test_work_units_filter_duplicates_and_associate_nearest_commit(tmp_path):
    repository = tmp_path / "project"
    repository.mkdir()
    start = datetime(2026, 8, 29, 9, 0, tzinfo=timezone.utc)
    events = normalize_events(
        [
            {
                "timestamp": start.isoformat(),
                "source": "copilot",
                "session_id": "session-1",
                "role": "user",
                "cwd": str(repository),
                "content": "Implement the daily-note pipeline.",
            },
            {
                "timestamp": (start + timedelta(minutes=1)).isoformat(),
                "source": "copilot",
                "session_id": "session-1",
                "role": "user",
                "cwd": str(repository),
                "content": "Implement the daily-note pipeline.",
            },
            {
                "timestamp": (start + timedelta(minutes=2)).isoformat(),
                "source": "copilot",
                "session_id": "session-1",
                "role": "tool",
                "cwd": str(repository),
                "content": "Noisy tool output that should not be retained.",
            },
        ],
        [repository],
        datetime.fromisoformat,
    )
    commit = Commit(
        "abc123def456",
        "Add work-unit pipeline",
        "project",
        start + timedelta(minutes=30),
    )

    units = build_work_units(events, [commit])

    assert len(units["2026-08-29"]) == 1
    assert len(units["2026-08-29"][0].events) == 1
    assert units["2026-08-29"][0].commits == [commit]


def test_work_units_cap_the_number_selected_per_day():
    timestamp = datetime(2026, 8, 29, 9, 0, tzinfo=timezone.utc)
    events = [
        {
            "timestamp": timestamp + timedelta(minutes=index),
            "date": "2026-08-29",
            "project": "project",
            "source": "copilot",
            "session_id": f"session-{index}",
            "role": "user",
            "content": f"Meaningful work item {index}",
        }
        for index in range(MAX_DAILY_WORK_UNITS + 4)
    ]

    units = build_work_units(events, [])

    assert len(units["2026-08-29"]) == MAX_DAILY_WORK_UNITS


def test_daily_note_state_tracks_input_fingerprint(tmp_path):
    state = DailyNoteState(tmp_path / "daily-state.json")

    assert not state.is_current("2026-08-29", "fingerprint")
    state.save("2026-08-29", "fingerprint")

    assert DailyNoteState(tmp_path / "daily-state.json").is_current(
        "2026-08-29", "fingerprint"
    )


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


def test_daily_backfill_refuses_to_overwrite_manual_note(tmp_path):
    agent = DailyBackfillAgent.__new__(DailyBackfillAgent)
    agent.vault_manager = VaultManager(tmp_path)
    note_path = tmp_path / "daily_notes" / "2026-08-28.md"
    note_path.parent.mkdir()
    note_path.write_text("# Manual note\n", encoding="utf-8")

    try:
        agent._write_daily_note("2026-08-28", "Replacement")
    except FileExistsError:
        pass
    else:
        raise AssertionError("Expected manual note overwrite protection")


def test_daily_backfill_writes_session_stubs_only_for_real_sessions(tmp_path):
    agent = DailyBackfillAgent.__new__(DailyBackfillAgent)
    agent.vault_manager = VaultManager(tmp_path)
    sections = [
        {"source": "claude", "session_id": "10a40d72-c7ec-4e33-8d64-af2eb61dd0c6"},
        {"source": "codex", "session_id": ".codex"},
        {"source": "git", "session_id": "abc123def456"},
    ]
    session_metadata = {
        ("claude", "10a40d72-c7ec-4e33-8d64-af2eb61dd0c6"): {
            "models": ["claude-opus-5"],
            "transcript": "claude/projects/session.jsonl",
        }
    }

    assert agent._write_session_notes(sections, session_metadata) == 1
    written = sorted(path.name for path in (tmp_path / "sessions").rglob("*.md"))
    assert written == ["10a40d72-c7ec-4e33-8d64-af2eb61dd0c6.md"]
    assert "`claude-opus-5`" in (
        tmp_path
        / "sessions"
        / "claude"
        / "10a40d72-c7ec-4e33-8d64-af2eb61dd0c6.md"
    ).read_text(encoding="utf-8")


def test_sections_only_carry_session_links_for_identified_sessions():
    class FakeSynthesizer:
        @staticmethod
        def synthesize_work_unit(prompt):
            return {"title": "Work", "work_done": "Done"}

    start = datetime(2026, 8, 29, 9, 0, tzinfo=timezone.utc)
    units = [
        WorkUnit(
            date="2026-08-29",
            project="project",
            source="claude",
            session_id="10a40d72-c7ec-4e33-8d64-af2eb61dd0c6",
            start=start,
            end=start,
        ),
        WorkUnit(
            date="2026-08-29",
            project="project",
            source="codex",
            session_id="04",
            start=start,
            end=start,
        ),
    ]
    agent = DailyBackfillAgent.__new__(DailyBackfillAgent)
    agent.synthesizer = FakeSynthesizer()
    session_metadata = {
        ("claude", "10a40d72-c7ec-4e33-8d64-af2eb61dd0c6"): {
            "models": ["claude-opus-5"]
        }
    }

    sections = agent._sections_for_units("2026-08-29", units, session_metadata)

    assert sections[0]["session_id"] == "10a40d72-c7ec-4e33-8d64-af2eb61dd0c6"
    assert sections[0]["models"] == ["claude-opus-5"]
    assert "session_id" not in sections[1]
    assert "models" not in sections[1]
