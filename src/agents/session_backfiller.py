import subprocess
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from config.settings import Config
from src.agents.sync_agent import AutographSyncAgent
from src.core.drivers.jsonl_session_driver import (
    ClaudeDriver,
    CodexDriver,
    CopilotDriver,
    PiDriver,
)
from src.core.synthesizer import Synthesizer, SynthesizerError
from src.core.vault import VaultManager


class SessionBackfillAgent:
    """Creates historical vault notes from retained local coding-agent sessions."""

    max_prompt_characters = 24000

    def __init__(self):
        self.config = Config()
        self.vault_manager = VaultManager(self.config.VAULT_ROOT)
        self.synthesizer = Synthesizer()
        self.sync_agent = AutographSyncAgent(self.vault_manager.vault_root)
        self.drivers = [
            CopilotDriver("copilot", self.config),
            ClaudeDriver("claude", self.config),
            CodexDriver("codex", self.config),
            PiDriver("pi", self.config),
        ]

    @staticmethod
    def _repository_for_path(cwd: Optional[str]) -> Optional[Path]:
        if not cwd:
            return None
        try:
            result = subprocess.run(
                ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError:
            return None
        return Path(result.stdout.strip())

    @staticmethod
    def _group_events(
        events: Iterable[Dict[str, object]]
    ) -> Dict[Tuple[str, str, Optional[str]], List[Dict[str, object]]]:
        groups = defaultdict(list)
        for event in events:
            source = str(event["source"])
            session_id = str(event.get("session_id") or "unknown-session")
            cwd = event.get("cwd")
            groups[(source, session_id, str(cwd) if cwd else None)].append(event)
        return groups

    @classmethod
    def _event_line(cls, event: Dict[str, object]) -> str:
        return (
            f"[{event.get('timestamp') or 'unknown time'}] "
            f"{event.get('source')} {event.get('role')}: {event.get('content')}"
        )

    @classmethod
    def _event_chunks(
        cls, events: List[Dict[str, object]]
    ) -> List[List[Dict[str, object]]]:
        chunks = []
        chunk = []
        chunk_length = 0
        for event in events:
            event_length = len(cls._event_line(event))
            if chunk and chunk_length + event_length > cls.max_prompt_characters:
                chunks.append(chunk)
                chunk = []
                chunk_length = 0
            chunk.append(event)
            chunk_length += event_length
        if chunk:
            chunks.append(chunk)
        return chunks

    def run(self, days: int = 14) -> int:
        if days <= 0:
            raise ValueError("days must be a positive integer")

        since = datetime.now(timezone.utc) - timedelta(days=days)
        events = [
            event
            for driver in self.drivers
            for event in driver.history_since(since)
        ]
        groups = self._group_events(events)
        print(
            f"🔍 Found {len(events)} retained session events in "
            f"{len(groups)} sessions from the last {days} days."
        )

        completed = 0
        for (source, session_id, cwd), group_events in groups.items():
            repository = self._repository_for_path(cwd)
            project_name = (
                f"{repository.name}_sessions" if repository else f"{source}_sessions"
            )
            commit_label = (
                f"Historical session associated with {repository.name}"
                if repository
                else "Historical session without a repository path"
            )
            chunks = self._event_chunks(group_events)
            for index, chunk in enumerate(chunks, start=1):
                prompt_data = {
                    "session_raw_log": "\n".join(
                        self._event_line(event) for event in chunk
                    ),
                    "trigger_commit": commit_label,
                    "repository": str(repository) if repository else "unknown",
                }
                try:
                    narrative = self.synthesizer.synthesize_session(prompt_data)
                except SynthesizerError as error:
                    print(
                        f"❌ Could not synthesize {source} session {session_id} "
                        f"(part {index}/{len(chunks)}): {error}"
                    )
                    continue

                self.vault_manager.write_event(
                    project_name,
                    f"{source} historical session {session_id} (part {index}/{len(chunks)})",
                    {"entities": [], "narrative": narrative},
                )
                completed += 1

        print(f"✅ Created {completed} historical session notes.")
        if completed:
            self.sync_agent.sync()
        return completed
