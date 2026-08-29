import os
import time
import json
from pathlib import Path
from typing import List, Dict, Any
from src.agents.sync_agent import AutographSyncAgent
from src.core.drivers.manager import DriverManager
from src.core.drivers.jsonl_session_driver import (
    ClaudeDriver,
    CodexDriver,
    CopilotDriver,
    PiDriver,
)
from src.core.drivers.shell_driver import ShellDriver
from src.core.synthesizer import Synthesizer
from src.core.vault import VaultManager
from src.core.session_buffer import SessionBuffer
from config.settings import Config

class SessionObserverAgent:
    """
    The Session Observer Agent.
    Orchestrates drivers to capture 'inter-commit' reasoning and dialogue.
    
    In the new architecture, this agent accumulates raw data into a buffer
    and only synthesizes a report when triggered by a Git commit.
    """

    def __init__(self):
        self.config = Config()
        self.vault_manager = VaultManager(self.config.VAULT_ROOT)
        self.synthesizer = Synthesizer()
        self.buffer = SessionBuffer(self.config.SESSION_BUFFER_PATH)
        self.sync_agent = AutographSyncAgent(self.vault_manager.vault_root)
        
        # Drivers
        self.driver_manager = DriverManager(
            driver_classes=[
                ShellDriver,
                CopilotDriver,
                ClaudeDriver,
                CodexDriver,
                PiDriver,
            ],
            config=self.config,
        )
        
        self.is_running = False

    def run_once(self) -> None:
        """
        A single 'pulse' of the observer.
        Instead of synthesizing, it only aggregates new observations into the buffer.
        """
        print("🔍 [SessionObserver] Pulsing: Collecting new observations into buffer...")
        
        events = self.driver_manager.collect_all_observations()
        
        if not events:
            print("😴 [SessionObserver] No new session activity detected in drivers.")
            return

        # Accumulate the findings into our persistent buffer
        for event in events:
            self.buffer.append(json.dumps(event))
            
        print(f"📥 [SessionObserver] Buffered {len(events)} new observations.")

    def handle_commit_event(
        self, commit_hash: str, repository: Path = None
    ) -> None:
        """
        THE TRIGGER: This is called when a Git commit is detected.
        It flushes the buffer, synthesizes the engineering narrative, and writes to the vault.
        """
        print(f"🚀 [SessionObserver] Commit detected ({commit_hash}). Closing session slice...")
        
        # 1. Flush the buffer (get everything since last commit, then clear)
        from src.core.session_buffer import SessionBuffer
        self.buffer = SessionBuffer(self.config.SESSION_BUFFER_PATH)
        session_data_raw = self.buffer.flush()
        
        if not session_data_raw.strip():
            print("⚠️ [Session 💥] No buffered data to synthesize for this commit. Skipping.")
            return

        print(f"🧠 [SessionObserver] Synthesizing engineering narrative from buffer...")

        # 2. Prepare payload for the Synthesizer
        # We wrap the raw string in a structure the Synthesizer expects
        prompt_data = {
            "session_raw_log": session_data_raw,
            "trigger_commit": commit_hash,
            "repository": str(repository) if repository else "unknown",
        }

        try:
            # 3. Synthesize the "Engineering Narrative"
            summary_story = self.synthesizer.synthesize_session(prompt_data)
            
            if summary_story:
                # 4. Save to the vault
                project_name = (
                    repository.name if repository else "system"
                )
                self.vault_manager.write_project_note(project_name)
                self.vault_manager.write_commit_note(
                    project_name,
                    commit_hash,
                    f"Session context for {commit_hash[:12]}",
                    time.strftime("%Y-%m-%d"),
                    session_context=summary_story,
                )
                print(f"✅ [SessionObserver] Session context linked to {commit_hash[:12]}")
                self.sync_agent.sync()
            else:
                print("⚠️ [SessionObserver] Synthesizer produced no content.")

        except Exception as e:
            print(f"❌ [SessionObserver] Failed to process commit-driven synthesis: {e}")

    def start_continuous(self, interval: int = 60):
        """Runs the observer in a loop."""
        self.is_running = True
        print(f"🚀 [SessionObserver] Continuous mode started (interval: {interval}s).")
        try:
            while self.is_running:
                self.run_once()
                time.sleep(interval)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.is_running = False
        self.driver_manager.shutdown()
        print("🛑 [SessionObserver] Stopped.")

if __name__ == "__main__":
    agent = SessionObserverAgent()
    agent.run_once()
