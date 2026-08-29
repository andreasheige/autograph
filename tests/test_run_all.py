from unittest.mock import patch

import run_all
from config.settings import Config


def test_run_all_starts_every_workflow(monkeypatch):
    monkeypatch.setattr("sys.argv", ["run_all.py"])

    with patch("run_all.AutographBackfillerAgent") as backfiller, patch(
        "run_all.AutographSummaryAgent"
    ) as summary, patch("run_all.run_daemon") as observer:
        run_all.main()

    backfiller.return_value.run.assert_called_once_with(str(Config.SEARCH_DIR), days=7)
    summary.return_value.run.assert_called_once_with()
    observer.assert_called_once_with()


def test_run_all_can_skip_workflows(monkeypatch):
    monkeypatch.setattr(
        "sys.argv",
        ["run_all.py", "--days", "30", "--skip-summary", "--skip-observer"],
    )

    with patch("run_all.AutographBackfillerAgent") as backfiller, patch(
        "run_all.AutographSummaryAgent"
    ) as summary, patch("run_all.run_daemon") as observer:
        run_all.main()

    backfiller.return_value.run.assert_called_once_with(str(Config.SEARCH_DIR), days=30)
    summary.return_value.run.assert_not_called()
    observer.assert_not_called()
