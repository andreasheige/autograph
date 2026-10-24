import io
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.agents.desktop_capture_server import serve
from src.core.drivers.jsonl_session_driver import ClaudeDesktopDriver


def _config(tmp_path):
    repo = tmp_path / "dev" / "autograph"
    (repo / ".git").mkdir(parents=True)
    return SimpleNamespace(
        VAULT_ROOT=tmp_path / "vault",
        DESKTOP_CAPTURE_ROOT=tmp_path / "captures",
        SEARCH_DIRS=[tmp_path / "dev"],
        PROJECT_GROUPS=[],
        SESSION_CURSOR_PATH=tmp_path / "cursors.json",
    )


def _run(config, *messages):
    stdin = io.StringIO("".join(json.dumps(message) + "\n" for message in messages))
    stdout = io.StringIO()
    serve(config, stdin=stdin, stdout=stdout)
    return [json.loads(line) for line in stdout.getvalue().splitlines()]


def _call(arguments):
    return {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {"name": "save_to_autograph", "arguments": arguments},
    }


def test_handshake_lists_the_tool_and_skips_notifications(tmp_path):
    responses = _run(
        _config(tmp_path),
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )

    assert [response["id"] for response in responses] == [1, 2]
    assert responses[0]["result"]["protocolVersion"] == "2025-06-18"
    tool = responses[1]["result"]["tools"][0]
    assert tool["name"] == "save_to_autograph"
    assert "autograph this" in tool["description"]


def test_save_writes_note_and_event_the_driver_reads(tmp_path):
    config = _config(tmp_path)
    responses = _run(
        config,
        _call(
            {
                "title": "Research: MCP capture\nfor desktop",
                "summary": "Desktop chats live server-side.",
                "decisions": ["Use an MCP tool"],
                "links": ["https://claude.ai/artifact/abc"],
                "project": "autograph",
                "tags": ["research", "bad tag!"],
            }
        ),
    )

    result = responses[0]["result"]
    assert result["isError"] is False
    notes = list((config.VAULT_ROOT / "sessions" / "claudedesktop").glob("*.md"))
    assert len(notes) == 1
    note = notes[0].read_text(encoding="utf-8")
    assert notes[0].stem.startswith("research-mcp-capture-for-desktop-")
    assert '# Research: MCP capture for desktop' in note
    assert "tags: [autograph-capture, research, bad-tag]" in note
    assert "- Use an MCP tool" in note
    assert "[[projects/autograph|autograph]]" in note

    driver = ClaudeDesktopDriver("claudedesktop", config)
    since = datetime.now(timezone.utc) - timedelta(days=1)
    events = driver.history_since(since)
    assert len(events) == 1
    assert events[0]["session_id"] == notes[0].stem
    assert events[0]["cwd"] == str(tmp_path / "dev" / "autograph")
    assert "Desktop chats live server-side." in events[0]["content"]
    assert notes[0].stem in driver.session_metadata(since)


def test_missing_summary_is_reported_not_raised(tmp_path):
    config = _config(tmp_path)
    responses = _run(config, _call({"title": "Only a title"}))

    assert responses[0]["result"]["isError"] is True
    assert not config.DESKTOP_CAPTURE_ROOT.exists()


def test_save_sorts_tags_against_the_vault_vocabulary(tmp_path):
    config = _config(tmp_path)
    config.VAULT_ROOT.mkdir(parents=True)
    vocabulary = config.VAULT_ROOT / "vocabulary.md"
    vocabulary.write_text(
        "# Vocabulary\n\n"
        "- [x] agent-harness; alt: harness-engineering; scheme: local; def: Harness\n"
        "- [x] knowit; scheme: local; def: Employer\n"
        "- [x] setup; retired: too generic; use: agent-harness\n"
        "- [ ] client-brain; scheme: local; def: Client\n"
        "\n## Proposed by captures\n\n"
        "Unknown tags land here.\n",
        encoding="utf-8",
    )

    responses = _run(
        config,
        _call(
            {
                "title": "Client kick-off",
                "summary": "Straw-man architecture.",
                "tags": ["Harness Engineering", "knowit", "setup", "client-brain",
                         "AI architecture", "kick-off", "autograph-capture"],
            }
        ),
    )

    assert responses[0]["result"]["isError"] is False
    note_path = next((config.VAULT_ROOT / "sessions" / "claudedesktop").glob("*.md"))
    note = note_path.read_text(encoding="utf-8")
    assert "tags: [autograph-capture, agent-harness, knowit]\n" in note
    assert "proposed_tags: [client-brain, ai-architecture, kick-off]\n" in note
    text = vocabulary.read_text(encoding="utf-8")
    assert text.endswith(
        "Unknown tags land here.\n"
        f"- [ ] ai-architecture  <!-- proposed by claudedesktop capture {note_path.stem} on "
        f"{note.split('date: ')[1][:10]} -->\n"
        f"- [ ] kick-off  <!-- proposed by claudedesktop capture {note_path.stem} on "
        f"{note.split('date: ')[1][:10]} -->\n"
    )
    assert text.count("client-brain") == 1
