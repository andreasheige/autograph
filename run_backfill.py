import sys
import os
from pathlib import Path

# Add the refactored repo to sys.path so imports work
repo_root = Path(__file__).resolve().parent
sys.path.append(str(repo_root))
sys.path.append(str(repo_root / "src"))

from src.agents.backfiller import AutographBackfillerAgent
from config.settings import Config

def main():
    search_path = sys.argv[1] if len(sys.argv) > 1 else str(Config.SEARCH_DIR)
    agent = AutographBackfillerAgent()
    agent.run(search_path)

if __name__ == "__main__":
    main()
