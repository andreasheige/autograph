import argparse

from src.agents.daily_note_retrofit import DailyNoteRetrofitAgent


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Add frontmatter, vocabulary tags and Related wiki links to existing "
            "generated daily notes, without calling Ollama."
        )
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Write the notes but do not commit and push the vault.",
    )
    args = parser.parse_args()
    DailyNoteRetrofitAgent().run(sync=not args.no_sync)


if __name__ == "__main__":
    main()
