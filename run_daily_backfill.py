import argparse

from src.agents.daily_backfiller import DailyBackfillAgent


def main():
    parser = argparse.ArgumentParser(
        description="Create daily notes from historical local sessions and commits."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=14,
        help="Number of days to process (default: 14).",
    )
    parser.add_argument(
        "--replace-generated",
        action="store_true",
        help="Remove existing Autograph-generated daily notes before regenerating.",
    )
    parser.add_argument(
        "--date",
        action="append",
        dest="dates",
        help="Process one date (YYYY-MM-DD); may be supplied more than once.",
    )
    args = parser.parse_args()
    DailyBackfillAgent().run(
        days=args.days,
        replace_generated=args.replace_generated,
        dates=args.dates,
    )


if __name__ == "__main__":
    main()
