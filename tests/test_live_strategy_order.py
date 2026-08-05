from datetime import datetime as RealDateTime
from types import SimpleNamespace
from unittest.mock import Mock

import trading_bot.bot as bot_module

from trading_bot.models import Stock

from conftest import frozen_datetime


def test_live_strategy_runs_before_dashboard(
        monkeypatch,
        trading_bot,
):
    events = []

    FakeDateTime = frozen_datetime(2026, 7, 28, 9, 25)

    class FakeThread:
        def __init__(self, *args, **kwargs):
            self.target = kwargs["target"]

        def start(self):
            events.append("stream-start")

        def join(self, timeout=None):
            events.append("stream-join")

        def is_alive(self):
            return False

    class FakeTracker:
        def track_window(
                self,
                date_str,
                window_start,
                window_end,
        ):
            events.append("track")

        def merge_stream_bars(
                self,
                streamed_bars,
        ):
            events.append("merge")

    trading_bot.stocks = {
        "OPEN": Stock(symbol="OPEN"),
    }
    trading_bot.symbol_reliability = None
    trading_bot.scanner_statistics = None
    trading_bot.scanner = SimpleNamespace()
    trading_bot.sheets = Mock()
    trading_bot.tracker = FakeTracker()

    trading_bot.refresh_symbols_for_date = (
        lambda date_str: ["OPEN"]
    )
    trading_bot.initialise_sheets = (
        lambda write_sheets=True: None
    )

    trading_bot.run_strategy_and_write = (
        lambda date_str: events.append("strategy")
    )

    trading_bot._publish_dashboard_session = (
        lambda **kwargs: events.append("dashboard")
    )

    monkeypatch.setattr(
        bot_module,
        "datetime",
        FakeDateTime,
    )
    monkeypatch.setattr(
        bot_module,
        "Thread",
        FakeThread,
    )

    class FakeStream:
        def __init__(self, *args, **kwargs):
            pass

        def collect_until(self, stop_time):
            return {}

    monkeypatch.setattr(
        bot_module,
        "AlpacaStockStream",
        FakeStream,
    )

    trading_bot.run_live_tracker(
        write_sheets=True,
        publish_dashboard=True,
    )

    assert "strategy" in events
    assert "dashboard" in events
    assert events.index("strategy") < events.index(
        "dashboard"
    )
