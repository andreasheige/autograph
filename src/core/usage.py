"""Token usage from Claude session records, priced at Anthropic's API list prices.

The user is on a flat subscription, so this is an estimate of what the same work
would cost on the API, not a bill. Prices are USD per million tokens, from the
Claude API reference as of 2026-09-25. Cache writes cost 1.25x input (5-minute
TTL) or 2x input (1-hour TTL); cache reads have their own price per model.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, Iterable, Optional

# model: (input, output, cache read)
PRICES: Dict[str, tuple] = {
    "claude-fable-5-1": (10.00, 50.00, 0.25),
    "claude-mythos-5-1": (10.00, 50.00, 0.25),
    "claude-fable-5": (10.00, 50.00, 1.00),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-opus-5": (5.00, 25.00, 0.50),
    "claude-opus-4-8": (5.00, 25.00, 0.50),
    "claude-opus-4-7": (5.00, 25.00, 0.50),
    "claude-opus-4-6": (5.00, 25.00, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-sonnet-5": (2.00, 10.00, 0.20),
    "claude-sonnet-4-6": (3.00, 15.00, 0.30),
    "claude-haiku-4-5": (1.00, 5.00, 0.10),
}
CACHE_WRITE_5M = 1.25
CACHE_WRITE_1H = 2.0
# Fast mode bills every token class at twice the standard rate.
FAST_MULTIPLIER = 2.0
SUBSCRIPTION_USD_PER_MONTH = 200

_DATE_SUFFIX = re.compile(r"-\d{8}$")


def price_key(model: str) -> str:
    """`claude-opus-5-5[1m]` and `claude-haiku-4-5-20251001` price as their base model."""
    return _DATE_SUFFIX.sub("", model.split("[", 1)[0].strip())


@dataclass
class Usage:
    tokens: int = 0
    cost: float = 0.0
    # Tokens from models with no known price; their cost is not in `cost`.
    unpriced_tokens: int = 0

    def add(self, other: "Usage") -> None:
        self.tokens += other.tokens
        self.cost += other.cost
        self.unpriced_tokens += other.unpriced_tokens


def _count(value: Any) -> int:
    return value if isinstance(value, int) and value > 0 else 0


def price_usage(model: str, usage: Dict[str, Any]) -> Usage:
    """Price one API response's `usage` object."""
    input_tokens = _count(usage.get("input_tokens"))
    output_tokens = _count(usage.get("output_tokens"))
    cache_read = _count(usage.get("cache_read_input_tokens"))
    cache_creation = usage.get("cache_creation")
    if isinstance(cache_creation, dict):
        write_5m = _count(cache_creation.get("ephemeral_5m_input_tokens"))
        write_1h = _count(cache_creation.get("ephemeral_1h_input_tokens"))
    else:
        write_5m, write_1h = _count(usage.get("cache_creation_input_tokens")), 0
    tokens = input_tokens + output_tokens + cache_read + write_5m + write_1h

    prices = PRICES.get(price_key(model))
    if prices is None:
        return Usage(tokens=tokens, unpriced_tokens=tokens)
    input_price, output_price, read_price = prices
    cost = (
        input_tokens * input_price
        + write_5m * input_price * CACHE_WRITE_5M
        + write_1h * input_price * CACHE_WRITE_1H
        + cache_read * read_price
        + output_tokens * output_price
    ) / 1_000_000
    if usage.get("speed") == "fast":
        cost *= FAST_MULTIPLIER
    return Usage(tokens=tokens, cost=cost)


def usage_record(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The priced usage of one Claude session line, or None for lines without any.

    A response with several content blocks is written as several lines that repeat
    the same message id and usage, so callers must count each `message_id` once.
    """
    message = record.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
        return None
    model = message.get("model")
    message_id = message.get("id") or record.get("requestId")
    if not isinstance(model, str) or "<" in model or not isinstance(message_id, str):
        return None
    return {
        "message_id": message_id,
        "session_id": record.get("sessionId"),
        "timestamp": record.get("timestamp"),
        "usage": price_usage(model, message["usage"]),
    }


def total(records: Iterable[Dict[str, Any]]) -> Usage:
    result = Usage()
    for record in records:
        result.add(record["usage"])
    return result


def format_tokens(tokens: int) -> str:
    if tokens >= 1_000_000:
        return f"{tokens / 1_000_000:.1f}M tokens"
    if tokens >= 1_000:
        return f"{tokens / 1_000:.0f}k tokens"
    return f"{tokens} tokens"


def format_cost(usage: Usage) -> str:
    text = f"≈ ${usage.cost:,.2f} at API prices ({format_tokens(usage.tokens)})"
    if usage.unpriced_tokens:
        text += f", {format_tokens(usage.unpriced_tokens)} from unpriced models"
    return text


def format_minutes(minutes: int) -> str:
    if minutes < 1:
        return "under 1 min"
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"
