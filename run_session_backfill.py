import argparse

from src.agents.session_backfiller import SessionBackfillAgent


def main():
    parser = argparse.ArgumentParser(
        description="Create vault notes from retained local coding-agent sessions."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days of retained sessions to process (default: 14).",
    )
    args = parser.parse_args()
    SessionBackfillAgent().run(days=args.days)


if __name__ == "__main__":
    main()
