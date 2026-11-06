import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from src.core.drivers.jsonl_session_driver import (
    DEAD_FRAGMENT_SECONDS,
    CopilotDriver,
    JsonlSessionDriver,
)
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


def test_copilot_driver_rereads_a_line_still_being_written(tmp_path):
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

    first = json.dumps({"type": "message", "data": {"role": "user", "content": "first"}})
    second = json.dumps({"type": "message", "data": {"role": "user", "content": "séc"}})
    with event_file.open("a", encoding="utf-8") as events:
        events.write(first + "\n" + second[:20])

    events = driver.extract_entities(driver.observe())
    assert [event["content"] for event in events] == ["first"]

    with event_file.open("a", encoding="utf-8") as events:
        events.write(second[20:] + "\n")

    events = driver.extract_entities(driver.observe())
    assert [event["content"] for event in events] == ["séc"]
    assert driver.observe() == ""


def test_copilot_driver_reads_a_complete_last_line_without_newline(tmp_path):
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

    with event_file.open("a", encoding="utf-8") as events:
        events.write(json.dumps({"type": "message", "data": {"content": "last"}}))

    events = driver.extract_entities(driver.observe())
    assert [event["content"] for event in events] == ["last"]

    with event_file.open("a", encoding="utf-8") as events:
        events.write("\n" + json.dumps({"type": "message", "data": {"content": "next"}}) + "\n")

    events = driver.extract_entities(driver.observe())
    assert [event["content"] for event in events] == ["next"]


def test_copilot_driver_recovers_a_record_appended_to_a_dead_fragment(tmp_path):
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

    now = datetime.now(timezone.utc).isoformat()
    lost = json.dumps({"type": "message", "data": {"content": {"text": "lost"}}})
    kept = json.dumps({"type": "message", "timestamp": now, "data": {"content": "kept"}})
    with event_file.open("a", encoding="utf-8") as events:
        events.write(lost[:40])
    assert driver.observe() == ""

    with event_file.open("a", encoding="utf-8") as events:
        events.write(kept + "\n")

    events = driver.extract_entities(driver.observe())
    assert [event["content"] for event in events] == ["kept"]
    history = driver.history_since(datetime.now(timezone.utc) - timedelta(days=1))
    assert [event["content"] for event in history] == ["kept"]


def _copilot_session(tmp_path, content=""):
    session_root = tmp_path / "copilot"
    event_file = session_root / "session-1" / "events.jsonl"
    event_file.parent.mkdir(parents=True)
    event_file.write_text(content, encoding="utf-8")
    config = SimpleNamespace(
        COPILOT_SESSION_ROOT=session_root,
        SESSION_CURSOR_PATH=tmp_path / "cursors.json",
    )
    return event_file, config


def _append(event_file, text):
    with event_file.open("a", encoding="utf-8") as events:
        events.write(text)


def _age(event_file):
    dead = time.time() - DEAD_FRAGMENT_SECONDS - 1
    os.utime(event_file, (dead, dead))


def _record(content, **fields):
    return json.dumps(
        {
            "type": "message",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"role": "user", "content": content},
            **fields,
        }
    )


def test_copilot_driver_salvages_a_dead_writers_last_line(tmp_path):
    event_file, config = _copilot_session(tmp_path)
    driver = CopilotDriver("copilot", config)
    driver.observe()

    _append(event_file, _record("half of what was said")[:-12])
    assert driver.observe() == ""

    _age(event_file)
    events = driver.extract_entities(driver.observe())
    assert [event["content"] for event in events] == ["half of what [truncated]"]
    history = driver.history_since(datetime.now(timezone.utc) - timedelta(days=1))
    assert [event["content"] for event in history] == ["half of what [truncated]"]
    assert driver.observe() == ""


def test_copilot_driver_splits_where_the_observer_saw_a_fragment_end(tmp_path):
    event_file, config = _copilot_session(tmp_path, _record("before") + "\n")
    driver = CopilotDriver("copilot", config)
    driver.observe()

    # Cut right where a value starts, so the appended object alone could as
    # well be the cut-off record's own nested value.
    fragment = _record("dead")[:-len('{"role": "user", "content": "dead"}}')]
    _append(event_file, fragment)
    driver.observe()
    _append(event_file, json.dumps({"data": {"content": "appended"}}) + "\n")

    events = driver.extract_entities(driver.observe())
    assert [event["content"] for event in events] == ["appended"]
    history = CopilotDriver("copilot", config).history_since(
        datetime.now(timezone.utc) - timedelta(days=1)
    )
    assert [event["content"] for event in history] == ["before", "appended"]
    assert history[1]["timestamp"] is None


def test_unrecorded_fragment_splits_off_a_record_shaped_like_the_files_own(tmp_path):
    fragment = _record("dead")[:30]
    event_file, config = _copilot_session(
        tmp_path, _record("before") + "\n" + fragment + _record("appended") + "\n"
    )

    history = CopilotDriver("copilot", config).history_since(
        datetime.now(timezone.utc) - timedelta(days=1)
    )

    assert [event["content"] for event in history] == ["before", "appended"]


def test_unrecorded_cut_after_a_nested_object_stays_one_record(tmp_path):
    cut_off = _record("nested")[:-1]
    event_file, config = _copilot_session(
        tmp_path, _record("before") + "\n" + cut_off + "\n"
    )

    history = CopilotDriver("copilot", config).history_since(
        datetime.now(timezone.utc) - timedelta(days=1)
    )

    assert [event["content"] for event in history] == ["before", "nested [truncated]"]
    assert history[1]["role"] == "user"


def test_fragment_and_record_arriving_between_polls_keep_the_record(tmp_path):
    event_file, config = _copilot_session(tmp_path)
    driver = CopilotDriver("copilot", config)
    driver.observe()

    _append(
        event_file,
        '{"type":"message","data":'
        + json.dumps({"type": "message", "data": {"content": "kept"}})
        + "\n",
    )

    events = driver.extract_entities(driver.observe())
    assert [event["content"] for event in events] == ["kept"]


def test_fragment_boundary_survives_a_record_appended_without_newline(tmp_path):
    event_file, config = _copilot_session(tmp_path)
    driver = CopilotDriver("copilot", config)
    driver.observe()

    _append(event_file, '{"type":"message","data":')
    assert driver.observe() == ""
    _append(event_file, json.dumps({"data": {"content": "appended"}}))
    assert driver.observe() == ""
    _append(event_file, "\n")

    events = driver.extract_entities(driver.observe())
    assert [event["content"] for event in events] == ["appended"]


def test_salvage_closes_any_cut_point():
    salvage = JsonlSessionDriver._salvage
    assert salvage(b'{"a": "x\\u00') == {"a": "x", "_autograph_salvaged": True}
    assert salvage(b'{"a": "x\\') == {"a": "x", "_autograph_salvaged": True}
    assert salvage(b'{"a": 1, "lo') == {"a": 1, "_autograph_salvaged": True}
    assert salvage(b'{"a": [1, 2, tr') == {"a": [1, 2], "_autograph_salvaged": True}
    assert salvage(b'{"a": {"b": 1.') == {"a": {"b": 1}, "_autograph_salvaged": True}
    assert salvage(b'{"a') is None
    assert salvage(b"garbage") is None


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
