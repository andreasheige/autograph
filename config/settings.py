import os
from pathlib import Path
from dotenv import load_dotenv

# Load variables from .env file if it exists
load_dotenv()


def get_env_path(key, default_template):
    """
    Retrieves an environment variable and ensures it is an expanded Path object.
    If the variable is not found, it returns the default_template expanded.
    """
    raw_path = os.environ.get(key, default_template)
    return Path(raw_path).expanduser().resolve()


def get_env_path_list(key, default_template):
    """
    Retrieves an environment variable as a comma-separated list of expanded
    Path objects (e.g. multiple project search roots). If the variable is not
    found, returns a single-item list built from default_template.
    """
    raw_value = os.environ.get(key)
    parts = raw_value.split(",") if raw_value is not None else [default_template]
    return [Path(part.strip()).expanduser().resolve() for part in parts if part.strip()]


def get_env_positive_int(key, default):
    """Read a positive integer environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default

    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{key} must be a positive integer, got {value!r}") from error

    if parsed <= 0:
        raise ValueError(f"{key} must be a positive integer, got {value!r}")
    return parsed


class Config:
    """
    Centralized configuration for Autograph.
    All paths and settings are loaded from environment variables.
    """
    
    # The root directory of the Autograph repository
    REPO_ROOT = Path(__file__).resolve().parent.parent
    
    # --- Obsidian Vault Settings ---
    VAULT_ROOT = get_env_path("AUTOGRAPH_VAULT_ROOT", "~/.autograph/vault")
    
    # --- LLM Settings ---
    MODEL_NAME = os.environ.get("AUTOGRAPH_MODEL_NAME", "gemma4:26b")
    OLLAMA_API_URL = os.environ.get("AUTOGRAPH_OLLAMA_URL", "http://localhost:11434/api/generate")
    OLLAMA_REQUEST_TIMEOUT_SECONDS = get_env_positive_int(
        "AUTOGRAPH_OLLAMA_TIMEOUT_SECONDS", 300
    )

    # --- Search Settings ---
    # AUTOGRAPH_SEARCH_DIR may list multiple roots, comma-separated (e.g. work
    # spans two unrelated trees like ~/Dev and ~/Knowit). SEARCH_DIR stays the
    # first root for callers that only ever expected a single path; SEARCH_DIRS
    # is the full list for repository discovery in the daily-note pipeline.
    SEARCH_DIRS = get_env_path_list("AUTOGRAPH_SEARCH_DIR", "~/projects")
    SEARCH_DIR = SEARCH_DIRS[0]
    # Folders whose repositories are one project, named after the folder: e.g.
    # a client folder holding DEV/TEST/PROD clones of the same code.
    PROJECT_GROUPS = get_env_path_list("AUTOGRAPH_PROJECT_GROUPS", "")
    # Folders kept out of the vault entirely: no repository, commit or session
    # event under them reaches a note, e.g. client work whose agreement does
    # not yet allow the vault's git remote.
    EXCLUDED_PATHS = get_env_path_list("AUTOGRAPH_EXCLUDE_PATHS", "")

    # --- Logging ---
    LOG_DIR = get_env_path("AUTOGRAPH_LOG_DIR", "~/.autograph/logs")

    # --- Session Buffer Settings ---
    SESSION_BUFFER_PATH = get_env_path("AUTOGRAPH_SESSION_BUFFER_PATH", "~/.autograph/session_buffer.log")
    SESSION_CURSOR_PATH = get_env_path("AUTOGRAPH_SESSION_CURSOR_PATH", "~/.autograph/session_cursors.json")

    # --- Driver Settings ---
    SESSION_LOG_FILE = get_env_path("AUTOGRAPH_SESSION_LOG_FILE", "~/autograph_session.log")
    COPILOT_SESSION_ROOT = get_env_path("AUTOGRAPH_COPILOT_SESSION_ROOT", "~/.copilot/session-state")
    CLAUDE_SESSION_ROOT = get_env_path("AUTOGRAPH_CLAUDE_SESSION_ROOT", "~/.claude")
    CODEX_SESSION_ROOT = get_env_path("AUTOGRAPH_CODEX_SESSION_ROOT", "~/.codex")
    PI_SESSION_ROOT = get_env_path("AUTOGRAPH_PI_SESSION_ROOT", "~/.pi/agent/sessions")
    # Written by the desktop capture MCP server only when the user asks.
    DESKTOP_CAPTURE_ROOT = get_env_path("AUTOGRAPH_DESKTOP_CAPTURE_ROOT", "~/.autograph/desktop-captures")
    # Written by run_chatgpt_import.py from a ChatGPT data export.
    CHATGPT_IMPORT_ROOT = get_env_path("AUTOGRAPH_CHATGPT_IMPORT_ROOT", "~/.autograph/chatgpt-imports")

# Ensure the basic logging directory exists immediately on import
os.makedirs(Config.LOG_DIR, exist_ok=True)
