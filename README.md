# 🎭 Autograph

**Transform the noise of Git commits into a structured, human-readable daily chronicle within your Obsidian Vault.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-orange.svg)](https://ollama.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Autograph is a modular, agentic system designed to bridge the gap between your development workflow and your personal knowledge management (PKM) system. It observes your Git activity, extracts meaningful entities and relationships, and uses local LLMs to synthesize these events into beautiful, daily journal entries.

---

## ✨ Key Features

* **📜 The Historian (Backfiller Agent):** A self-discovering agent that recursively scans your `AUTOGRAPH_SEARCH_DIR` for Git repositories. It performs a **Deep Inspection** of every commit—analyzing not just the commit message, but the exact files changed—to extract structured entities and relationships directly into Obsidian. It is intelligent enough to ignore "noise" like `node_modules` and `__pycache__`.
* **📅 The Chronicler (Summary Agent):** An automated morning agent that aggregates all events from the last 24 hours, fetches local weather via `wttr.in`, and generates a human-readable daily journal entry.
* **🧠 LLM-Powered Synthesis:** Uses **Ollama** (default: `deepseek-v3`) to perform semantic extraction and natural language summarization locally—keeping your data private and free.
* **🛡️ Privacy First:** Everything runs locally. Your git logs, your `.env` configurations, and your LLM inference never leave your machine.
* **🔌 Obsidian-Native:** Outputs directly to your Obsidian vault in structured Markdown, ready for linking and long-term knowledge storage.

---

## 🏗️ Architecture

Autograph is built with a modular, "Agentic" architecture:

* `src/core/`: The engine. Contains the `VaultManager` (Obsidian interaction) and `Synthesizer` (Ollama interface).
* `src/agents/`: The brains. Specialized agents like the `Backfiller` and `Summary` agent.
* `config/`: The configuration layer. Environment-driven and identity-blind.
* `infrastructure/`: The deployment layer. Contains setup scripts and automation (e.g., `launchd` templates).

### 📂 The Two-Repo Strategy
Autograph operates using a clean separation between the **Engine** and the **Memory**:
* **The Engine (Code):** The logic, agents, and automation residing in your development repository.
* **The Memory (Vault):** Your Obsidian vault, acting as a version-on-controlled, structured knowledge base.

---

## 🚀 Quick Start

### Prerequisites

1.  **Ollama:** Installed and running (e.g., `ollama serve`) with the configured model available (for the default, run `ollama pull deepseek-v3`).
2.  **Python 3.9+**
3.  **An Obsidian Vault:** A place to store your chronicles.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/autograph.git
    cd autograph
    ```

2.  **Run the Setup Agent:**
    The built-in setup script will initialize your environment, create necessary directories, and prepare your `.env` file.
    ```bash
    ./infrastructure/setup_agent.sh
    ```

    Install the Python dependencies:
    ```bash
    python3 -m pip install -r requirements.txt
    ```

3.  **Configure your identity:**
    Open the newly created `.env` file and point it to your local paths:
    ```bash
    nano .env
    ```
    *(Set `AUTOGRAPH_VAULT_ROOT` to your Obsidian vault path and `AUTOGRAPH_SEARCH_DIR` to your projects folder.)*

4. **Enable macOS automation (optional):**
    ```bash
    ./infrastructure/install_launchd.sh
    ```
    This starts the session observer whenever you log in and runs the daily summary
    at 08:00. The launch agents write logs to `~/.autograph/logs`. Historical
    backfill remains manual because repeating it can create duplicate history events.

    To remove the automation:
    ```bash
    ./infrastructure/uninstall_launchd.sh
    ```

### Usage

#### Run Everything
To backfill the last seven days, generate the current daily summary, and then keep
observing new sessions:
```bash
python3 run_all.py
```

Use `python3 run_all.py --help` to skip individual workflows or change the backfill
window. The session observer continues until you stop it with `Ctrl+C`.

#### 1. Backfilling History
To process your existing Git repositories and populate your vault with past activities:
```bash
python3 run_backfill.py
```

#### 2. Generating the Daily Summary
To manually trigger the daily journal generation:
```bash
python3 run_summary.py
```

#### 3. Backfilling Agent Sessions
To create notes from retained Copilot, Claude, Codex, and Pi sessions from the last
two weeks:
```bash
python3 run_session_backfill.py --days 14
```
This is explicit rather than automated: it reads historical local assistant records and
may generate many notes.

#### 4. Backfilling Daily Notes
To regenerate daily notes from retained local sessions and Git commits:
```bash
python3 run_daily_backfill.py --days 14 --replace-generated
```
`--replace-generated` replaces only daily notes marked as generated by Autograph; unmarked
notes are never overwritten. Without that flag, completed generated days are retained so an
interrupted import can resume. Use `--date YYYY-MM-DD --replace-generated` to regenerate a
single marked day.

Daily-note generation first filters and deduplicates local session records, groups them by
repository and session, and associates nearby commits. It then synthesizes no more than six
technical sections plus one day overview per date. This keeps the scheduled daily job bounded
and makes every section traceable to a project and, when available, a commit.

---

## 🛠️ Configuration (`.env`)

Autograph is entirely driven by environment variables. Never commit your `.env` file to version control.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `AUTOGRAPH_VAULT_ROOT` | Absolute path to your Obsidian Vault | `~/.autograph/vault` |
| `AUTOGRAPH_SEARCH_DIR` | Where to look for Git repositories | `~/projects` |
| `AUTOGRAPH_MODEL_NAME` | The Ollama model to use | `deepseek-v3` |
| `AUTOGRAPH_OLLAMA_URL` | The local API endpoint for Ollama | `http://localhost:11434/api/generate` |
| `AUTOGRAPH_OLLAMA_TIMEOUT_SECONDS` | Seconds to wait for an Ollama response | `300` |
| `AUTOGRAPH_SESSION_DRIVERS` | Comma-separated session drivers to run | `shell,copilot,claude,codex,pi` |
| `AUTOGRAPH_SESSION_LOG_FILE` | File the shell driver observes | `~/autograph_session.log` |
| `AUTOGRAPH_SESSION_CURSOR_PATH` | Persistent cursor state for agent session files | `~/.autograph/session_cursors.json` |
| `AUTOGRAPH_COPILOT_SESSION_ROOT` | Copilot CLI session directory | `~/.copilot/session-state` |
| `AUTOGRAPH_CLAUDE_SESSION_ROOT` | Claude Code session directory | `~/.claude` |
| `AUTOGRAPH_CODEX_SESSION_ROOT` | Codex CLI session directory | `~/.codex` |
| `AUTOGRAPH_PI_SESSION_ROOT` | Pi session directory | `~/.pi/agent/sessions` |
| `AUTOGRAPH_LOG_DIR` | Where to store system logs | `~/.autograph/logs` |

The observer enables Shell, Copilot CLI, Claude Code, Codex CLI, and Pi drivers by default.
Each JSONL driver records its current position on first launch, then captures only new local
session records. It buffers them until a new commit is detected in any repository under
`AUTOGRAPH_SEARCH_DIR`, then writes a synthesized narrative to the vault.

---

## 🧪 Testing

We use `pytest` to ensure the reliability of our agents. To run the test suite:

```bash
python3 -m pytest tests/
```

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
