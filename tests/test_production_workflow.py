from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import trading_bot.bot as bot_module

from conftest import install_clock


EASTERN = ZoneInfo("America/New_York")


def test_weekend_stops_without_running_workflow(
    monkeypatch,
    trading_bot,
):
    trading_bot.run_live_tracker = lambda: None
    trading_bot.run_strategy_and_write = (
        lambda date_str=None: None
    )

    install_clock(
        monkeypatch,
        bot_module,
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
        lambda seconds: None,
    )

    trading_bot.run_production()


def test_before_open_waits_then_runs_full_workflow(
    monkeypatch,
    trading_bot,
):
    events = []

    trading_bot.run_live_tracker = lambda: events.append(
        "tracker"
    )
    trading_bot.run_strategy_and_write = (
        lambda date_str=None: events.append(
            f"strategy:{date_str}"
        )
    )

    install_clock(
        monkeypatch,
        bot_module,
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

    trading_bot.run_production()

    assert events == [
        "sleep:1800.0",
        "tracker",
        "strategy:2026-07-27",
    ]


def test_during_opening_window_tracks_then_waits(
    monkeypatch,
    trading_bot,
):
    events = []

    trading_bot.run_live_tracker = lambda: events.append(
        "tracker"
    )
    trading_bot.run_strategy_and_write = (
        lambda date_str=None: events.append(
            f"strategy:{date_str}"
        )
    )

    install_clock(
        monkeypatch,
        bot_module,
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

    trading_bot.run_production()

    assert events == [
        "tracker",
        "sleep:5.0",
        "strategy:2026-07-27",
    ]


def test_after_opening_window_runs_strategy_immediately(
    monkeypatch,
    trading_bot,
):
    events = []

    trading_bot.run_live_tracker = lambda: events.append(
        "tracker"
    )
    trading_bot.run_strategy_and_write = (
        lambda date_str=None: events.append(
            f"strategy:{date_str}"
        )
    )

    install_clock(
        monkeypatch,
        bot_module,
        [
            datetime(
                2026,
                7,
                27,
                9,
                50,
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

    trading_bot.run_production()

    assert events == [
        "strategy:2026-07-27",
    ]


def test_production_stops_after_cutoff(
        monkeypatch,
        capsys,
        trading_bot,
):
    from datetime import datetime as RealDateTime

    real_datetime = bot_module.datetime

    class CutoffDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(
                2026,
                7,
                27,
                10,
                0,
                tzinfo=tz,
            )

    monkeypatch.setattr(
        bot_module,
        "datetime",
        CutoffDateTime,
    )

    def unexpected_workflow(*args, **kwargs):
        raise AssertionError(
            "Production workflow should not start "
            "after the cutoff."
        )

    trading_bot.run_live_tracker = unexpected_workflow
    trading_bot.run_strategy_and_write = unexpected_workflow

    trading_bot.run_production()

    output = capsys.readouterr().out

    assert (
        "The 10:00 New York production cutoff "
        "has passed."
        in output
    )
    assert (
        "spreadsheet writes were not started."
        in output
    )


def test_tracking_failure_prevents_strategy_write(
        monkeypatch,
        trading_bot,
):
    from datetime import datetime as RealDateTime

    real_datetime = bot_module.datetime

    class OpeningWindowDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(
                2026,
                7,
                27,
                9,
                35,
                tzinfo=tz,
            )

    monkeypatch.setattr(
        bot_module,
        "datetime",
        OpeningWindowDateTime,
    )

    def fail_tracking():
        raise RuntimeError("Tracker failed.")

    def unexpected_strategy(*args, **kwargs):
        raise AssertionError(
            "Strategy writes must not run after "
            "a tracking failure."
        )

    trading_bot.run_live_tracker = fail_tracking
    trading_bot.run_strategy_and_write = unexpected_strategy

    with pytest.raises(
        RuntimeError,
        match="Tracker failed",
    ):
        trading_bot.run_production()
