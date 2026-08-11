from datetime import datetime
from zoneinfo import ZoneInfo

from trading_bot.bot import TradingBot
from trading_bot.models import Stock
from trading_bot.quick_flip_monitor import (
    QuickFlipMonitor,
)


EASTERN = ZoneInfo(
    "America/New_York"
)


class FakeAlpaca:
    def __init__(self):
        self.opening_calls = 0
        self.atr_calls = 0
        self.minute_calls = []

    def get_opening_15min_bars(
        self,
        **kwargs,
    ):
        self.opening_calls += 1

        return {
            "TEST": {
                "t": "2026-08-11T13:30:00Z",
                "o": 10.80,
                "h": 11.50,
                "l": 10.00,
                "c": 10.20,
                "v": 500000,
            }
        }

    def get_previous_day_ranges_all(
        self,
        **kwargs,
    ):
        self.atr_calls += 1

        return {
            "TEST": 1.00,
        }

    def get_historical_1min_bars(
        self,
        **kwargs,
    ):
        self.minute_calls.append(
            kwargs
        )

        return {
            "TEST": [],
        }


def build_bot():
    bot = TradingBot.__new__(
        TradingBot
    )

    bot.stocks = {
        "TEST": Stock(
            symbol="TEST"
        )
    }

    bot.symbols_csv = "TEST"

    bot.quick_flip_monitor = (
        QuickFlipMonitor()
    )

    bot.quick_flip_results = {}
    bot.quick_flip_status = {}

    bot.alpaca = FakeAlpaca()

    return bot


class Clock:
    def __init__(
        self,
        values,
    ):
        self.values = list(values)
        self.index = 0

    def now(self):
        if self.index >= len(
            self.values
        ):
            return self.values[-1]

        value = self.values[
            self.index
        ]

        self.index += 1

        return value


def test_live_monitor_fetches_static_inputs_once():
    bot = build_bot()

    clock = Clock(
        [
            datetime(
                2026, 8, 11,
                9, 50,
                tzinfo=EASTERN,
            ),
            datetime(
                2026, 8, 11,
                9, 50,
                tzinfo=EASTERN,
            ),
            datetime(
                2026, 8, 11,
                11, 0,
                tzinfo=EASTERN,
            ),
        ]
    )

    bot.run_quick_flip_monitor(
        date_str="2026-08-11",
        now_fn=clock.now,
        sleep_fn=lambda seconds: None,
        data_feed="iex",
    )

    assert (
        bot.alpaca.opening_calls
        == 1
    )

    assert bot.alpaca.atr_calls == 1


def test_live_monitor_incrementally_fetches_after_0945():
    bot = build_bot()

    clock = Clock(
        [
            datetime(
                2026, 8, 11,
                9, 50,
                tzinfo=EASTERN,
            ),
            datetime(
                2026, 8, 11,
                9, 50,
                tzinfo=EASTERN,
            ),
            datetime(
                2026, 8, 11,
                11, 0,
                tzinfo=EASTERN,
            ),
        ]
    )

    bot.run_quick_flip_monitor(
        date_str="2026-08-11",
        now_fn=clock.now,
        sleep_fn=lambda seconds: None,
        data_feed="iex",
    )

    first = (
        bot.alpaca.minute_calls[0]
    )

    assert (
        first["start_iso"]
        == "2026-08-11T13:45:00Z"
    )

    assert (
        first["end_iso"]
        == "2026-08-11T13:50:00Z"
    )


def test_live_monitor_does_not_create_stop_fields():
    bot = build_bot()

    bot.stocks[
        "TEST"
    ].stop_loss = 8.88

    bot.stocks[
        "TEST"
    ].trading_stop_loss = 8.77

    clock = Clock(
        [
            datetime(
                2026, 8, 11,
                9, 50,
                tzinfo=EASTERN,
            ),
            datetime(
                2026, 8, 11,
                9, 50,
                tzinfo=EASTERN,
            ),
            datetime(
                2026, 8, 11,
                11, 0,
                tzinfo=EASTERN,
            ),
        ]
    )

    bot.run_quick_flip_monitor(
        date_str="2026-08-11",
        now_fn=clock.now,
        sleep_fn=lambda seconds: None,
        data_feed="iex",
    )

    stock = bot.stocks[
        "TEST"
    ]

    assert stock.stop_loss == 8.88

    assert (
        stock.trading_stop_loss
        == 8.77
    )


