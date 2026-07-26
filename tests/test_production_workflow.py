from datetime import datetime
from zoneinfo import ZoneInfo

import trading_bot.bot as bot_module
from trading_bot.bot import TradingBot


EASTERN = ZoneInfo("America/New_York")


def make_bot(events):
    bot = object.__new__(TradingBot)

    bot.run_live_tracker = lambda: events.append(
        "tracker"
    )

    bot.run_strategy_and_write = (
        lambda date_str=None: events.append(
            f"strategy:{date_str}"
        )
    )

    return bot


def install_clock(monkeypatch, times):
    class FakeDateTime(datetime):
        queued_times = list(times)

        @classmethod
        def now(cls, tz=None):
            return cls.queued_times.pop(0)

    monkeypatch.setattr(
        bot_module,
        "datetime",
        FakeDateTime,
    )


def test_weekend_stops_without_running_workflow(
    monkeypatch,
):
    events = []
    bot = make_bot(events)

    install_clock(
        monkeypatch,
        [
            datetime(
                2026,
                7,
                26,
                10,
                0,
                tzinfo=EASTERN,
            ),
        ],
    )

    monkeypatch.setattr(
        bot_module.time_module,
        "sleep",
        lambda seconds: events.append(
            f"sleep:{seconds}"
        ),
    )

    bot.run_production()

    assert events == []


def test_before_open_waits_then_runs_full_workflow(
    monkeypatch,
):
    events = []
    bot = make_bot(events)

    install_clock(
        monkeypatch,
        [
            datetime(
                2026,
                7,
                27,
                9,
                0,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                7,
                27,
                9,
                45,
                15,
                tzinfo=EASTERN,
            ),
        ],
    )

    monkeypatch.setattr(
        bot_module.time_module,
        "sleep",
        lambda seconds: events.append(
            f"sleep:{seconds}"
        ),
    )

    bot.run_production()

    assert events == [
        "sleep:1800.0",
        "tracker",
        "strategy:2026-07-27",
    ]


def test_during_opening_window_tracks_then_waits(
    monkeypatch,
):
    events = []
    bot = make_bot(events)

    install_clock(
        monkeypatch,
        [
            datetime(
                2026,
                7,
                27,
                9,
                40,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                7,
                27,
                9,
                45,
                10,
                tzinfo=EASTERN,
            ),
        ],
    )

    monkeypatch.setattr(
        bot_module.time_module,
        "sleep",
        lambda seconds: events.append(
            f"sleep:{seconds}"
        ),
    )

    bot.run_production()

    assert events == [
        "tracker",
        "sleep:5.0",
        "strategy:2026-07-27",
    ]


def test_after_opening_window_runs_strategy_immediately(
    monkeypatch,
):
    events = []
    bot = make_bot(events)

    install_clock(
        monkeypatch,
        [
            datetime(
                2026,
                7,
                27,
                10,
                0,
                tzinfo=EASTERN,
            ),
        ],
    )

    monkeypatch.setattr(
        bot_module.time_module,
        "sleep",
        lambda seconds: events.append(
            f"sleep:{seconds}"
        ),
    )

    bot.run_production()

    assert events == [
        "strategy:2026-07-27",
    ]
