"""Run Autograph's one-shot workflows, then start continuous observation."""

import argparse

from config.settings import Config
from src.agents.backfiller import AutographBackfillerAgent
from src.agents.session_observer_daemon import run_daemon
from src.agents.summary import AutographSummaryAgent


def parse_args():
    parser = argparse.ArgumentParser(
        description="Backfill history, generate a daily summary, and observe new sessions."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days of Git history to backfill (default: 7).",
    )
    parser.add_argument(
        "--skip-backfill",
        action="store_true",
        help="Do not backfill Git history before starting observation.",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Do not generate the daily summary before starting observation.",
    )
    parser.add_argument(
        "--skip-observer",
        action="store_true",
        help="Exit after the one-shot workflows instead of starting the observer.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.days <= 0:
        raise ValueError("--days must be a positive integer")

    if not args.skip_backfill:
        AutographBackfillerAgent().run(str(Config.SEARCH_DIR), days=args.days)

    if not args.skip_summary:
        AutographSummaryAgent().run()

    if not args.skip_observer:
        run_daemon()


if __name__ == "__main__":
    main()
