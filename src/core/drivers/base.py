from abc import ABC, abstractmethod
from typing import Any, Dict, List

class BaseDriver(ABC):
    """
    The blueprint for all Session Observers.
    Each driver is responsible for one tool (e.g., PI, Claude, Shell).
    """

    def __init__(self, name: str):
        self.name = name

    @property
    @abstractmethod
    def driver_id(self) -> str:
        """Unique identifier for the driver."""
        pass

    @abstractmethod
    def observe(self) -> str:
        """
        The core logic that 'watches' the tool. 
        Returns the raw, unparsed stream or the latest buffer of text.
        """
        pass

    @abstractmethod
    def extract_entities(self, raw_data: str) -> List[Dict[str, Any]]:
        """
        Parsers the raw text into structured 'event' dictionary/entities.
        Example output: [{'type': 'action', 'content': 'user ran ls'}]
        """
        pass

    def cleanup(self) -> None:
        """Cleanup method for when the driver is stopped."""
        pass
