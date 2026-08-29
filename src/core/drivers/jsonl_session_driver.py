import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.core.drivers.base import BaseDriver


class JsonlSessionDriver(BaseDriver):
    """Incrementally reads local JSONL session records for one coding assistant."""

    source_name = ""
    root_attribute = ""
    file_patterns: Iterable[str] = ()
    max_content_length = 12000

    def __init__(self, name: str, config: Any):
        super().__init__(name)
        self.root = Path(getattr(config, self.root_attribute))
        self.cursor_path = Path(config.SESSION_CURSOR_PATH)
        self._cursors = self._load_cursors()

    @property
    def driver_id(self) -> str:
        return self.source_name

    def _load_cursors(self) -> Dict[str, int]:
        if not self.cursor_path.exists():
            return {}

        try:
            with open(self.cursor_path, "r", encoding="utf-8") as cursor_file:
                data = json.load(cursor_file)
        except (OSError, json.JSONDecodeError) as error:
            print(f"⚠️ [{self.source_name}] Could not load session cursors: {error}")
            return {}

        cursors = data.get(self.source_name, {})
        return {
            path: offset
            for path, offset in cursors.items()
            if isinstance(path, str) and isinstance(offset, int) and offset >= 0
        }

    def _save_cursors(self) -> None:
        self.cursor_path.parent.mkdir(parents=True, exist_ok=True)
        all_cursors: Dict[str, Any] = {}
        if self.cursor_path.exists():
            try:
                with open(self.cursor_path, "r", encoding="utf-8") as cursor_file:
                    all_cursors = json.load(cursor_file)
            except (OSError, json.JSONDecodeError):
                all_cursors = {}

        all_cursors[self.source_name] = self._cursors
        temporary_path = self.cursor_path.with_suffix(".tmp")
        with open(temporary_path, "w", encoding="utf-8") as cursor_file:
            json.dump(all_cursors, cursor_file, indent=2, sort_keys=True)
        os.replace(temporary_path, self.cursor_path)

    def _session_files(self) -> List[Path]:
        if not self.root.exists():
            return []

        files = set()
        for pattern in self.file_patterns:
            files.update(path for path in self.root.glob(pattern) if path.is_file())
        return sorted(files)

    def _read_new_records(self, path: Path) -> List[Dict[str, Any]]:
        path_key = str(path)
        size = path.stat().st_size
        saved_offset = self._cursors.get(path_key)
        if saved_offset is None:
            self._cursors[path_key] = size
            return []

        offset = saved_offset if saved_offset <= size else 0
        records = []
        with open(path, "r", encoding="utf-8", errors="replace") as session_file:
            session_file.seek(offset)
            for line in session_file:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
            self._cursors[path_key] = session_file.tell()
        return records

    @staticmethod
    def _first_string(*values: Any) -> Optional[str]:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @classmethod
    def _content_as_text(cls, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, list):
            text = [
                cls._content_as_text(item)
                for item in value
            ]
            joined = "\n".join(item for item in text if item)
            return joined or None
        if isinstance(value, dict):
            return cls._content_as_text(
                value.get("text")
                or value.get("content")
                or value.get("display")
                or value.get("message")
            )
        return None

    def _normalize_record(
        self, record: Dict[str, Any], source_path: Optional[Path] = None
    ) -> Optional[Dict[str, Any]]:
        data = record.get("data")
        payload = record.get("payload")
        message = record.get("message")
        containers = [
            container
            for container in (record, data, payload, message)
            if isinstance(container, dict)
        ]
        content = self._first_string(
            *(
                self._content_as_text(
                    container.get("text")
                    or container.get("content")
                    or container.get("display")
                    or container.get("message")
                )
                for container in containers
            )
        )
        if not content:
            return None

        role = self._first_string(*(container.get("role") for container in containers))
        cwd = self._first_string(*(container.get("cwd") for container in containers))
        timestamp = self._first_string(
            record.get("timestamp"),
            record.get("ts"),
            *(container.get("timestamp") for container in containers[1:]),
        )
        session_id = self._first_string(
            record.get("sessionId"),
            record.get("session_id"),
            *(container.get("sessionId") for container in containers[1:]),
            *(container.get("session_id") for container in containers[1:]),
        )
        if session_id is None and source_path is not None:
            session_id = source_path.parent.name

        return {
            "source": self.source_name,
            "session_id": session_id,
            "timestamp": timestamp,
            "event_type": self._first_string(record.get("type"), "message"),
            "role": role or "unknown",
            "cwd": cwd,
            "content": content[: self.max_content_length],
        }

    @staticmethod
    def _parse_timestamp(timestamp: Optional[str]) -> Optional[datetime]:
        if timestamp is None:
            return None

        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return (
                parsed.replace(tzinfo=timezone.utc)
                if parsed.tzinfo is None
                else parsed.astimezone(timezone.utc)
            )
        except ValueError:
            try:
                numeric_timestamp = float(timestamp)
            except ValueError:
                return None
            if numeric_timestamp > 10_000_000_000:
                numeric_timestamp /= 1000
            return datetime.fromtimestamp(numeric_timestamp, tz=timezone.utc)

    def history_since(self, since: datetime) -> List[Dict[str, Any]]:
        """Read retained session records after ``since`` without changing live cursors."""
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        events = []
        seen = set()
        for path in self._session_files():
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified_at < since:
                continue

            try:
                with open(path, "r", encoding="utf-8", errors="replace") as session_file:
                    for line in session_file:
                        try:
                            record = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if not isinstance(record, dict):
                            continue
                        event = self._normalize_record(record, path)
                        if event is None:
                            continue
                        event_time = self._parse_timestamp(event["timestamp"])
                        if event_time is not None and event_time < since:
                            continue
                        event_key = (
                            event["source"],
                            event["session_id"],
                            event["timestamp"],
                            event["role"],
                            event["content"],
                        )
                        if event_key not in seen:
                            seen.add(event_key)
                            events.append(event)
            except OSError as error:
                print(f"⚠️ [{self.source_name}] Could not read {path.name}: {error}")
        return events

    def observe(self) -> str:
        events = []
        for path in self._session_files():
            try:
                records = self._read_new_records(path)
            except OSError as error:
                print(f"⚠️ [{self.source_name}] Could not read {path.name}: {error}")
                continue
            events.extend(
                event
                for event in (self._normalize_record(record, path) for record in records)
                if event is not None
            )

        self._save_cursors()
        return "\n".join(json.dumps(event) for event in events)

    def extract_entities(self, raw_data: str) -> List[Dict[str, Any]]:
        events = []
        for line in raw_data.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events


class CopilotDriver(JsonlSessionDriver):
    source_name = "copilot"
    root_attribute = "COPILOT_SESSION_ROOT"
    file_patterns = ("**/events.jsonl",)


class ClaudeDriver(JsonlSessionDriver):
    source_name = "claude"
    root_attribute = "CLAUDE_SESSION_ROOT"
    file_patterns = ("history.jsonl", "projects/**/*.jsonl")


class CodexDriver(JsonlSessionDriver):
    source_name = "codex"
    root_attribute = "CODEX_SESSION_ROOT"
    file_patterns = ("history.jsonl", "sessions/**/*.jsonl")


class PiDriver(JsonlSessionDriver):
    source_name = "pi"
    root_attribute = "PI_SESSION_ROOT"
    file_patterns = ("**/*.jsonl",)
