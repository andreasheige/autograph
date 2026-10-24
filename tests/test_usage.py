import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.agents.daily_backfiller import DailyBackfillAgent
from src.core.daily_note_renderer import render_daily_note, retrofit_daily_note
from src.core.drivers.jsonl_session_driver import ClaudeDriver
from src.core.usage import Usage, format_minutes, price_usage
from src.core.work_units import session_day_totals

START = datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc)


def claude_line(message_id, minutes, model="claude-opus-5-5", **usage):
    return json.dumps(
        {
            "type": "assistant",
            "sessionId": "session-1",
            "timestamp": (START + timedelta(minutes=minutes)).isoformat(),
            "message": {
                "id": message_id,
                "model": model,
                "usage": {"input_tokens": 0, "output_tokens": 0, **usage},
            },
        }
    )


def record(minutes, cost, session_id="session-1"):
    return {
        "timestamp": START + timedelta(minutes=minutes),
        "source": "claude",
        "session_id": session_id,
        "usage": Usage(tokens=1000, cost=cost),
    }


def event(minutes, content, session_id="session-1"):
    timestamp = START + timedelta(minutes=minutes)
    return {
        "timestamp": timestamp,
        "date": timestamp.date().isoformat(),
        "project": "project",
        "source": "claude",
        "session_id": session_id,
        "role": "user",
        "content": content,
    }


def test_price_usage_prices_each_token_class_at_its_rate():
    usage = price_usage(
        "claude-opus-5-5[1m]",
        {
            "input_tokens": 1_000_000,
            "output_tokens": 1_000_000,
            "cache_read_input_tokens": 1_000_000,
            "cache_creation": {
                "ephemeral_5m_input_tokens": 1_000_000,
                "ephemeral_1h_input_tokens": 1_000_000,
            },
        },
    )

    # $4 input + $20 output + $0.20 cache read + $5 (1.25x) + $8 (2x) cache writes
    assert usage.cost == pytest.approx(37.20)
    assert usage.tokens == 5_000_000
    assert usage.unpriced_tokens == 0


def test_price_usage_reads_dated_ids_fast_mode_and_unknown_models():
    haiku = price_usage("claude-haiku-4-5-20251001", {"output_tokens": 1_000_000})
    fast = price_usage("claude-opus-5-5", {"output_tokens": 1_000_000, "speed": "fast"})
    unknown = price_usage("gpt-x", {"output_tokens": 500})

    assert haiku.cost == pytest.approx(5.00)
    assert fast.cost == pytest.approx(40.00)
    assert (unknown.cost, unknown.unpriced_tokens) == (0.0, 500)


def test_usage_since_counts_a_response_once_however_many_lines_repeat_it(tmp_path):
    session_file = tmp_path / "projects" / "repo" / "session-1.jsonl"
    session_file.parent.mkdir(parents=True)
    session_file.write_text(
        "\n".join(
            [
                claude_line("msg_1", 1, output_tokens=1_000_000),
                claude_line("msg_1", 1, output_tokens=1_000_000),
                claude_line("msg_2", 2, model="<synthetic>", output_tokens=5),
                json.dumps({"type": "user", "message": {"content": "hi"}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    driver = ClaudeDriver(
        "claude",
        SimpleNamespace(
            CLAUDE_SESSION_ROOT=tmp_path, SESSION_CURSOR_PATH=tmp_path / "cursors.json"
        ),
    )

    records = driver.usage_since(START - timedelta(days=1))

    assert [r["message_id"] for r in records] == ["msg_1"]
    assert records[0]["usage"].cost == pytest.approx(20.00)
    assert records[0]["session_id"] == "session-1"


def test_session_day_totals_count_short_pauses_and_tool_calls_as_time():
    events = [event(0, "Start."), event(10, "More."), event(200, "After lunch.")]
    usage = [record(5, 1.0), record(20, 2.0), record(203, 4.0), record(0, 8.0, "other")]

    totals = session_day_totals(events, usage)
    session = totals[("2026-10-23", "claude", "session-1")]

    # 0, 5, 10, 20 count (gaps of at most 15 min); the 180 min gap to 200 doesn't; 200 to 203 does.
    assert session.minutes == 23
    assert session.usage.cost == pytest.approx(7.0)
    assert totals[("2026-10-23", "claude", "other")].usage.cost == pytest.approx(8.0)


def test_format_minutes():
    assert format_minutes(0) == "under 1 min"
    assert format_minutes(42) == "42 min"
    assert format_minutes(125) == "2 h 05 min"


def test_usage_summary_totals_the_day_and_the_month_so_far():
    usage = [
        record(0, 1.0),
        record(60 * 24, 2.0),  # 2026-10-24, after the note's day
        {**record(0, 4.0), "timestamp": datetime(2026, 10, 1, tzinfo=timezone.utc)},
        {**record(0, 8.0), "timestamp": datetime(2026, 9, 30, tzinfo=timezone.utc)},
    ]

    session_days = session_day_totals([], usage)

    summary = DailyBackfillAgent._usage_summary("2026-10-23", usage, session_days)

    assert summary["day"].cost == pytest.approx(1.0)
    assert summary["month"].cost == pytest.approx(5.0)
    assert summary["month_name"] == "October"
    assert DailyBackfillAgent._usage_summary("2026-10-22", usage, session_days) is None


def rendered_note():
    section = {
        "title": "Work",
        "work_done": "Did it.",
        "project": "web",
        "source": "claude",
        "session_id": "abc-1",
        "models": ["claude-opus-5-5"],
        "time": "42 min",
        "usage": Usage(tokens=1_200_000, cost=3.1),
        "terms": [],
        "wiki_pages": [],
    }
    usage = {
        "day": Usage(tokens=2_000_000, cost=41.2),
        "month": Usage(tokens=9_000_000, cost=150.0),
        "month_name": "October",
        "minutes": 95,
    }
    return render_daily_note("2026-10-23", "Summary.", [section], [], [], usage)


def test_render_daily_note_gives_each_section_its_sessions_time_and_cost():
    note = rendered_note()

    assert "active_minutes: 95\napi_cost_usd: 41.2\n" in note
    assert "**Session time today:** 42 min" in note
    assert "**Session cost today:** ≈ $3.10 at API prices (1.2M tokens)" in note
    assert (
        "**Time and cost today:** 1 h 35 min across all sessions, "
        "Claude ≈ $41.20 at API prices (2.0M tokens). "
        "October so far: ≈ $150.00, 75% of the $200/month subscription."
    ) in note


def test_retrofit_keeps_time_and_cost():
    note = rendered_note()

    def annotate(section):
        section["terms"] = []
        section["wiki_pages"] = []

    assert retrofit_daily_note(note, "2026-10-23", annotate) == note
