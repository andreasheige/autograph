import os
from typing import List, Dict, Any
from src.core.drivers.base import BaseDriver

class DriverManager:
    """
    Orchestrates multiple Session Drivers.
    Responsibility: Load, run, and aggregate data from all active drivers.
    """

    def __init__(self, driver_classes: List[type], config: Any):
        """
        :param driver_classes: A list of classes that implement BaseDriver.
        :param config: The central Config object.
        """
        self.driver_classes = driver_classes
        self.config = config
        self.active_drivers: List[BaseDriver] = []
        self._initialize_drivers()

    def _initialize_drivers(self) -> None:
        """
        Loads drivers based on the environment variable `AUTOGRAPH_SESSION_DRIVERS`.
        Example: `AUTOGRAPH_SESSION_DRIVERS=shell,pi`
        """
        enabled_driver_names = os.getenv("AUTOGRAPH_SESSION_DRIVERS", "").split(",")
        enabled_driver_names = [name.strip() for name in enabled_driver_names if name.strip()]
        print(f"DEBUG: [DriverManager] Enabled drivers from ENV: {enabled_driver_names}")

        for driver_cls in self.driver_classes:
            driver_name_candidate = driver_cls.__name__.replace("Driver", "").lower()
            print(f"DEBUG: [DriverManager] Checking candidate: {driver_name_candidate}")

            if driver_name_candidate in enabled_driver_names:
                try:
                    instance = driver_cls(name=driver_name_candidate, config=self.config)
                    self.active_drivers.append(instance)
                    print(f"🚀 [DriverManager] Activated driver: {driver_name_candidate}")
                except Exception as e:
                    print(f"❌ [DriverManager] Failed to activate {driver_name_candidate}: {e}")
            else:
                print(f"DEBUG: [DriverManager] Skipping {driver_name_candidate} (not in enabled list)")

    def collect_all_observations(self) -> List[Dict[str, Any]]:
        """
        Iterates through all active drivers, performs observation, and aggregates results.
        Returns a list of structured entities found across all drivers.
        """
        all_events = []
        print(f"DEBUG: [DriverManager] Collecting observations from {self.active_driver_count()} drivers")
        for driver in self.active_drivers:
            try:
                raw_data = driver.observe()
                if raw_data:
                    entities = driver.extract_entities(raw_data)
                    all_events.extend(entities)
            except Exception as e:
                print(f"⚠️ [DriverManager] Error in driver {driver.driver_id}: {e}")
        
        return all_events

    def active_driver_count(self) -> int:
        return len(self.active_drivers)

    def shutdown(self) -> None:
        """Cleanup all drivers."""
        for driver in self.active_drivers:
            driver.cleanup()
        print("🛑 [DriverManager] All drivers shut down.")
