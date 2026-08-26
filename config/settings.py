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

class Config:
    """
    Centralized configuration for Autograph.
    All paths and settings are loaded from environment variables.
    """
    
    # The root directory of the Autograph repository
    REPO_ROOT = Path(__file__).resolve().parent.parent.parent
    
    # --- Obsidian Vault Settings ---
    VAULT_ROOT = get_env_path("AUTOGRAPH_VAULT_ROOT", "~/.autograph/vault")
    
    # --- LLM Settings ---
    MODEL_NAME = os.environ.get("AUTOGRAPH_MODEL_NAME", "llama3")
    OLLAMA_API_URL = os.environ.get("AUTOGRAPH_OLLAMA_URL", "http://localhost:11434/api/generate")

    # --- Search Settings ---
    SEARCH_DIR = get_env_path("AUTOGRAPH_SEARCH_DIR", "~/projects")

    # --- Logging ---
    LOG_DIR = get_env_path("AUTOGRAPH_LOG_DIR", "~/.autograph/logs")

# Ensure the basic logging directory exists immediately on import
os.makedirs(Config.LOG_DIR, exist_ok=True)
