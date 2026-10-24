"""MCP stdio server that saves a Claude desktop conversation to Autograph on request.

Desktop chats live on claude.ai, not on disk, so nothing can read them after the
fact. Claude summarises the conversation itself and passes the summary to the
``save_to_autograph`` tool, which writes two things:

- a standalone note at ``sessions/claudedesktop/<id>.md`` in the vault, the same
  path a daily note's **Session:** link points to, and
- one event in ``DESKTOP_CAPTURE_ROOT/<date>.jsonl`` that ``ClaudeDesktopDriver``
  feeds into the daily-note pipeline.

Stdlib only, and stdout carries the protocol: never print to it.
"""

import json
import re
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from config.settings import Config
from src.core.daily_note_renderer import (
    agent_note_link,
    daily_note_link,
    project_note_link,
)
from src.core.projects import find_repositories, project_groups
from src.core.vocabulary import append_proposals, sort_tags

SOURCE = "claudedesktop"
PROTOCOL_VERSION = "2025-06-18"

TOOL = {
    "name": "save_to_autograph",
    "description": (
        "Save the current conversation to the user's Autograph vault, where it "
        "becomes a standalone note and part of that day's daily note. Call this "
        "when the user says \"autograph this\", \"save this\", \"save this to "
        "Autograph\" or something similar. Never call it unprompted. Before "
        "calling, summarise the whole conversation: what was explored or "
        "decided, findings worth keeping, open questions, and links to any "
        "artifacts or sources. Write it so the user can pick the work up weeks "
        "later without the chat."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short title for the note."},
            "summary": {
                "type": "string",
                "description": "Markdown summary of the conversation: context, what was done, findings.",
            },
            "decisions": {"type": "array", "items": {"type": "string"}},
            "open_questions": {"type": "array", "items": {"type": "string"}},
            "links": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Artifact URLs, sources, docs referenced.",
            },
            "project": {
                "type": "string",
                "description": "Repository or project name this relates to, if any.",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Specific topic tags, lowercase kebab-case. Prefer established "
                    "terms (SWEBOK, NIST SSDF, OWASP LLM/Agentic Top 10, DORA, MCP). "
                    "They are checked against the vault vocabulary; unknown ones are "
                    "kept as proposals for the owner to review."
                ),
            },
        },
        "required": ["title", "summary"],
    },
}


def _one_line(value: str) -> str:
    return " ".join(value.split())


def _slug(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:48].strip("-") or "capture"


