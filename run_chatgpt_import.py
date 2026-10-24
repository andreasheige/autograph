import argparse
from pathlib import Path

from config.settings import Config
from src.core.chatgpt_export import import_export


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Import a ChatGPT data export (the .zip, its unpacked folder, or "
            "conversations.json) for the daily-note pipeline."
        )
    )
    parser.add_argument("export", type=Path, help="Path to the ChatGPT export.")
    args = parser.parse_args()
    conversations, messages = import_export(args.export, Config.CHATGPT_IMPORT_ROOT)
    print(
        f"💬 Imported {conversations} ChatGPT conversations ({messages} messages) "
        f"into {Config.CHATGPT_IMPORT_ROOT}."
    )
    print(
        "   Daily notes pick them up on the next backfill. For older days, run "
        "run_daily_backfill.py with a wider --days (one Ollama call per work unit)."
    )


if __name__ == "__main__":
    main()
