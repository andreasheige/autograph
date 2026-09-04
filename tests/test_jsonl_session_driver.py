import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from src.core.drivers.jsonl_session_driver import CopilotDriver
from src.agents.session_trigger import MultiRepositorySessionTriggerAgent


def test_copilot_driver_reads_only_new_records(tmp_path):
    session_root = tmp_path / "copilot"
    event_file = session_root / "session-1" / "events.jsonl"
    event_file.parent.mkdir(parents=True)
    event_file.write_text(
        json.dumps({"type": "message", "data": {"role": "user", "content": "old"}})
        + "\n",
        encoding="utf-8",
    )
    config = SimpleNamespace(
        COPILOT_SESSION_ROOT=session_root,
        SESSION_CURSOR_PATH=tmp_path / "cursors.json",
    )
    driver = CopilotDriver("copilot", config)

    assert driver.observe() == ""

    with event_file.open("a", encoding="utf-8") as events:
        events.write(
            json.dumps(
                {
                    "type": "message",
                    "timestamp": "2026-08-28T09:00:00Z",
                    "data": {
                        "role": "assistant",
                        "cwd": "/tmp/project",
                        "content": [{"type": "text", "text": "new activity"}],
                    },
                }
            )
            + "\n"
        )

    events = driver.extract_entities(driver.observe())

    assert events == [
        {
            "source": "copilot",
            "session_id": "session-1",
            "timestamp": "2026-08-28T09:00:00Z",
            "event_type": "message",
            "role": "assistant",
            "cwd": "/tmp/project",
            "content": "new activity",
        }
    ]


def test_copilot_driver_recovers_when_a_session_file_rotates(tmp_path):
    session_root = tmp_path / "copilot"
    event_file = session_root / "session-1" / "events.jsonl"
    event_file.parent.mkdir(parents=True)
    event_file.write_text("", encoding="utf-8")
    config = SimpleNamespace(
        COPILOT_SESSION_ROOT=session_root,
        SESSION_CURSOR_PATH=tmp_path / "cursors.json",
    )
    driver = CopilotDriver("copilot", config)
    driver.observe()
    event_file.write_text(
        json.dumps({"type": "message", "data": {"content": "replacement"}}) + "\n",
        encoding="utf-8",
    )

    events = driver.extract_entities(driver.observe())

    assert events[0]["content"] == "replacement"


def test_multi_repository_trigger_skips_dependency_directories(tmp_path):
    repository = tmp_path / "project"
    (repository / ".git").mkdir(parents=True)
    (tmp_path / "node_modules" / "nested" / ".git").mkdir(parents=True)
    trigger = MultiRepositorySessionTriggerAgent(tmp_path, lambda *_: None)

    assert trigger._repositories() == [repository]


def test_copilot_driver_reads_recent_history_without_changing_live_cursors(tmp_path):
    session_root = tmp_path / "copilot"
    event_file = session_root / "session-1" / "events.jsonl"
    event_file.parent.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    event_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": (now - timedelta(days=30)).isoformat(),
                        "data": {"content": "old"},
                    }
                ),
                json.dumps(
                    {
                        "type": "message",
                        "timestamp": now.isoformat(),
                        "data": {"content": "recent"},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    cursor_path = tmp_path / "cursors.json"
    config = SimpleNamespace(
        COPILOT_SESSION_ROOT=session_root,
        SESSION_CURSOR_PATH=cursor_path,
    )

    events = CopilotDriver("copilot", config).history_since(
        now - timedelta(days=14)
    )

    assert [event["content"] for event in events] == ["recent"]
    assert not cursor_path.exists()


def test_session_metadata_collects_models_and_transcript(tmp_path):
    session_root = tmp_path / "copilot"
    event_file = session_root / "session-1" / "events.jsonl"
    event_file.parent.mkdir(parents=True)
    event_file.write_text(
        "\n".join(
            json.dumps(record)
            for record in (
                {
                    "type": "session.start",
                    "data": {"sessionId": "session-1"},
                    "timestamp": "2026-08-28T09:00:00Z",
                },
                {
                    "type": "session.model_change",
                    "data": {"newModel": "claude-sonnet-5"},
                },
                {
                    "type": "session.model_change",
                    "data": {"newModel": "claude-sonnet-5"},
                },
                {"type": "session.model_change", "data": {"newModel": "gpt-5.6-sol"}},
                {"type": "message", "data": {"model": "<synthetic>"}},
            )
        )
        + "\n",
        encoding="utf-8",
    )
    config = SimpleNamespace(
        COPILOT_SESSION_ROOT=session_root,
        SESSION_CURSOR_PATH=tmp_path / "cursors.json",
    )
    driver = CopilotDriver("copilot", config)

    metadata = driver.session_metadata(
        datetime.now(timezone.utc) - timedelta(days=1)
    )

    assert metadata["session-1"]["models"] == ["claude-sonnet-5", "gpt-5.6-sol"]
    assert metadata["session-1"]["transcript"] == "copilot/session-1/events.jsonl"


def test_session_metadata_skips_files_older_than_the_window(tmp_path):
    session_root = tmp_path / "copilot"
    event_file = session_root / "session-1" / "events.jsonl"
    event_file.parent.mkdir(parents=True)
    event_file.write_text(
        json.dumps({"type": "session.model_change", "data": {"newModel": "old"}})
        + "\n",
        encoding="utf-8",
    )
    config = SimpleNamespace(
        COPILOT_SESSION_ROOT=session_root,
        SESSION_CURSOR_PATH=tmp_path / "cursors.json",
    )
    driver = CopilotDriver("copilot", config)

    assert driver.session_metadata(datetime.now(timezone.utc) + timedelta(days=1)) == {}
