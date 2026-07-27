from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import main as main_module

from trading_bot.alpaca_client import AlpacaClient
from trading_bot.models import Stock
from trading_bot.replay import HistoricalReplay


UTC = ZoneInfo("UTC")


def make_bar(
        minute: datetime,
        price: float,
) -> dict:
    return {
        "o": price,
        "h": price + 0.10,
        "l": price - 0.10,
        "c": price + 0.05,
        "v": 100,
        "t": minute.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
    }


class RecordingStrategy:
    def __init__(self):
        self.calls = []

    def evaluate(
            self,
            stock,
            opening_bar,
            atr,
    ):
        self.calls.append(
            (
                stock.symbol,
                opening_bar.copy(),
                atr,
            )
        )

        stock.opening_bar = opening_bar
        stock.atr = atr
        stock.signal = "INVEST"

        return stock


def test_replay_uses_only_revealed_opening_bars():
    start = datetime(
        2026,
        7,
        23,
        13,
        30,
        tzinfo=UTC,
    )

    complete_bars = [
        make_bar(
            start + timedelta(minutes=index),
            10.0 + index,
        )
        for index in range(15)
    ]

    future_bar = make_bar(
        start + timedelta(minutes=15),
        1000.0,
    )

    incomplete_bars = complete_bars[:-1]

    stocks = {
        "FULL": Stock(symbol="FULL"),
        "MISS": Stock(symbol="MISS"),
    }

    strategy = RecordingStrategy()

    replay = HistoricalReplay(
        stocks=stocks,
        strategy=strategy,
        speed=0,
    )

    summary = replay.run(
        date_str="2026-07-23",
        window_start=start,
        bars_by_symbol={
            "FULL": complete_bars + [future_bar],
            "MISS": incomplete_bars,
        },
        atrs={
            "FULL": 1.5,
            "MISS": 1.5,
        },
    )

    assert summary.processed_bars == {
        "FULL": 15,
        "MISS": 14,
    }
    assert summary.missing_bars == {
        "FULL": 0,
        "MISS": 1,
    }

    assert len(strategy.calls) == 1
    assert strategy.calls[0][0] == "FULL"

    assert stocks["FULL"].opening_bar["h"] < 1000
    assert stocks["FULL"].signal == "INVEST"

    assert stocks["MISS"].opening_bar is None
    assert stocks["MISS"].signal == "NO INVEST"


def test_replay_speed_controls_virtual_delay():
    start = datetime(
        2026,
        7,
        23,
        13,
        30,
        tzinfo=UTC,
    )

    bars = [
        make_bar(
            start + timedelta(minutes=index),
            10.0,
        )
        for index in range(15)
    ]

    sleep_calls = []

    replay = HistoricalReplay(
        stocks={
            "TEST": Stock(symbol="TEST"),
        },
        strategy=RecordingStrategy(),
        speed=60,
        sleep_fn=sleep_calls.append,
    )

    replay.run(
        date_str="2026-07-23",
        window_start=start,
        bars_by_symbol={
            "TEST": bars,
        },
        atrs={
            "TEST": 1.0,
        },
    )

    assert sleep_calls == [1.0] * 14


def test_historical_fetch_returns_all_valid_bars_sorted():
    client = object.__new__(AlpacaClient)

    later = {
        "o": 10,
        "h": 11,
        "l": 9,
        "c": 10.5,
        "t": "2026-07-23T13:31:00Z",
    }

    earlier = {
        "o": 9,
        "h": 10,
        "l": 8,
        "c": 9.5,
        "t": "2026-07-23T13:30:00Z",
    }

    invalid = {
        "o": -1,
        "h": 1,
        "l": -2,
        "c": 0,
        "t": "2026-07-23T13:32:00Z",
    }

    client._request = lambda **kwargs: {
        "bars": {
            "TEST": [
                later,
                invalid,
                earlier,
            ],
        },
    }

    result = client.get_historical_1min_bars(
        symbols_csv="TEST",
        start_iso="2026-07-23T13:30:00Z",
        end_iso="2026-07-23T13:44:59Z",
    )

    assert result["TEST"] == [
        earlier,
        later,
    ]


