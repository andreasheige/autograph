import argparse

from src.agents.vault_cleanup import VaultCleanupAgent


def main():
    parser = argparse.ArgumentParser(
        description="Remove vault files with no value: empty placeholders and legacy notes."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="List what would be removed and why."
    )
    parser.add_argument(
        "--no-sync",
        action="store_true",
        help="Remove the files but do not commit and push the vault.",
    )
    args = parser.parse_args()
    VaultCleanupAgent().run(dry_run=args.dry_run, sync=not args.no_sync)


if __name__ == "__main__":
    main()
