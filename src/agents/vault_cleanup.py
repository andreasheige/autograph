from config.settings import Config
from src.agents.sync_agent import AutographSyncAgent
from src.core.vault import VaultManager


class VaultCleanupAgent:
    """Remove generated session fragments that are no longer active knowledge notes."""

    def __init__(self):
        self.vault_manager = VaultManager(Config.VAULT_ROOT)
        self.sync_agent = AutographSyncAgent(self.vault_manager.vault_root)

    def run(self) -> int:
        removed = self.vault_manager.prune_legacy_session_notes()
        print(f"🧹 Removed {removed} legacy session fragment notes.")
        if removed:
            self.sync_agent.sync()
        return removed
