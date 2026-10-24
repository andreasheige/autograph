import json
import zipfile
from datetime import datetime, timezone
from types import SimpleNamespace

from src.core.chatgpt_export import conversation_records, import_export
from src.core.daily_note_renderer import agent_label
from src.core.drivers.jsonl_session_driver import ChatGPTDriver, CodexDriver
from src.core.vault import VaultManager

T = datetime(2026, 10, 20, 9, tzinfo=timezone.utc).timestamp()


def node(node_id, parent, role, text, offset, **metadata):
    message = {
        "author": {"role": role},
        "create_time": T + offset,
        "content": {"content_type": "text", "parts": [text]},
        "metadata": metadata,
    }
    return node_id, {"id": node_id, "parent": parent, "message": message}


CONVERSATION = {
    "id": "abc-123",
    "title": "Threat model the BFF",
    "create_time": T,
    "current_node": "a2",
    "mapping": dict(
        [
            ("root", {"id": "root", "parent": None, "message": None}),
            node("sys", "root", "system", "You are ChatGPT.", 0),
            node("u1", "sys", "user", "Threat model our BFF login.", 1),
            # Regenerated away: not on the branch the chat ended on.
            node("a1", "u1", "assistant", "Discarded answer.", 2, model_slug="gpt-5"),
            node("a2", "u1", "assistant", "Start with token storage.", 3, model_slug="gpt-5.5"),
        ]
    ),
}


def test_records_follow_the_final_branch_and_skip_system_messages():
    conversation_id, records = conversation_records(CONVERSATION)

    assert conversation_id == "abc-123"
    assert [record["role"] for record in records] == ["user", "assistant"]
    assert records[0]["content"] == "Threat model the BFF\n\nThreat model our BFF login."
    assert records[1]["content"] == "Start with token storage."
    assert records[1]["model"] == "gpt-5.5"
    assert records[0]["timestamp"].startswith("2026-10-20T09:00:01")


def test_import_reads_a_zip_and_feeds_the_driver(tmp_path):
    export = tmp_path / "export.zip"
    with zipfile.ZipFile(export, "w") as archive:
        archive.writestr("conversations.json", json.dumps([CONVERSATION, {"id": "empty"}]))
    root = tmp_path / "imports"

    assert import_export(export, root) == (1, 2)
    assert import_export(export, root) == (1, 2)
    assert [path.name for path in root.iterdir()] == ["abc-123.jsonl"]

    config = SimpleNamespace(CHATGPT_IMPORT_ROOT=root, SESSION_CURSOR_PATH=tmp_path / "cursors.json")
    driver = ChatGPTDriver("chatgpt", config)
    since = datetime(2026, 10, 1, tzinfo=timezone.utc)
    events = driver.history_since(since)
    assert {(event["source"], event["session_id"]) for event in events} == {("chatgpt", "abc-123")}
    assert driver.session_metadata(since)["abc-123"]["models"] == ["gpt-5.5"]


def test_codex_desktop_sessions_get_their_own_agent(tmp_path):
    day = tmp_path / "codex" / "sessions" / "2026" / "10" / "20"
    day.mkdir(parents=True)
    for name, originator in [("desktop.jsonl", "Codex Desktop"), ("cli.jsonl", "codex-tui")]:
        (day / name).write_text(
            json.dumps({"type": "session_meta", "payload": {"session_id": name, "originator": originator}})
            + "\n"
            + json.dumps(
                {
                    "timestamp": "2026-10-20T09:00:00Z",
                    "type": "response_item",
                    "payload": {"role": "user", "content": f"work in {name}"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
    config = SimpleNamespace(CODEX_SESSION_ROOT=tmp_path / "codex", SESSION_CURSOR_PATH=tmp_path / "c.json")

    events = CodexDriver("codex", config).history_since(datetime(2026, 10, 1, tzinfo=timezone.utc))

    sources = {event["content"]: event["source"] for event in events}
    assert sources["work in desktop.jsonl"] == "codexdesktop"
    assert sources["work in cli.jsonl"] == "codex"
    assert agent_label("codexdesktop") == "Codex Desktop"


def test_agent_hub_is_written_once_for_new_sources(tmp_path):
    vault = VaultManager(tmp_path)

    assert vault.write_agent_note("chatgpt") is True
    assert vault.write_agent_note("chatgpt") is False
    hub = (tmp_path / "agents" / "ChatGPT.md").read_text(encoding="utf-8")
    assert hub.startswith("# ChatGPT\n\nChatGPT conversations imported")
    assert "[[agents/Ollama|Ollama]]" in hub