def test_live_monitor_stops_at_1100():
    bot = build_bot()

    bot.run_quick_flip_monitor(
        date_str="2026-08-11",
        now_fn=lambda: datetime(
            2026, 8, 11,
            11, 0,
            tzinfo=EASTERN,
        ),
        sleep_fn=lambda seconds: None,
        data_feed="iex",
    )

    assert (
        bot.alpaca.opening_calls
        == 0
    )

    assert bot.alpaca.atr_calls == 0

    assert bot.alpaca.minute_calls == []


def test_rest_reconciliation_overrides_stream_bar(
    monkeypatch,
):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from trading_bot.bot import TradingBot
    from trading_bot.models import Stock

    eastern = ZoneInfo("America/New_York")

    bot = object.__new__(TradingBot)

    bot.stocks = {
        "OPEN": Stock(symbol="OPEN"),
    }

    bot.symbols_csv = "OPEN"

    class FakeAlpaca:
        def get_opening_15min_bars(
            self,
            symbols_csv,
            date_str,
            feed,
        ):
            return {
                "OPEN": {
                    "t": "2026-08-11T13:30:00Z",
                    "o": 10.00,
                    "h": 11.00,
                    "l": 9.00,
                    "c": 9.50,
                }
            }

        def get_previous_day_ranges_all(
            self,
            symbols_csv,
            date_str,
            feed,
        ):
            return {
                "OPEN": 1.00,
            }

        def get_historical_1min_bars(
            self,
            symbols_csv,
            start_iso,
            end_iso,
            feed,
        ):
            return {
                "OPEN": [
                    {
                        "t": "2026-08-11T13:45:00Z",
                        "o": 10.00,
                        "h": 10.35,
                        "l": 9.88,
                        "c": 10.30,
                        "v": 175,
                    }
                ]
            }

    bot.alpaca = FakeAlpaca()

    captured = {}

    class FakeQuickFlipMonitor:
        def evaluate_minute_bars(
            self,
            *,
            symbol,
            opening_bar,
            atr_14,
            minute_bars,
            evaluation_end,
            cutoff_reached,
        ):
            if minute_bars:
                captured["bar"] = dict(
                    minute_bars[0]
                )

            class Result:
                status = "WATCHING"
                signal = None

            return Result()

    bot.quick_flip_monitor = (
        FakeQuickFlipMonitor()
    )

    bot.quick_flip_results = {}
    bot.quick_flip_status = {}

    class FakeStream:
        def __init__(
            self,
            symbols,
            feed,
        ):
            self.symbols = symbols

        def collect_until(
            self,
            stop_time,
            stop_event=None,
        ):
            return self.snapshot()

        def snapshot(self):
            return {
                "OPEN": [
                    {
                        "t": "2026-08-11T13:45:00Z",
                        "o": 10.00,
                        "h": 10.20,
                        "l": 9.90,
                        "c": 10.10,
                        "v": 100,
                    }
                ]
            }

    times = iter(
        [
            datetime(
                2026,
                8,
                11,
                9,
                46,
                tzinfo=eastern,
            ),
            datetime(
                2026,
                8,
                11,
                9,
                46,
                tzinfo=eastern,
            ),
            datetime(
                2026,
                8,
                11,
                11,
                0,
                tzinfo=eastern,
            ),
        ]
    )

    bot.run_quick_flip_monitor(
        date_str="2026-08-11",
        now_fn=lambda: next(times),
        sleep_fn=lambda seconds: None,
        data_feed="iex",
        stream_factory=FakeStream,
    )

    assert captured["bar"]["h"] == 10.35
    assert captured["bar"]["l"] == 9.88
    assert captured["bar"]["c"] == 10.30
    assert captured["bar"]["v"] == 175
