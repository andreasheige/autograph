import sys
from pathlib import Path

# Claude Desktop launches this from an arbitrary cwd, so bootstrap imports here.
repo_root = Path(__file__).resolve().parent
sys.path.append(str(repo_root))

from src.agents.desktop_capture_server import serve

if __name__ == "__main__":
    serve()
