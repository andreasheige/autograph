import sys
import os
from pathlib import Path

# Add the refactored repo to sys.path so imports work
repo_root = Path(__file__).resolve().parent
sys.path.append(str(repo_root))
sys.path.append(str(repo_root / "src"))

from src.agents.summary import AutographSummaryAgent

def main():
    agent = AutographSummaryAgent()
    agent.run()

if __name__ == "__main__":
    main()
