from unittest.mock import patch

from src.agents.summary import AutographSummaryAgent


def test_summary_uses_bounded_daily_backfill():
    with patch("src.agents.summary.DailyBackfillAgent") as daily_backfill:
        AutographSummaryAgent().run()

    daily_backfill.return_value.run.assert_called_once_with(days=1)
