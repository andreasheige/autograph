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
    MODEL_NAME = os.environ.get("AUTOGRAPH_MODEL_NAME", "deepseek-v3")
    OLLAMA_API_URL = os.environ.get("AUTOGRAPH_OLLAMA_URL", "http://localhost:11434/api/generate")
    OLLAMA_REQUEST_TIMEOUT_SECONDS = get_env_positive_int(
        "AUTOGRAPH_OLLAMA_TIMEOUT_SECONDS", 300
    )

    # --- Search Settings ---
    SEARCH_DIR = get_env_path("AUTOGRAPH_SEARCH_DIR", "~/projects")

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

# Ensure the basic logging directory exists immediately on import
os.makedirs(Config.LOG_DIR, exist_ok=True)
