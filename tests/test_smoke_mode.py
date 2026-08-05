import sys
from types import SimpleNamespace

import main as main_module


def test_scanner_smoke_writes_only_dashboard(trading_bot):
    events = []
    tracker_sentinel = object()

    trading_bot.scanner = object()
    trading_bot.scanner_statistics = None
    trading_bot.tracker = tracker_sentinel

    class FakeSheets:
        def write_scanner_dashboard(
                self,
                date_str,
                statistics,
                selected_symbols,
                scanner,
        ):
            events.append(
                (
                    "dashboard",
                    date_str,
                    tuple(
                        stats.symbol
                        for stats in statistics
                    ),
                    tuple(selected_symbols),
                    scanner,
                )
            )

    trading_bot.sheets = FakeSheets()

    def fake_refresh(date_str):
        events.append(
            ("refresh", date_str)
        )
        trading_bot.scanner_statistics = [
            SimpleNamespace(symbol="SNAP"),
        ]
        return ["CORE", "SNAP"]

    trading_bot.refresh_symbols_for_date = fake_refresh
    trading_bot.run_live_tracker = lambda: events.append(
        ("forbidden", "tracking")
    )
    trading_bot.run_strategy_and_write = (
        lambda date_str=None: events.append(
            ("forbidden", "strategy")
        )
    )
    trading_bot.run_production = lambda: events.append(
        ("forbidden", "production")
    )

    succeeded = trading_bot.run_scanner_smoke(
        date_str="2026-07-27"
    )

    assert succeeded is True
    assert events == [
        ("refresh", "2026-07-27"),
        (
            "dashboard",
            "2026-07-27",
            ("SNAP",),
            ("CORE", "SNAP"),
            trading_bot.scanner,
        ),
    ]
    assert trading_bot.tracker is tracker_sentinel


def test_scanner_smoke_stops_when_statistics_fail(trading_bot):
    events = []
    tracker_sentinel = object()

    trading_bot.scanner = object()
    trading_bot.scanner_statistics = None
    trading_bot.sheets = None
    trading_bot.tracker = tracker_sentinel

    def fake_refresh(date_str):
        events.append(
            ("refresh", date_str)
        )
        trading_bot.scanner_statistics = None
        return ["CORE"]

    trading_bot.refresh_symbols_for_date = fake_refresh
    trading_bot.run_live_tracker = lambda: events.append(
        ("forbidden", "tracking")
    )
    trading_bot.run_strategy_and_write = (
        lambda date_str=None: events.append(
            ("forbidden", "strategy")
        )
    )
    trading_bot.run_production = lambda: events.append(
        ("forbidden", "production")
    )

    succeeded = trading_bot.run_scanner_smoke(
        date_str="2026-07-27"
    )

    assert succeeded is False
    assert events == [
        ("refresh", "2026-07-27"),
    ]
    assert trading_bot.sheets is None
    assert trading_bot.tracker is tracker_sentinel


def test_main_routes_smoke_mode_only(
        monkeypatch,
):
    events = []

    class FakeBot:
        def __init__(self):
            events.append(("initialise", None))

        def run_scanner_smoke(
                self,
                date_str=None,
        ):
            events.append(
                ("smoke", date_str)
            )
            return True

    monkeypatch.setattr(
        main_module,
        "TradingBot",
        FakeBot,
    )
    monkeypatch.setattr(
        main_module,
        "setup_logging",
        lambda: "controlled-test.log",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "smoke",
            "2026-07-27",
        ],
    )

    result = main_module.main()

    assert result == 0
    assert events == [
        ("initialise", None),
        ("smoke", "2026-07-27"),
    ]
