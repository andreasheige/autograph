import json
import os
import re
import time
from datetime import datetime, timezone
from itertools import islice
from pathlib import Path
from typing import Any, Dict, FrozenSet, Iterable, Iterator, List, Optional, Set, Tuple

from src.core.drivers.base import BaseDriver
from src.core.usage import usage_record

# A last line still missing its newline after this long was left by a writer
# that died mid-line; a live write finishes in milliseconds.
DEAD_FRAGMENT_SECONDS = 300
# Marks a record closed from a dead writer's half-written line.
SALVAGED_KEY = "_autograph_salvaged"
TRUNCATED_MARKER = " [truncated]"
# Key overlap with a file's other records at which an object ending a broken
# line counts as a record of its own rather than the tail of a cut-off one.
SHAPE_SIMILARITY = 0.6
MAX_SALVAGE_ATTEMPTS = 64


class JsonlSessionDriver(BaseDriver):
    """Incrementally reads local JSONL session records for one coding assistant."""

    source_name = ""
    root_attribute = ""
    file_patterns: Iterable[str] = ()
    max_content_length = 12000
    model_keys = ("model", "modelId", "newModel")

    def __init__(self, name: str, config: Any):
        super().__init__(name)
        self.root = Path(getattr(config, self.root_attribute))
        self.cursor_path = Path(config.SESSION_CURSOR_PATH)
        self._cursors, self._fragments = self._load_cursors()

    @property
    def driver_id(self) -> str:
        return self.source_name

    def _load_cursors(self) -> Tuple[Dict[str, int], Dict[str, Dict[str, List[int]]]]:
        """Read offsets per file, and the lengths of unfinished lines seen at them."""
        if not self.cursor_path.exists():
            return {}, {}

        try:
            with open(self.cursor_path, "r", encoding="utf-8") as cursor_file:
                data = json.load(cursor_file)
        except (OSError, json.JSONDecodeError) as error:
            print(f"⚠️ [{self.source_name}] Could not load session cursors: {error}")
            return {}, {}

        cursors = data.get(self.source_name, {})
        fragments = data.get("_fragments", {}).get(self.source_name, {})
        return (
            {
                path: offset
                for path, offset in cursors.items()
                if isinstance(path, str) and isinstance(offset, int) and offset >= 0
            },
            {
                path: {
                    # A single length is how one was kept before they became lists.
                    offset: [
                        length
                        for length in (lengths if isinstance(lengths, list) else [lengths])
                        if isinstance(length, int) and length > 0
                    ]
                    for offset, lengths in by_offset.items()
                }
                for path, by_offset in fragments.items()
                if isinstance(path, str) and isinstance(by_offset, dict)
            },
        )

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
        all_cursors.setdefault("_fragments", {})[self.source_name] = self._fragments
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

        if saved_offset > size:
            saved_offset = 0
            self._fragments.pop(path_key, None)
        records, self._cursors[path_key] = self._read_records(
            path, saved_offset, observing=True
        )
        return records

    def _read_records(
        self,
        path: Path,
        offset: int = 0,
        observing: bool = False,
        must_contain: Optional[bytes] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Records from ``offset`` on, and the offset after the last one read.

        A last line without a newline is either a complete record whose writer
        never terminates it, one still being written, or a fragment left by a
        writer that died mid-line. Reading stops before one still being written
        so the next run reads it once complete. When ``observing``, every length
        such a line is seen at is kept, so that once a new record is appended to
        a dead fragment, the line splits exactly where the fragment ended.
        """
        path_key = str(path)
        if observing:
            fragments = self._fragments.setdefault(path_key, {})
        else:
            fragments = self._fragments.get(path_key, {})
        stale = time.time() - path.stat().st_mtime >= DEAD_FRAGMENT_SECONDS
        start = offset
        entries: List[Any] = []
        # Binary mode so offsets are exact bytes to stop short of the end at;
        # text-mode tell() is an opaque cookie.
        with open(path, "rb") as session_file:
            session_file.seek(offset)
            for line in session_file:
                fragment_key = str(offset)
                if must_contain is not None and must_contain not in line:
                    offset += len(line)
                    continue
                record = self._load_record(line)
                if record is not None:
                    entries.append(record)
                    if observing:
                        fragments.pop(fragment_key, None)
                else:
                    if not line.endswith(b"\n"):
                        if observing:
                            lengths = fragments.setdefault(fragment_key, [])
                            if len(line) not in lengths:
                                lengths.append(len(line))
                        if not stale:
                            break
                    entries.extend(self._recover(line, fragments.get(fragment_key, [])))
                offset += len(line)
        if observing and not fragments:
            self._fragments.pop(path_key, None)

        # Only a broken line needs the file's record shapes to be judged, and
        # from the whole file: a batch may hold nothing but the broken line.
        shapes: Set[FrozenSet[str]] = set()
        if any(isinstance(entry, tuple) for entry in entries):
            earlier: List[Any] = []
            if start:
                with open(path, "rb") as session_file:
                    earlier = [
                        self._load_record(line)
                        for line in session_file.read(start).splitlines()
                    ]
            shapes = {
                frozenset(entry)
                for entry in earlier + entries
                if isinstance(entry, dict) and not entry.get(SALVAGED_KEY)
            }
        records = []
        for entry in entries:
            if isinstance(entry, dict):
                records.append(entry)
                continue
            prefix, candidate, line = entry
            whole = self._salvage(line)
            if self._is_own_record(candidate, whole, shapes):
                parts = [self._salvage(prefix), candidate]
            else:
                parts = [whole]
            records.extend(part for part in parts if part is not None)
        return records, offset

    @staticmethod
    def _load_record(line: bytes) -> Optional[Dict[str, Any]]:
        try:
            record = json.loads(line.decode("utf-8", errors="replace"))
        except json.JSONDecodeError:
            return None
        return record if isinstance(record, dict) else None

    def _recover(self, line: bytes, fragment_lengths: List[int]) -> List[Any]:
        """What a line that does not parse holds, once its writer is done with it.

        A writer that died mid-line leaves a fragment, and the next record is
        appended to it. With a length the fragment was seen at, the split is exact.
        Otherwise a complete object the line ends with is returned as
        ``(prefix, object, line)`` for ``_read_records`` to judge against the
        file's other records, and a line with none is salvaged whole.
        """
        line = line.rstrip(b"\r\n")
        for length in fragment_lengths:
            record = self._load_record(line[length:]) if length < len(line) else None
            if record is not None:
                parts = [self._salvage(line[:length]), record]
                return [part for part in parts if part is not None]

        start = line.find(b"{", 1)
        while start != -1:
            candidate = self._load_record(line[start:])
            if candidate is not None:
                return [(line[:start], candidate, line)]
            start = line.find(b"{", start + 1)
        salvaged = self._salvage(line)
        return [salvaged] if salvaged is not None else []

    def _is_own_record(
        self,
        candidate: Dict[str, Any],
        whole: Optional[Dict[str, Any]],
        shapes: Set[FrozenSet[str]],
    ) -> bool:
        """Whether an object ending a broken line is a record of its own.

        A record cut off right after a nested object reads byte for byte like a
        fragment with a new record appended. Records in one file share most of
        their keys and nested objects do not (over real Claude, Codex, Copilot
        and Pi sessions, 2 of 1.2M nested objects reach the threshold), so key
        overlap decides. A file with no other record to compare splits unless
        reading the line whole, ``whole``, keeps the object's content too.
        """
        keys = frozenset(candidate)
        if not keys:
            return False
        if shapes:
            return any(
                len(keys & shape) / len(keys | shape) >= SHAPE_SIMILARITY
                for shape in shapes
            )
        candidate_event = self._normalize_record(candidate)
        if candidate_event is None:
            return False
        whole_event = self._normalize_record(whole) if whole is not None else None
        return whole_event is None or candidate_event["content"] not in whole_event["content"]

    @staticmethod
    def _salvage(fragment: bytes) -> Optional[Dict[str, Any]]:
        """Close a dead writer's half-written record, marked as salvaged.

        Ends an open string and closes open objects and arrays. Where the cut
        leaves a key, number or literal unfinished, backs up to the last point
        outside a string at which closing gives valid JSON.
        """
        text = fragment.decode("utf-8", errors="replace").strip()
        closers: List[str] = []
        cuts: List[Tuple[int, str]] = []
        in_string = escaped = False
        for position, char in enumerate(text):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            cuts.append((position, "".join(reversed(closers))))
            if char == '"':
                in_string = True
            elif char in "{[":
                closers.append("}" if char == "{" else "]")
            elif char in "}]" and closers:
                closers.pop()
        closing = "".join(reversed(closers))

        def attempts() -> Iterator[str]:
            if in_string:
                yield text + '"' + closing
                # Cut inside an escape: drop the unfinished \ or \uXXXX.
                yield re.sub(r"\\(u[0-9a-fA-F]{0,3})?$", "", text) + '"' + closing
            yield text + closing
            for position, closed in reversed(cuts):
                yield text[:position] + closed

        for attempt in islice(attempts(), MAX_SALVAGE_ATTEMPTS):
            try:
                record = json.loads(attempt)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict) and record:
                record[SALVAGED_KEY] = True
                return record
        return None

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
        session_id = self._record_session_id(record)
        if session_id is None and source_path is not None:
            session_id = source_path.parent.name

        return {
            "source": self._source_for(source_path),
            "session_id": session_id,
            "timestamp": timestamp,
            "event_type": self._first_string(record.get("type"), "message"),
            "role": role or "unknown",
            "cwd": cwd,
            "content": content[: self.max_content_length]
            + (TRUNCATED_MARKER if record.get(SALVAGED_KEY) else ""),
        }

    def _source_for(self, source_path: Optional[Path]) -> str:
        """The agent a session file belongs to; one per driver unless overridden."""
        return self.source_name

    @classmethod
    def _record_containers(cls, record: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [
            container
            for container in (
                record.get("data"),
                record.get("payload"),
                record.get("message"),
            )
            if isinstance(container, dict)
        ]

    @classmethod
    def _record_session_id(cls, record: Dict[str, Any]) -> Optional[str]:
        containers = cls._record_containers(record)
        return cls._first_string(
            record.get("sessionId"),
            record.get("session_id"),
            *(container.get("sessionId") for container in containers),
            *(container.get("session_id") for container in containers),
        )

    @classmethod
    def _record_models(cls, record: Dict[str, Any]) -> List[str]:
        """Read model identifiers from the differing shapes each assistant writes."""
        return [
            container[key].strip()
            for container in [record] + cls._record_containers(record)
            for key in cls.model_keys
            if isinstance(container.get(key), str)
            and container[key].strip()
            # Claude writes "<synthetic>" for locally generated messages; angle
            # brackets mark a placeholder, never a model that ran.
            and "<" not in container[key]
        ]

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
                records, _ = self._read_records(path)
            except OSError as error:
                print(f"⚠️ [{self.source_name}] Could not read {path.name}: {error}")
                continue
            for record in records:
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
        return events

    def session_metadata(self, since: datetime) -> Dict[str, Dict[str, Any]]:
        """Read per-session identity for retained sessions without changing cursors."""
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        sessions: Dict[str, Dict[str, Any]] = {}
        for path in self._session_files():
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified_at < since:
                continue

            session_id = None
            models: List[str] = []
            try:
                records, _ = self._read_records(path)
            except OSError as error:
                print(f"⚠️ [{self.source_name}] Could not read {path.name}: {error}")
                continue
            for record in records:
                session_id = session_id or self._record_session_id(record)
                for model in self._record_models(record):
                    if model not in models:
                        models.append(model)

            sessions[session_id or path.parent.name] = {
                "models": models,
                "transcript": self._transcript_reference(path),
            }
        return sessions

    def usage_since(self, since: datetime) -> List[Dict[str, Any]]:
        """Priced token usage per API response after ``since``, without changing cursors.

        Only Claude writes usage into its session lines; other agents yield nothing.
        Each response is counted once, however many lines repeat it.
        """
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)

        records: Dict[str, Dict[str, Any]] = {}
        for path in self._session_files():
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified_at < since:
                continue
            try:
                file_records, _ = self._read_records(path, must_contain=b'"usage"')
            except OSError as error:
                print(f"⚠️ [{self.source_name}] Could not read {path.name}: {error}")
                continue
            for record in file_records:
                # A salvaged record's usage may be cut off part way: no price
                # beats a wrong one.
                if record.get(SALVAGED_KEY):
                    continue
                usage = usage_record(record)
                if usage is None or usage["message_id"] in records:
                    continue
                timestamp = self._parse_timestamp(usage["timestamp"])
                if timestamp is None or timestamp < since:
                    continue
                usage["timestamp"] = timestamp
                usage["source"] = self.source_name
                if usage["session_id"] is None:
                    usage["session_id"] = path.stem
                records[usage["message_id"]] = usage
        return sorted(records.values(), key=lambda usage: usage["timestamp"])

    def _transcript_reference(self, path: Path) -> str:
        """Describe a session file without writing an absolute path into the vault."""
        try:
            return f"{self.root.name}/{path.relative_to(self.root).as_posix()}"
        except ValueError:
            return path.name

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
    # The Codex desktop app writes to the same folder as the CLI and editor
    # plugins; only the first record's `originator` tells its sessions apart.
    desktop_originators = {"Codex Desktop", "codex_work_desktop"}

    def __init__(self, name: str, config: Any):
        super().__init__(name, config)
        self._file_sources: Dict[Path, str] = {}

    def _source_for(self, source_path: Optional[Path]) -> str:
        if source_path is None:
            return self.source_name
        if source_path not in self._file_sources:
            source = self.source_name
            try:
                with open(source_path, "r", encoding="utf-8", errors="replace") as session_file:
                    first = json.loads(session_file.readline() or "{}")
                payload = first.get("payload") if isinstance(first, dict) else None
                if isinstance(payload, dict) and payload.get("originator") in self.desktop_originators:
                    source = "codexdesktop"
            except (OSError, json.JSONDecodeError):
                pass
            self._file_sources[source_path] = source
        return self._file_sources[source_path]


class PiDriver(JsonlSessionDriver):
    source_name = "pi"
    root_attribute = "PI_SESSION_ROOT"
    file_patterns = ("**/*.jsonl",)


class ChatGPTDriver(JsonlSessionDriver):
    """Reads conversations run_chatgpt_import.py wrote from a ChatGPT data export."""

    source_name = "chatgpt"
    root_attribute = "CHATGPT_IMPORT_ROOT"
    file_patterns = ("*.jsonl",)


class ClaudeDesktopDriver(JsonlSessionDriver):
    """Reads conversations the user explicitly saved from the Claude desktop app."""

    source_name = "claudedesktop"
    root_attribute = "DESKTOP_CAPTURE_ROOT"
    file_patterns = ("*.jsonl",)
