from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import trading_bot.bot as bot_module

from trading_bot.bot import TradingBot
from trading_bot.models import Stock


EASTERN = ZoneInfo("America/New_York")


def make_bot(events):
    bot = object.__new__(TradingBot)

    bot.stocks = {
        "OPEN": Stock(symbol="OPEN"),
    }
    bot.sheets = SimpleNamespace()

    bot.evaluate_active_strategy = (
        lambda **kwargs: events.append(
            (
                "evaluate",
                kwargs["evaluation_end"].strftime(
                    "%H:%M:%S"
                ),
            )
        )
    )

    bot.publish_current_strategy_results = (
        lambda **kwargs: events.append("publish")
    )

    bot._publish_dashboard_session = (
        lambda **kwargs: events.append(
            (
                "dashboard",
                kwargs["source"],
            )
        )
    )

    bot.finalise_strategy_workbook = (
        lambda **kwargs: events.append("finalise")
    )

    bot.calculate_live_fibonacci_outcomes = (
        lambda **kwargs: events.append(
            (
                "outcomes",
                kwargs["outcome_end"].strftime(
                    "%H:%M:%S"
                ),
            )
        )
    )

    return bot


def sequence_clock(values):
    queued = list(values)

    def now():
        if queued:
            return queued.pop(0)

        return values[-1]

    return now


def test_monitor_rejects_wrong_active_strategy(
        monkeypatch,
):
    bot = make_bot([])

    monkeypatch.setattr(
        bot_module,
        "ACTIVE_STRATEGY",
        "MANIPULATION_OPENING_15M",
    )

    try:
        bot.run_fibonacci_monitor(
            date_str="2026-08-03",
            now_fn=lambda: datetime(
                2026,
                8,
                3,
                10,
                0,
                tzinfo=EASTERN,
            ),
            sleep_fn=lambda seconds: None,
        )
    except RuntimeError as error:
        assert "ACTIVE_STRATEGY=FIBONACCI_61_8" in str(
            error
        )
    else:
        raise AssertionError(
            "Wrong strategy should have been rejected."
        )


def test_monitor_uses_completed_minute_boundary(
        monkeypatch,
):
    events = []
    bot = make_bot(events)

    signatures = iter([
        (),
        (),
    ])

    bot.current_signal_signature = (
        lambda: next(signatures)
    )

    monkeypatch.setattr(
        bot_module,
        "ACTIVE_STRATEGY",
        "FIBONACCI_61_8",
    )
    monkeypatch.setattr(
        bot_module,
        "FIBONACCI_MONITOR_CUTOFF",
        "09:47",
    )

    bot.run_fibonacci_monitor(
        date_str="2026-08-03",
        write_sheets=False,
        publish_dashboard=False,
        now_fn=sequence_clock([
            datetime(
                2026,
                8,
                3,
                9,
                45,
                32,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                45,
                32,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                47,
                0,
                tzinfo=EASTERN,
            ),
        ]),
        sleep_fn=lambda seconds: events.append(
            ("sleep", seconds)
        ),
    )

    assert (
        "evaluate",
        "09:45:00",
    ) in events


def test_monitor_publishes_only_on_signal_change(
        monkeypatch,
):
    events = []
    bot = make_bot(events)

    signatures = iter([
        (),
        (),
        (("OPEN", "FIBONACCI_61_8"),),
        (("OPEN", "FIBONACCI_61_8"),),
    ])

    bot.current_signal_signature = (
        lambda: next(signatures)
    )

    monkeypatch.setattr(
        bot_module,
        "ACTIVE_STRATEGY",
        "FIBONACCI_61_8",
    )
    monkeypatch.setattr(
        bot_module,
        "FIBONACCI_MONITOR_CUTOFF",
        "09:47",
    )

    bot.run_fibonacci_monitor(
        date_str="2026-08-03",
        write_sheets=True,
        publish_dashboard=True,
        now_fn=sequence_clock([
            datetime(
                2026,
                8,
                3,
                9,
                45,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                45,
                10,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                46,
                10,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                47,
                tzinfo=EASTERN,
            ),
        ]),
        sleep_fn=lambda seconds: None,
    )

    assert events.count("publish") == 2
    assert events.count("finalise") == 1


def test_monitor_dry_run_skips_external_outputs(
        monkeypatch,
):
    events = []
    bot = make_bot(events)

    bot.current_signal_signature = lambda: ()

    monkeypatch.setattr(
        bot_module,
        "ACTIVE_STRATEGY",
        "FIBONACCI_61_8",
    )
    monkeypatch.setattr(
        bot_module,
        "FIBONACCI_MONITOR_CUTOFF",
        "09:46",
    )

    bot.run_fibonacci_monitor(
        date_str="2026-08-03",
        write_sheets=False,
        publish_dashboard=False,
        now_fn=sequence_clock([
            datetime(
                2026,
                8,
                3,
                9,
                45,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                45,
                5,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                46,
                tzinfo=EASTERN,
            ),
        ]),
        sleep_fn=lambda seconds: None,
    )

    assert "publish" not in events
    assert "finalise" not in events
    assert not any(
        isinstance(event, tuple)
        and event[0] == "dashboard"
        for event in events
    )


def test_monitor_always_publishes_final_dashboard(
        monkeypatch,
):
    events = []
    bot = make_bot(events)

    bot.current_signal_signature = lambda: ()

    monkeypatch.setattr(
        bot_module,
        "ACTIVE_STRATEGY",
        "FIBONACCI_61_8",
    )
    monkeypatch.setattr(
        bot_module,
        "FIBONACCI_MONITOR_CUTOFF",
        "09:46",
    )

    bot.run_fibonacci_monitor(
        date_str="2026-08-03",
        write_sheets=False,
        publish_dashboard=True,
        now_fn=sequence_clock([
            datetime(
                2026,
                8,
                3,
                9,
                45,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                45,
                5,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                46,
                tzinfo=EASTERN,
            ),
        ]),
        sleep_fn=lambda seconds: None,
    )

    assert (
        "outcomes",
        "09:46:00",
    ) in events

    assert (
        "dashboard",
        "LIVE_FIBONACCI_FINAL",
    ) in events


def test_monitor_calculates_outcomes_in_dry_run(
        monkeypatch,
):
    events = []
    bot = make_bot(events)

    bot.current_signal_signature = lambda: ()

    monkeypatch.setattr(
        bot_module,
        "ACTIVE_STRATEGY",
        "FIBONACCI_61_8",
    )
    monkeypatch.setattr(
        bot_module,
        "FIBONACCI_MONITOR_CUTOFF",
        "09:46",
    )

    bot.run_fibonacci_monitor(
        date_str="2026-08-03",
        write_sheets=False,
        publish_dashboard=False,
        now_fn=sequence_clock([
            datetime(
                2026,
                8,
                3,
                9,
                45,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                45,
                5,
                tzinfo=EASTERN,
            ),
            datetime(
                2026,
                8,
                3,
                9,
                46,
                tzinfo=EASTERN,
            ),
        ]),
        sleep_fn=lambda seconds: None,
    )

    assert (
        "outcomes",
        "09:46:00",
    ) in events

    assert not any(
        isinstance(event, tuple)
        and event[0] == "dashboard"
        for event in events
    )
