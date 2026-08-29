from unittest.mock import patch

from src.agents.session_backfiller import SessionBackfillAgent


def test_session_backfill_uses_compact_daily_pipeline():
    with patch(
        "src.agents.session_backfiller.DailyBackfillAgent"
    ) as daily_backfill:
        SessionBackfillAgent().run(days=14)

    daily_backfill.return_value.run.assert_called_once_with(days=14)
