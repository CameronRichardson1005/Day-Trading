from types import SimpleNamespace

import pytest


def test_ticker_failure_does_not_stop_remaining_tickers(trading_bot):
    events = []

    trading_bot.stocks = {
        "FAIL": SimpleNamespace(
            symbol="FAIL",
            signal=None,
        ),
        "PASS": SimpleNamespace(
            symbol="PASS",
            signal=None,
        ),
    }

    class FakeAlpaca:
        def get_opening_15min_bars(
            self,
            symbols_csv,
            date_str,
        ):
            events.append("opening bars requested")
            return {
                "FAIL": {"test": "bar"},
                "PASS": {"test": "bar"},
            }

        def get_previous_day_ranges_all(
            self,
            symbols_csv,
            date_str,
        ):
            events.append("ATRs requested")
            return {
                "FAIL": 1.0,
                "PASS": 1.0,
            }

    class FakeStrategy:
        def evaluate(
            self,
            stock,
            opening_bar,
            atr,
        ):
            events.append(f"evaluated {stock.symbol}")

            if stock.symbol == "FAIL":
                raise RuntimeError(
                    "CONTROLLED TICKER FAILURE"
                )

            stock.signal = "INVEST"

    trading_bot.alpaca = FakeAlpaca()
    trading_bot.strategy = FakeStrategy()
    trading_bot.symbols_csv = "FAIL,PASS"

    trading_bot.calculate_strategy("2026-07-23")

    assert trading_bot.stocks["FAIL"].signal == "NO INVEST"
    assert trading_bot.stocks["PASS"].signal == "INVEST"
    assert events == [
        "opening bars requested",
        "ATRs requested",
        "evaluated FAIL",
        "evaluated PASS",
    ]


def test_orders_write_is_attempted_when_invest_write_fails(trading_bot):
    events = []

    trading_bot.stocks = {
        "OPEN": SimpleNamespace(
            symbol="OPEN",
            signal="INVEST",
        ),
    }

    trading_bot.calculate_strategy = lambda date_str: events.append(
        "strategy calculated"
    )
    trading_bot.initialise_sheets = lambda: events.append(
        "sheets initialised"
    )

    class FakeSheets:
        def write_strategy_results(
            self,
            date_str,
            stocks,
        ):
            events.append("Invest attempted")
            raise RuntimeError(
                "CONTROLLED INVEST FAILURE"
            )

        def write_orders(
            self,
            date_str,
            stocks,
        ):
            events.append("Orders attempted")

    trading_bot.sheets = FakeSheets()

    with pytest.raises(
        RuntimeError,
        match="One or more strategy writes failed",
    ):
        trading_bot.run_strategy_and_write(
            date_str="2026-07-23"
        )

    assert events == [
        "strategy calculated",
        "sheets initialised",
        "Invest attempted",
        "Orders attempted",
    ]
