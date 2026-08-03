from trading_bot.fibonacci_retracement import (
    analyse_retracement_level,
    find_upward_impulse,
    metrics_for,
)


def bar(
    minute: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1000,
):
    hour = 13 + (30 + minute) // 60
    minute_value = (30 + minute) % 60

    return {
        "t": (
            f"2026-07-30T{hour:02d}:"
            f"{minute_value:02d}:00Z"
        ),
        "o": open_price,
        "h": high,
        "l": low,
        "c": close,
        "v": volume,
        "vw": close,
    }


def test_finds_chronological_upward_impulse():
    bars = [
        bar(
            0,
            open_price=10.00,
            high=10.05,
            low=9.95,
            close=10.02,
        ),
        bar(
            1,
            open_price=10.02,
            high=10.40,
            low=10.00,
            close=10.35,
        ),
        bar(
            2,
            open_price=10.35,
            high=11.10,
            low=10.30,
            close=11.00,
        ),
    ]

    result = find_upward_impulse(
        bars,
        atr=1.0,
        minimum_atr_multiple=1.0,
    )

    assert result == (0, 2)


def test_rejects_impulse_below_atr_requirement():
    bars = [
        bar(
            0,
            open_price=10.00,
            high=10.10,
            low=10.00,
            close=10.05,
        ),
        bar(
            1,
            open_price=10.05,
            high=10.40,
            low=10.03,
            close=10.30,
        ),
    ]

    assert find_upward_impulse(
        bars,
        atr=1.0,
        minimum_atr_multiple=1.0,
    ) is None


def test_detects_confirmed_50_percent_retracement():
    bars = [
        bar(
            0,
            open_price=10.00,
            high=10.10,
            low=10.00,
            close=10.08,
            volume=2000,
        ),
        bar(
            1,
            open_price=10.08,
            high=10.60,
            low=10.05,
            close=10.55,
            volume=2200,
        ),
        bar(
            2,
            open_price=10.55,
            high=11.20,
            low=10.50,
            close=11.10,
            volume=2500,
        ),
        bar(
            3,
            open_price=11.10,
            high=11.12,
            low=10.62,
            close=10.70,
            volume=1000,
        ),
        bar(
            4,
            open_price=10.68,
            high=10.85,
            low=10.60,
            close=10.82,
            volume=900,
        ),
        bar(
            5,
            open_price=10.82,
            high=10.90,
            low=10.75,
            close=10.88,
        ),
        bar(
            6,
            open_price=10.88,
            high=11.25,
            low=10.85,
            close=11.20,
        ),
    ]

    result = analyse_retracement_level(
        date_str="2026-07-30",
        symbol="TEST",
        data_feed="iex",
        bars=bars,
        atr=1.0,
        level_name="FIB_50_0",
        ratio=0.500,
        minimum_reward_risk=1.0,
    )

    assert result.setup_found
    assert result.confirmation_time == "09:34"
    assert result.entry_price == 10.86
    assert result.outcome == "WIN"
    assert result.exit_reason == "IMPULSE_HIGH"
    assert result.pullback_volume_ratio is not None
    assert result.pullback_volume_ratio < 1.0


def test_rejects_setup_without_confirmation():
    bars = [
        bar(
            0,
            open_price=10.00,
            high=10.10,
            low=10.00,
            close=10.05,
        ),
        bar(
            1,
            open_price=10.05,
            high=11.10,
            low=10.03,
            close=11.00,
        ),
        bar(
            2,
            open_price=11.00,
            high=11.02,
            low=10.50,
            close=10.55,
        ),
        bar(
            3,
            open_price=10.55,
            high=10.60,
            low=10.40,
            close=10.45,
        ),
    ]

    result = analyse_retracement_level(
        date_str="2026-07-30",
        symbol="TEST",
        data_feed="iex",
        bars=bars,
        atr=1.0,
        level_name="FIB_50_0",
        ratio=0.500,
    )

    assert not result.setup_found
    assert result.rejection_reason == (
        "NO_BULLISH_CONFIRMATION"
    )


def test_metrics_cover_profitable_and_losing_trades():
    winning_bars = [
        bar(
            0,
            open_price=10.00,
            high=10.10,
            low=10.00,
            close=10.08,
        ),
        bar(
            1,
            open_price=10.08,
            high=11.20,
            low=10.05,
            close=11.10,
        ),
        bar(
            2,
            open_price=11.10,
            high=11.12,
            low=10.60,
            close=10.65,
        ),
        bar(
            3,
            open_price=10.65,
            high=10.85,
            low=10.60,
            close=10.82,
        ),
        bar(
            4,
            open_price=10.82,
            high=11.25,
            low=10.80,
            close=11.20,
        ),
    ]

    result = analyse_retracement_level(
        date_str="2026-07-30",
        symbol="TEST",
        data_feed="iex",
        bars=winning_bars,
        atr=1.0,
        level_name="FIB_50_0",
        ratio=0.500,
        minimum_reward_risk=1.0,
    )

    metrics = metrics_for([result])

    assert metrics.setups == 1
    assert metrics.entered_trades == 1
    assert metrics.wins == 1
    assert metrics.losses == 0
    assert metrics.win_rate_pct == 100.0
