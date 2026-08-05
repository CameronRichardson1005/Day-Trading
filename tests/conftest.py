"""
Shared pytest fixtures and helper factories for the trading-bot test suite.

Tests in this repo allocate bare ``TradingBot`` instances via
``object.__new__`` so that ``TradingBot.__init__`` does not run
(it builds ``AlpacaClient`` and ``DashboardExporter`` which require a
populated ``.env``). They also need to construct minimal OHLCV bar
dicts, ``StockStats`` rows, and ``Stock`` records over and over. This
module is the single source of truth for those fixtures.

Each helper matches the most-common signature seen in the test suite.
Migrations of older call sites may need to adapt parameter ordering,
but the produced dict/dataclass shape is identical to what each test
used to build locally.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Sequence
from unittest.mock import Mock

import pytest

from trading_bot.bot import TradingBot
from trading_bot.models import Stock
from trading_bot.scanner import StockStats
from trading_bot.tracker import MinuteTracker


# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def make_bar(
    timestamp: str | datetime,
    open_price: float | None = None,
    high: float | None = None,
    low: float | None = None,
    close: float | None = None,
    volume: int = 1000,
    vwap: float | None = None,
) -> dict[str, Any]:
    """Build a one-minute OHLCV bar dict matching Alpaca's shape.

    ``timestamp`` may be an ISO-8601 string or a ``datetime`` (rendered
    as ``%Y-%m-%dT%H:%M:%SZ``). ``open_price`` and friends are
    positional to keep call sites terse for tests that need an
    arbitrary flat-price bar; pass ``high``/``low``/``close`` only when
    the test cares about them and let the others default to ``None``
    — call sites that need precise OHLC should pass all four.
    """
    if isinstance(timestamp, datetime):
        timestamp_str = timestamp.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    else:
        timestamp_str = timestamp

    return {
        "t": timestamp_str,
        "o": open_price,
        "h": high,
        "l": low,
        "c": close,
        "v": volume,
        "vw": vwap if vwap is not None else close,
    }


def make_stats(
    symbol: str,
    *,
    valid_bars: int = 30,
    avg_volume: float = 1_000_000,
    avg_price: float = 10.0,
    avg_range: float = 0.50,
    avg_range_pct: float = 5.0,
) -> StockStats:
    """Build a ``StockStats`` record with sensible defaults.

    Defaults match the canonical "rankable mid-cap candidate" shape
    used throughout the scanner tests.
    """
    return StockStats(
        symbol=symbol,
        valid_bars=valid_bars,
        avg_volume=avg_volume,
        avg_price=avg_price,
        avg_range=avg_range,
        avg_range_pct=avg_range_pct,
    )


def make_stock(
    symbol: str = "TEST",
    *,
    signal: str = "INVEST",
    opening_bar: dict[str, Any] | None = None,
    atr: float | None = 1.0,
    candle_range: float | None = 2.0,
    atr_threshold: float | None = 0.5,
    is_manipulation: bool = True,
    is_red: bool = True,
    limit_buy: float | None = 9.0,
    limit_sell: float | None = 9.382,
    stop_loss: float | None = 8.809,
    trading_stop_loss: float | None = 8.759,
) -> Stock:
    """Build a ``Stock`` record populated with the canonical INVEST
    happy-path shape.

    Every field is overridable via kwarg; tests that need a
    NO INVEST signal, an empty opening_bar, or no stops pass
    ``signal="NO INVEST"``, ``opening_bar=None``, ``limit_buy=None``,
    etc.
    """
    if opening_bar is None:
        opening_bar = {
            "o": 10.0,
            "h": 11.0,
            "l": 9.0,
            "c": 9.5,
        }

    stock = Stock(symbol=symbol)
    stock.signal = signal
    stock.opening_bar = opening_bar
    stock.atr = atr
    stock.candle_range = candle_range
    stock.atr_threshold = atr_threshold
    stock.is_manipulation = is_manipulation
    stock.is_red = is_red
    stock.limit_buy = limit_buy
    stock.limit_sell = limit_sell
    stock.stop_loss = stop_loss
    stock.trading_stop_loss = trading_stop_loss
    return stock


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------


def frozen_datetime(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
    tzinfo: timezone | None = None,
) -> type[datetime]:
    """Build a ``datetime`` subclass whose ``now()`` returns a fixed
    instant.

    Use ``monkeypatch.setattr(module, "datetime", cls)`` to install.
    For tests that need a *sequence* of ``now()`` calls, use
    ``install_clock`` instead.
    """

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(
                year,
                month,
                day,
                hour,
                minute,
                second,
                tzinfo=tz,
            )

    return FrozenDateTime


def install_clock(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    times: Sequence[datetime],
) -> None:
    """Install a queued-clock ``datetime`` class onto ``module``.

    Each call to ``datetime.now()`` pops the next entry from
    ``times``; if exhausted, the last entry is reused. Mirrors the
    behaviour tests previously implemented inline.
    """

    class FakeDateTime(datetime):
        queued_times = list(times)

        @classmethod
        def now(cls, tz=None):
            if not cls.queued_times:
                return cls.queued_times[-1]
            return cls.queued_times.pop(0)

    monkeypatch.setattr(module, "datetime", FakeDateTime)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def trading_bot() -> TradingBot:
    """Return a bare ``TradingBot`` allocated without running
    ``__init__``.

    The fixture does not populate ``bot.stocks``, ``bot.alpaca``,
    ``bot.sheets``, or any other attribute — tests set what they
    need. This keeps the fixture honest: it provides the
    ``object.__new__`` allocation that 9+ test files were duplicating
    by hand.
    """
    return object.__new__(TradingBot)


@pytest.fixture
def mock_alpaca_client() -> Mock:
    """Return a ``Mock`` standing in for ``AlpacaClient``.

    Pre-stubbed methods return empty containers so attribute access
    does not raise. Tests override what they need via
    ``mock_alpaca_client.get_scanner_statistics.return_value = [...]``.
    """
    alpaca = Mock()
    alpaca.get_scanner_statistics.return_value = []
    alpaca.get_opening_15min_bars.return_value = {}
    alpaca.get_previous_day_ranges_all.return_value = {}
    alpaca.get_1min_bars.return_value = {}
    alpaca.get_historical_1min_bars.return_value = {}
    return alpaca


@pytest.fixture
def mock_sheets_client() -> Mock:
    """Return a ``Mock`` standing in for ``SheetsClient``.

    Pre-stubbed ``test_connection`` returns the full happy-path
    sheet list so default preflight assertions pass.
    """
    sheets = Mock()
    sheets.test_connection.return_value = [
        "Orders",
        "Scanner Dashboard",
        "1 minute intervals",
    ]
    sheets.write_strategy_results.return_value = None
    sheets.write_orders.return_value = None
    sheets.write_scanner_dashboard.return_value = None
    return sheets


@pytest.fixture
def minute_tracker(mock_alpaca_client, mock_sheets_client) -> MinuteTracker:
    """Return a ``MinuteTracker`` wired with mocked alpaca/sheets.

    The tracker's stocks dict is empty so tests add the symbols they
    care about. ``symbol_rows`` is initialised to a single row per
    symbol so ``process_bar``/``merge_stream_bars`` operate on a
    consistent starting state.
    """
    tracker = MinuteTracker(
        alpaca=mock_alpaca_client,
        sheets=mock_sheets_client,
        stocks={},
        symbols_csv="",
    )
    return tracker