import os
from typing import Any, Dict, List
from src.core.drivers.base import BaseDriver

class ShellDriver(BaseDriver):
    """
    A driver that observes a local log file (simulating a terminal stream).
    Usage: Append text to the configured log file to simulate a session.
    """

    def __init__(self, name: str, config: Any):
        super().__init__(name)
        self.log_path = config.SESSION_LOG_FILE
        self._last_position = 0

    @property
    def driver_id(self) -> str:
        return f"shell_{self.name}"

    def observe(self) -> str:
        """Reads only the new lines since the last observation."""
        print(f"DEBUG: [ShellDriver] Checking path: {self.log_path}")
        if not os.path.exists(self.log_path):
            print(f"DEBUG: [ShellDriver] File does not exist: {self.log_path}")
            return ""

        new_content = ""
        try:
            with open(self.log_path, "r") as f:
                print(f"DEBUG: [ShellDriver] Current position before seek: {self._last_position}")
                f.seek(self._last_position)
                new_content = f.read()
                self._last_position = f.tell()
                print(f"DEBUG: [ShellDriver] New content length: {len(new_content)}")
                if new_content:
                    print(f"DEBUG: [ShellDriver] Read: {repr(new_content)}")
        except Exception as e:
            print(f"❌ [ShellDriver] Error reading log: {e}")

        return new_content

    def extract_entities(self, raw_data: str) -> List[Dict[str, Any]]:
        """
        Parses lines like:
        [USER]: I am thinking about refactoring the vault.
        [AGENT]: That sounds like a great idea! Let's start with the drivers.
        """
        entities = []
        if not raw_data.strip():
            return entities

        lines = raw_data.strip().split('\n')
        for line in lines:
            if ":" in line:
                role, content = line.split(":", 1)
                entities.append({
                    "type": "session_interaction",
                    "role": role.strip().lower(),
                    "content": content.strip()
                })
            else:
                entities.append({
                    "type": "session_event",
                    "content": line.strip()
                })
        return entities

    def cleanup(self) -> None:
        self._last_position = 0
        print("🧹 [ShellDriver] Cleanup complete.")
