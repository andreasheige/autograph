from dataclasses import dataclass, field
from datetime import datetime, timedelta
from hashlib import sha256
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


MAX_EVENT_CONTENT = 1600
MAX_UNIT_EVIDENCE = 6000
MAX_DAILY_WORK_UNITS = 6
COMMIT_ASSOCIATION_WINDOW = timedelta(hours=4)


@dataclass(frozen=True)
class Commit:
    id: str
    title: str
    project: str
    timestamp: datetime


@dataclass
class WorkUnit:
    date: str
    project: str
    source: str
    session_id: str
    start: datetime
    end: datetime
    events: List[Dict[str, str]] = field(default_factory=list)
    commits: List[Commit] = field(default_factory=list)

    @property
    def score(self) -> Tuple[int, int]:
        unique_messages = {event["content"] for event in self.events}
        return len(unique_messages), len(self.events)

    def prompt(self) -> str:
        evidence = []
        length = 0
        for event in self.events:
            line = (
                f"[{event['timestamp']}] {event['source']} "
                f"{event['role']}: {event['content']}"
            )
            if evidence and length + len(line) > MAX_UNIT_EVIDENCE:
                break
            evidence.append(line)
            length += len(line)

        commits = "\n".join(
            f"- {commit.id}: {commit.title}" for commit in self.commits
        ) or "None associated"
        return (
            f"Project: {self.project}\n"
            f"Session source: {self.source}\n"
            f"Session ID: {self.session_id}\n"
            f"Time range: {self.start.isoformat()} to {self.end.isoformat()}\n\n"
            f"Associated commits:\n{commits}\n\n"
            f"Evidence:\n" + "\n".join(evidence)
        )


def _normalize_content(content: object) -> Optional[str]:
    if not isinstance(content, str):
        return None
    normalized = re.sub(r"\s+", " ", content).strip()
    if len(normalized) < 4:
        return None
    return normalized[:MAX_EVENT_CONTENT]


def _project_for_cwd(cwd: object, repositories: Iterable[Path]) -> str:
    if not isinstance(cwd, str) or not cwd.strip():
        return "unassigned"
    try:
        cwd_path = Path(cwd).expanduser().resolve()
    except OSError:
        return "unassigned"

    for repository in repositories:
        try:
            cwd_path.relative_to(repository)
            return repository.name
        except ValueError:
            continue
    return "unassigned"


def normalize_events(
    events: Iterable[Dict[str, object]], repositories: Iterable[Path], parse_timestamp
) -> List[Dict[str, object]]:
    """Retain unique, human-authored session messages with useful context."""
    repositories = list(repositories)
    normalized_events = []
    seen = set()
    for event in events:
        timestamp = parse_timestamp(event.get("timestamp"))
        content = _normalize_content(event.get("content"))
        if timestamp is None or content is None:
            continue
        role = str(event.get("role") or "unknown").lower()
        if role in {"tool", "system"}:
            continue
        source = str(event.get("source") or "unknown")
        session_id = str(event.get("session_id") or "unknown-session")
        project = _project_for_cwd(event.get("cwd"), repositories)
        deduplication_key = (
            source,
            session_id,
            role,
            sha256(content.encode("utf-8")).hexdigest(),
        )
        if deduplication_key in seen:
            continue
        seen.add(deduplication_key)
        normalized_events.append(
            {
                "timestamp": timestamp,
                "date": timestamp.date().isoformat(),
                "project": project,
                "source": source,
                "session_id": session_id,
                "role": role,
                "content": content,
            }
        )
    return sorted(normalized_events, key=lambda event: event["timestamp"])


def build_work_units(
    events: Iterable[Dict[str, object]], commits: Iterable[Commit]
) -> Dict[str, List[WorkUnit]]:
    """Group normalized events and associate each unit with its nearest commit."""
    groups: Dict[Tuple[str, str, str, str], List[Dict[str, object]]] = {}
    for event in events:
        key = (
            event["date"],
            event["project"],
            event["source"],
            event["session_id"],
        )
        groups.setdefault(key, []).append(event)

    commits_by_date: Dict[str, List[Commit]] = {}
    for commit in commits:
        commits_by_date.setdefault(commit.timestamp.date().isoformat(), []).append(commit)

    units_by_date: Dict[str, List[WorkUnit]] = {}
    for (date, project, source, session_id), unit_events in groups.items():
        unit = WorkUnit(
            date=date,
            project=project,
            source=source,
            session_id=session_id,
            start=unit_events[0]["timestamp"],
            end=unit_events[-1]["timestamp"],
            events=[
                {
                    "timestamp": event["timestamp"].isoformat(),
                    "source": str(event["source"]),
                    "role": str(event["role"]),
                    "content": str(event["content"]),
                }
                for event in unit_events
            ],
        )
        candidates = [
            commit
            for commit in commits_by_date.get(date, [])
            if commit.project == project and commit.timestamp >= unit.end
        ]
        if candidates:
            nearest = min(candidates, key=lambda commit: commit.timestamp)
            if nearest.timestamp - unit.end <= COMMIT_ASSOCIATION_WINDOW:
                unit.commits = [nearest]
        units_by_date.setdefault(date, []).append(unit)

    for date, date_commits in commits_by_date.items():
        if date not in units_by_date:
            units_by_date[date] = [
                WorkUnit(
                    date=date,
                    project=commit.project,
                    source="git",
                    session_id=commit.id,
                    start=commit.timestamp,
                    end=commit.timestamp,
                    events=[
                        {
                            "timestamp": commit.timestamp.isoformat(),
                            "source": "git",
                            "role": "commit",
                            "content": commit.title,
                        }
                    ],
                    commits=[commit],
                )
                for commit in date_commits
            ]

    return {
        date: sorted(units, key=lambda unit: unit.score, reverse=True)[:MAX_DAILY_WORK_UNITS]
        for date, units in units_by_date.items()
    }


def fingerprint_work_day(units: Iterable[WorkUnit], commits: Iterable[Commit]) -> str:
    """Return a stable input fingerprint for an incremental daily note."""
    lines = [
        f"{unit.project}|{unit.source}|{unit.session_id}|{unit.start.isoformat()}|"
        f"{unit.end.isoformat()}|{'|'.join(event['content'] for event in unit.events)}"
        for unit in units
    ]
    lines.extend(
        f"{commit.id}|{commit.title}|{commit.project}|{commit.timestamp.isoformat()}"
        for commit in commits
    )
    return sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()
