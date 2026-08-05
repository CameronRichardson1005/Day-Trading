from unittest.mock import Mock

import pytest

from trading_bot.models import Stock
from trading_bot.tracker import MinuteTracker

from conftest import make_bar


def _build_tracker() -> MinuteTracker:
    alpaca = Mock()
    alpaca.get_scanner_statistics.return_value = []
    alpaca.get_opening_15min_bars.return_value = {}
    alpaca.get_previous_day_ranges_all.return_value = {}
    alpaca.get_1min_bars.return_value = {}
    alpaca.get_historical_1min_bars.return_value = {}

    sheets = Mock()
    sheets.get_or_create_worksheet.return_value = Mock()

    tracker = MinuteTracker(
        alpaca=alpaca,
        sheets=sheets,
        stocks={
            "OPEN": Stock(symbol="OPEN"),
        },
        symbols_csv="OPEN",
    )
    tracker.symbol_rows = {"OPEN": 2}
    return tracker


@pytest.fixture
def tracker() -> MinuteTracker:
    return _build_tracker()


def test_merge_stream_bars_deduplicates_timestamps(tracker):
    stock = tracker.stocks["OPEN"]

    original = make_bar(
        "2026-07-28T13:30:00Z",
        open_price=4.10,
        high=4.20,
        low=4.05,
        close=4.15,
        volume=100,
    )

    stock.minute_bars.append(original)
    tracker.process_bar(stock, original)

    streamed = {
        "OPEN": [
            make_bar(
                "2026-07-28T13:30:00Z",
                open_price=4.10,
                high=4.20,
                low=4.05,
                close=4.15,
                volume=100,
            )
        ]
    }

    counts = tracker.merge_stream_bars(streamed)

    assert counts["OPEN"] == 1
    assert len(stock.minute_bars) == 1
    assert stock.green_minutes == 1
    assert stock.red_minutes == 0


def test_updated_stream_bar_replaces_rest_bar(tracker):
    stock = tracker.stocks["OPEN"]

    rest_bar = make_bar(
        "2026-07-28T13:30:00Z",
        open_price=4.10,
        high=4.20,
        low=4.05,
        close=4.15,
        volume=100,
    )

    stock.minute_bars.append(rest_bar)
    tracker.process_bar(stock, rest_bar)

    updated_bar = make_bar(
        "2026-07-28T13:30:00Z",
        open_price=4.10,
        high=4.30,
        low=4.05,
        close=4.25,
        volume=150,
    )

    counts = tracker.merge_stream_bars(
        {"OPEN": [updated_bar]}
    )

    assert counts["OPEN"] == 1
    assert stock.minute_bars[0]["h"] == 4.30
    assert stock.minute_bars[0]["c"] == 4.25
    assert stock.minute_bars[0]["v"] == 150
    assert stock.running_high == 4.30


def test_stream_merge_rebuilds_bars_chronologically(tracker):
    stock = tracker.stocks["OPEN"]

    streamed = {
        "OPEN": [
            make_bar(
                "2026-07-28T13:32:00Z",
                open_price=4.20,
                high=4.25,
                low=4.15,
                close=4.18,
                volume=100,
            ),
            make_bar(
                "2026-07-28T13:30:00Z",
                open_price=4.10,
                high=4.15,
                low=4.05,
                close=4.12,
                volume=100,
            ),
            make_bar(
                "2026-07-28T13:31:00Z",
                open_price=4.12,
                high=4.22,
                low=4.10,
                close=4.20,
                volume=100,
            ),
        ]
    }

    counts = tracker.merge_stream_bars(streamed)

    assert counts["OPEN"] == 3
    assert [
        bar["t"]
        for bar in stock.minute_bars
    ] == [
        "2026-07-28T13:30:00Z",
        "2026-07-28T13:31:00Z",
        "2026-07-28T13:32:00Z",
    ]

    assert stock.green_minutes == 2
    assert stock.red_minutes == 1
    assert stock.running_high == 4.25
    assert stock.running_low == 4.05


def test_merge_does_not_fabricate_missing_minutes(tracker):
    stock = tracker.stocks["OPEN"]

    streamed = {
        "OPEN": [
            make_bar(
                "2026-07-28T13:30:00Z",
                open_price=4.10,
                high=4.20,
                low=4.05,
                close=4.15,
                volume=100,
            ),
            make_bar(
                "2026-07-28T13:32:00Z",
                open_price=4.15,
                high=4.25,
                low=4.10,
                close=4.20,
                volume=100,
            ),
        ]
    }

    counts = tracker.merge_stream_bars(streamed)

    assert counts["OPEN"] == 2
    assert len(stock.minute_bars) == 2
    assert all(
        bar["t"] != "2026-07-28T13:31:00Z"
        for bar in stock.minute_bars
    )


def test_reconciliation_merges_late_rest_bar(tracker):
    stock = tracker.stocks["OPEN"]

    first_bar = make_bar(
        "2026-07-28T13:30:00Z",
        open_price=4.10,
        high=4.20,
        low=4.05,
        close=4.15,
        volume=100,
    )

    stock.minute_bars.append(first_bar)
    tracker.process_bar(stock, first_bar)

    tracker.alpaca.get_historical_1min_bars.return_value = {
        "OPEN": [
            first_bar,
            make_bar(
                "2026-07-28T13:31:00Z",
                open_price=4.15,
                high=4.25,
                low=4.10,
                close=4.20,
                volume=100,
            ),
        ]
    }

    from datetime import datetime

    counts = tracker.reconcile_window(
        window_start=datetime(
            2026,
            7,
            28,
            13,
            30,
        ),
        window_end=datetime(
            2026,
            7,
            28,
            13,
            44,
        ),
        delay_seconds=0,
    )

    assert counts["OPEN"] == 2
    assert len(stock.minute_bars) == 2
    assert stock.green_minutes == 2
