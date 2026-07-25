from typing import Any


def calculate_true_ranges(
    bars: list[dict[str, Any]],
) -> list[float]:
    """
    Calculate True Range values.

    Bars must be ordered from oldest to newest.
    """
    true_ranges: list[float] = []

    for index in range(1, len(bars)):
        current_bar = bars[index]
        previous_bar = bars[index - 1]

        high = float(current_bar["h"])
        low = float(current_bar["l"])
        previous_close = float(previous_bar["c"])

        true_range = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close),
        )

        true_ranges.append(true_range)

    return true_ranges


def calculate_wilder_atr(
    bars: list[dict[str, Any]],
    period: int = 14,
) -> float | None:
    """
    Calculate Wilder's ATR.

    Alpaca currently returns the daily bars newest-first, so this
    function reverses them into chronological order.
    """
    if len(bars) < period + 1:
        return None

    chronological_bars = list(reversed(bars))

    true_ranges = calculate_true_ranges(
        chronological_bars
    )

    if len(true_ranges) < period:
        return None

    atr = sum(true_ranges[:period]) / period

    for true_range in true_ranges[period:]:
        atr = (
            (atr * (period - 1)) + true_range
        ) / period

    return atr