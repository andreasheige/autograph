import argparse

from src.agents.daily_note_linker import DailyNoteLinker


def main():
    parser = argparse.ArgumentParser(
        description="Connect generated daily notes to verified agent and commit nodes."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of retained days to inspect (default: 14).",
    )
    args = parser.parse_args()
    DailyNoteLinker().run(days=args.days)


if __name__ == "__main__":
    main()
