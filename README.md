# 🎭 Autograph

**Transform the noise of Git commits into a structured, human-readable daily chronicle within your Obsidian Vault.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](httpshttps://www.python.org/downloads/)
[![Ollama](https://img.shields.io/badge/LLM-Ollama-orange.svg)](https://ollama.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Autograph is a modular, agentic system designed to bridge the gap between your development workflow and your



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
* **🧠 LLM-Powered Synthesis:** Uses **Ollama** (e.g., `llama3`) to perform semantic extraction and natural language summarization locally—keeping your data private and free.
* **🛡️ Privacy First:** Everything runs locally. Your git logs, your `.env` configurations, and your LLM inference never leave your machine.
* **🔌 Obsidian-Native:** Outputs directly to your Obsidian vault in structured Markdown, ready for linking and long-term knowledge storage.

---

## 🏗️ Architecture

Autograph is built with a modular, "Agentic" architecture:

* `src/core/`: The engine. Contains the `VaultManager` (Obsintidian interaction) and `Synthesizer` (Ollama interface).
* `src/agents/`: The brains. Specialized agents like the `Backfiller` and `Summary` agent.
* `config/`: The configuration layer. Environment-driven and identity-blind.
* `infrastructure/`: The deployment layer. Contains setup scripts and automation (e.g., `launchd` templates).

---

## 🚀 Quick Start

### Prerequisites

1.  **Ollama:** Installed and running (e.g., `ollama serve`).
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

3.  **Configure your identity:**
    Open the newly created `.env` file and point it to your local paths:
    ```bash
    nano .env
    ```
    *(Set `AUTOGRAPH_VAULT_ROOT` to your Obsidian vault path and `AUTOGRAPH_SEARCH_DIR` to your projects folder.)*

### Usage

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

---

## 🛠️ Configuration (`.env`)

Autograph is entirely driven by environment variables. Never commit your `.env` file to version control.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `AUTOGRAPH_VAULT_ROOT` | Absolute path to your Obsidian Vault | `~/.autograph/vault` |
| `AUTOGRAPH_SEARCH_DIR` | Where to look for Git repositories | `~/projects` |
| `AUTOGRAPH_MODEL_NAME` | The Ollama model to use | `llama3` |
| `AUTOGRAPH_OLLAMA_URL` | The local API endpoint for Ollama | `http://localhost:11434/api/generate` |
| `AUTOGRAPH_LOG_DIR` | Where to store system logs | `~/.autograph/logs` |

---

## 🧪 Testing

We use `pytest` to ensure the reliability of our agents. To run the test suite:

```bash
pip install pytest
pytest tests/
```

## 📜 License

Distributed under the MIT License. See `LICENSE` for more information.
