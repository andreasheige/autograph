from src.agents.daily_backfiller import DailyBackfillAgent


class SessionBackfillAgent:
    """Backfill retained sessions into compact daily notes, not session fragments."""

    def run(self, days: int = 14) -> int:
        return DailyBackfillAgent().run(days=days)
