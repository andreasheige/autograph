from src.agents.daily_backfiller import DailyBackfillAgent


class AutographSummaryAgent:
    """Generate the current daily note through the bounded work-unit pipeline."""

    def run(self):
        print("📅 Generating the current technical daily note...")
        DailyBackfillAgent().run(days=1)


if __name__ == "__main__":
    AutographSummaryAgent().run()