def _strings(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    return [_one_line(value) for value in values if isinstance(value, str) and value.strip()]


def _tags(values: Any) -> List[str]:
    """Normalize to the vocabulary's label shape: lowercase kebab-case."""
    tags: List[str] = []
    for value in _strings(values):
        tag = re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")
        if tag and tag != "autograph-capture" and tag not in tags:
            tags.append(tag)
    return tags


def _project_cwd(
    project: Optional[str], search_dirs: Iterable[Path], groups: Iterable[Path] = ()
) -> Optional[str]:
    """Point the event at a repository so the daily note can attribute it."""
    if not project:
        return None
    for search_dir in search_dirs:
        candidate = Path(search_dir) / project
        if (candidate / ".git").exists():
            return str(candidate)
    # Not a top-level repository: a nested one, or a group such as cmks.
    repositories = find_repositories(search_dirs)
    for folder in [*project_groups(repositories, search_dirs, groups), *repositories]:
        if folder.name == project:
            return str(folder)
    return None


def _section(heading: str, items: List[str]) -> List[str]:
    if not items:
        return []
    return ["", f"## {heading}"] + [f"- {item}" for item in items]


def save_capture(arguments: Dict[str, Any], config: Any, now: Optional[datetime] = None) -> Dict[str, str]:
    title = _one_line(str(arguments.get("title") or ""))
    summary = str(arguments.get("summary") or "").strip()
    if not title or not summary:
        raise ValueError("title and summary are required")

    now = now or datetime.now(timezone.utc)
    local_now = now.astimezone()
    date = local_now.date().isoformat()
    project = _one_line(str(arguments.get("project") or "")) or None
    decisions = _strings(arguments.get("decisions"))
    open_questions = _strings(arguments.get("open_questions"))
    links = _strings(arguments.get("links"))
    tags = _tags(arguments.get("tags"))
    proposed: List[str] = []
    new_labels: List[str] = []
    vocabulary = Path(config.VAULT_ROOT) / "vocabulary.md"
    if vocabulary.is_file():
        tags, proposed, new_labels = sort_tags(
            tags, vocabulary.read_text(encoding="utf-8", errors="replace")
        )
    # autograph-capture marks where the note came from, so it is never sorted.
    tags = ["autograph-capture"] + tags

    session_dir = Path(config.VAULT_ROOT) / "sessions" / SOURCE
    session_dir.mkdir(parents=True, exist_ok=True)
    capture_id = f"{_slug(title)}-{secrets.token_hex(3)}"
    while (session_dir / f"{capture_id}.md").exists():
        capture_id = f"{_slug(title)}-{secrets.token_hex(3)}"

    header = [
        "---",
        f"title: {json.dumps(title)}",
        f"date: {date}",
        f"source: {SOURCE}",
    ]
    if project:
        header.append(f"project: {json.dumps(project)}")
    header.append(f"tags: [{', '.join(tags)}]")
    if proposed:
        header.append(f"proposed_tags: [{', '.join(proposed)}]")
    header.append("---")
    meta = (
        f"**Saved:** {local_now.strftime('%Y-%m-%d %H:%M')} · "
        f"**Agent:** {agent_note_link(SOURCE)} · **Day:** {daily_note_link(date)}"
    )
    if project:
        meta += f" · **Project:** {project_note_link(project)}"
    lines = header + ["", f"# {title}", "", meta, "", "## Summary", "", summary]
    lines += _section("Decisions", decisions)
    lines += _section("Open questions", open_questions)
    lines += _section("Links", links)
    note_path = session_dir / f"{capture_id}.md"
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    append_proposals(vocabulary, new_labels, f"proposed by {SOURCE} capture {capture_id} on {date}")

    content = [f"Saved Claude Desktop conversation: {title}", "", summary]
    if decisions:
        content += ["", "Decisions:"] + [f"- {item}" for item in decisions]
    if open_questions:
        content += ["", "Open questions:"] + [f"- {item}" for item in open_questions]
    event = {
        "type": "capture",
        "timestamp": now.isoformat(),
        "session_id": capture_id,
        "role": "user",
        "cwd": _project_cwd(project, config.SEARCH_DIRS, config.PROJECT_GROUPS),
        "content": "\n".join(content),
    }
    capture_root = Path(config.DESKTOP_CAPTURE_ROOT)
    capture_root.mkdir(parents=True, exist_ok=True)
    with open(capture_root / f"{date}.jsonl", "a", encoding="utf-8") as capture_file:
        capture_file.write(json.dumps(event) + "\n")

    return {"id": capture_id, "date": date, "note": f"sessions/{SOURCE}/{capture_id}.md"}


def handle(message: Dict[str, Any], config: Any) -> Optional[Dict[str, Any]]:
    """Answer one JSON-RPC message; notifications get no response."""
    method = message.get("method")
    if "id" not in message:
        return None
    response: Dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"]}
    params = message.get("params") or {}

    if method == "initialize":
        response["result"] = {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "autograph-capture", "version": "1.0.0"},
        }
    elif method == "ping":
        response["result"] = {}
    elif method == "tools/list":
        response["result"] = {"tools": [TOOL]}
    elif method == "tools/call" and params.get("name") == TOOL["name"]:
        try:
            saved = save_capture(params.get("arguments") or {}, config)
        except (ValueError, OSError) as error:
            text, is_error = f"Not saved: {error}", True
        else:
            text = (
                f"Saved to Autograph as {saved['note']}. It joins the "
                f"{saved['date']} daily note on the next backfill."
            )
            is_error = False
        response["result"] = {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        }
    else:
        response["error"] = {"code": -32601, "message": f"Unknown method: {method}"}
    return response


def serve(config: Any = None, stdin=sys.stdin, stdout=sys.stdout) -> None:
    config = config or Config()
    for line in stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            response: Optional[Dict[str, Any]] = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
        else:
            response = handle(message, config) if isinstance(message, dict) else None
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
