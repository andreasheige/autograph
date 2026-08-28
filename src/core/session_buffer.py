import os
from pathlib import Path

class SessionBuffer:
    """
    Manand a persistent buffer for accumulating raw session data 
    until a commit trigger occurs.
    """
    def __init__(self, buffer_path: str):
        self.buffer_path = Path(buffer_path)
        self.buffer_path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, text: str):
        """Append new raw data to the buffer."""
        with open(self.buffer_path, "a") as f:
            f.write(text + "\n")

    def flush(self) -> str:
        """
        Read the entire buffer, and then wipe it clean.
        This is called by the Synthesizer after processing.
        """
        if not self.buffer_path.exists():
            return ""
        
        with open(self.buffer_path, "r") as f:
            data = f.read()
        
        # Wipe the buffer
        with open(self.buffer_path, "w") as f:
            f.write("")
            
        return data

    def clear(self):
        """Complete removal of the buffer file."""
        if self.buffer_path.exists():
            os.remove(self.buffer_path)

    def exists(self) -> bool:
        return self.buffer_path.exists()

    def has_content(self) -> bool:
        return self.exists() and os.path.getsize(self.buffer_path) > 0
