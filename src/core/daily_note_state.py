import json
import os
from pathlib import Path
from typing import Dict


class DailyNoteState:
    """Persist input fingerprints for generated daily notes."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._state = self._load()

    def _load(self) -> Dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as state_file:
                state = json.load(state_file)
        except (OSError, json.JSONDecodeError):
            return {}
        return state if isinstance(state, dict) else {}

    def is_current(self, date: str, fingerprint: str) -> bool:
        return self._state.get(date) == fingerprint

    def save(self, date: str, fingerprint: str) -> None:
        self._state[date] = fingerprint
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        with open(temporary_path, "w", encoding="utf-8") as state_file:
            json.dump(self._state, state_file, indent=2, sort_keys=True)
        os.replace(temporary_path, self.path)