def test_main_dispatches_replay_mode(
        monkeypatch,
):
    events = []

    class FakeBot:
        def run_replay(
                self,
                date_str,
                speed,
        ):
            events.append(
                (date_str, speed)
            )

    monkeypatch.setattr(
        main_module,
        "TradingBot",
        FakeBot,
    )
    monkeypatch.setattr(
        main_module,
        "setup_logging",
        lambda: "logs/test.log",
    )
    monkeypatch.setattr(
        main_module.sys,
        "argv",
        [
            "main.py",
            "replay",
            "2026-07-23",
            "--speed",
            "60",
        ],
    )

    assert main_module.main() == 0
    assert events == [
        ("2026-07-23", 60.0),
    ]


def outcome_bar(
    timestamp: str,
    open_price: float,
    high_price: float,
    low_price: float,
    close_price: float,
) -> dict:
    return {
        "o": open_price,
        "h": high_price,
        "l": low_price,
        "c": close_price,
        "v": 100,
        "t": timestamp,
    }


def outcome_stock(symbol: str) -> Stock:
    stock = Stock(symbol=symbol)
    stock.signal = "INVEST"
    stock.limit_buy = 10.0
    stock.limit_sell = 11.0
    stock.stop_loss = 9.0
    return stock


def test_replay_calculates_all_outcome_states():
    stocks = {
        "WIN": outcome_stock("WIN"),
        "LOSS": outcome_stock("LOSS"),
        "NONE": outcome_stock("NONE"),
        "OPEN": outcome_stock("OPEN"),
    }

    replay = HistoricalReplay(
        stocks=stocks,
        strategy=RecordingStrategy(),
        speed=0,
    )

    replay.calculate_outcomes({
        "WIN": [
            outcome_bar(
                "2026-07-23T13:45:00Z",
                10.2,
                10.4,
                9.9,
                10.1,
            ),
            outcome_bar(
                "2026-07-23T13:46:00Z",
                10.5,
                11.1,
                10.4,
                11.0,
            ),
        ],
        "LOSS": [
            outcome_bar(
                "2026-07-23T13:45:00Z",
                10.0,
                11.1,
                8.9,
                9.5,
            ),
        ],
        "NONE": [
            outcome_bar(
                "2026-07-23T13:45:00Z",
                10.7,
                10.9,
                10.5,
                10.8,
            ),
        ],
        "OPEN": [
            outcome_bar(
                "2026-07-23T13:45:00Z",
                10.1,
                10.5,
                9.9,
                10.3,
            ),
        ],
    })

    assert stocks["WIN"].outcome["status"] == "WIN"
    assert stocks["WIN"].outcome["pnlPerShare"] == 1.0
    assert stocks["WIN"].outcome["returnPct"] == 10.0

    assert stocks["LOSS"].outcome["status"] == "LOSS"
    assert stocks["LOSS"].outcome["pnlPerShare"] == -1.0
    assert "conservative loss" in (
        stocks["LOSS"].outcome["detail"]
    )

    assert stocks["NONE"].outcome["status"] == "NO ENTRY"
    assert stocks["OPEN"].outcome["status"] == "STILL OPEN"


def test_historical_fetch_follows_pagination():
    client = object.__new__(AlpacaClient)
    requested_tokens = []

    def fake_request(**kwargs):
        token = kwargs["params"].get("page_token")
        requested_tokens.append(token)

        if token is None:
            return {
                "bars": {
                    "TEST": [
                        make_bar(
                            datetime(
                                2026,
                                7,
                                23,
                                13,
                                31,
                                tzinfo=UTC,
                            ),
                            10.0,
                        ),
                    ],
                },
                "next_page_token": "NEXT",
            }

        return {
            "bars": {
                "TEST": [
                    make_bar(
                        datetime(
                            2026,
                            7,
                            23,
                            13,
                            30,
                            tzinfo=UTC,
                        ),
                        9.0,
                    ),
                ],
            },
            "next_page_token": None,
        }

    client._request = fake_request

    result = client.get_historical_1min_bars(
        symbols_csv="TEST",
        start_iso="2026-07-23T13:30:00Z",
        end_iso="2026-07-23T20:00:00Z",
    )

    assert requested_tokens == [
        None,
        "NEXT",
    ]
    assert [
        bar["t"]
        for bar in result["TEST"]
    ] == [
        "2026-07-23T13:30:00Z",
        "2026-07-23T13:31:00Z",
    ]
