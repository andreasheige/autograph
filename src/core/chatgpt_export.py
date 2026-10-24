"""Turn a ChatGPT data export into session JSONL that ChatGPTDriver reads.

ChatGPT keeps conversations on OpenAI's servers, so the export (Settings ->
Data controls -> Export data) is the only local copy. Each conversation is a
tree of messages; only the branch the conversation ended on is kept, so
regenerated answers that were discarded don't count as work.
"""
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

CONVERSATION_FILE = re.compile(r"(^|/)conversations(-\d+)?\.json$")
SAFE_ID = re.compile(r"[^A-Za-z0-9-]")


def _load_conversations(export: Path) -> Iterator[Dict[str, Any]]:
    """Yield conversations from an export .zip, its unpacked folder or a .json."""
    if export.is_file() and export.suffix == ".json":
        payloads = [export.read_text(encoding="utf-8")]
    elif export.is_file():
        with zipfile.ZipFile(export) as archive:
            payloads = [
                archive.read(name).decode("utf-8")
                for name in sorted(archive.namelist())
                if CONVERSATION_FILE.search(name)
            ]
    else:
        payloads = [
            path.read_text(encoding="utf-8")
            for path in sorted(export.rglob("conversations*.json"))
            if CONVERSATION_FILE.search(path.as_posix())
        ]
    for payload in payloads:
        data = json.loads(payload)
        for conversation in data if isinstance(data, list) else []:
            if isinstance(conversation, dict):
                yield conversation


def _timestamp(value: Any) -> Optional[str]:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _text(message: Dict[str, Any]) -> Optional[str]:
    content = message.get("content")
    if not isinstance(content, dict):
        return None
    # Custom instructions and memory edits are settings, not conversation.
    if content.get("content_type") in {"user_editable_context", "model_editable_context"}:
        return None
    parts = [part for part in content.get("parts") or [] if isinstance(part, str)]
    if isinstance(content.get("text"), str):
        parts.append(content["text"])
    text = "\n".join(part for part in parts if part.strip()).strip()
    return text or None


def _active_branch(conversation: Dict[str, Any]) -> List[Dict[str, Any]]:
    mapping = conversation.get("mapping")
    if not isinstance(mapping, dict):
        return []
    branch = []
    node_id = conversation.get("current_node")
    seen = set()
    while isinstance(node_id, str) and node_id in mapping and node_id not in seen:
        seen.add(node_id)
        node = mapping[node_id]
        if isinstance(node.get("message"), dict):
            branch.append(node["message"])
        node_id = node.get("parent")
    return list(reversed(branch))


def conversation_records(conversation: Dict[str, Any]) -> Tuple[str, List[Dict[str, Any]]]:
    """The conversation's file-safe id and one record per visible message."""
    conversation_id = SAFE_ID.sub("", str(conversation.get("conversation_id") or conversation.get("id") or ""))
    title = str(conversation.get("title") or "Untitled ChatGPT conversation")
    fallback_time = _timestamp(conversation.get("create_time"))
    records = []
    for message in _active_branch(conversation):
        role = (message.get("author") or {}).get("role")
        metadata = message.get("metadata") or {}
        if role not in {"user", "assistant"} or metadata.get("is_visually_hidden_from_conversation"):
            continue
        text = _text(message)
        if text is None:
            continue
        record = {
            "type": "message",
            "session_id": conversation_id,
            "timestamp": _timestamp(message.get("create_time")) or fallback_time,
            "role": role,
            "content": text if records else f"{title}\n\n{text}",
        }
        if isinstance(metadata.get("model_slug"), str):
            record["model"] = metadata["model_slug"]
        records.append(record)
    return conversation_id, records


def import_export(export: Path, root: Path) -> Tuple[int, int]:
    """Write one JSONL file per conversation under `root`; returns (conversations, messages).

    The export always holds the whole history, so each file is rewritten
    from it, and importing a newer export updates conversations in place.
    """
    root.mkdir(parents=True, exist_ok=True)
    conversations = messages = 0
    for conversation in _load_conversations(Path(export).expanduser()):
        conversation_id, records = conversation_records(conversation)
        if not conversation_id or not records:
            continue
        content = "".join(json.dumps(record) + "\n" for record in records)
        path = root / f"{conversation_id}.jsonl"
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            path.write_text(content, encoding="utf-8")
        conversations += 1
        messages += len(records)
    return conversations, messages
