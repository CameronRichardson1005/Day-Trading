import time as time_module

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from .models import Stock
from .strategy import ManipulationStrategy
from .tracker import MinuteTracker


@dataclass
class ReplaySummary:
    processed_bars: dict[str, int]
    missing_bars: dict[str, int]


class HistoricalReplay:
    OPENING_MINUTES = 15

    def __init__(
        self,
        stocks: dict[str, Stock],
        strategy: ManipulationStrategy,
        speed: float = 60.0,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        if speed < 0:
            raise ValueError(
                "Replay speed cannot be negative."
            )

        self.stocks = stocks
        self.strategy = strategy
        self.speed = speed
        self.sleep_fn = sleep_fn or time_module.sleep

    @staticmethod
    def _bar_minute(bar: dict[str, Any]) -> datetime:
        raw_timestamp = str(bar["t"])
        normalised = raw_timestamp.replace(
            "Z",
            "+00:00",
        )

        try:
            timestamp = datetime.fromisoformat(
                normalised
            )
        except ValueError as error:
            raise RuntimeError(
                "Historical bar has an invalid timestamp: "
                f"{raw_timestamp}"
            ) from error

        utc = ZoneInfo("UTC")

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=utc
            )
        else:
            timestamp = timestamp.astimezone(utc)

        return timestamp.replace(
            second=0,
            microsecond=0,
        )

    @staticmethod
    def _build_opening_bar(
        bars: list[dict[str, Any]],
    ) -> dict[str, Any]:
        first_bar = bars[0]
        last_bar = bars[-1]

        opening_bar = {
            "o": float(first_bar["o"]),
            "h": max(float(bar["h"]) for bar in bars),
            "l": min(float(bar["l"]) for bar in bars),
            "c": float(last_bar["c"]),
            "t": first_bar["t"],
        }

        if all("v" in bar for bar in bars):
            opening_bar["v"] = sum(
                float(bar["v"])
                for bar in bars
            )

        return opening_bar

    @staticmethod
    def _reset_stock(stock: Stock) -> None:
        stock.running_high = None
        stock.running_low = None
        stock.green_minutes = 0
        stock.red_minutes = 0
        stock.new_highs = 0
        stock.new_lows = 0

        stock.atr = None
        stock.opening_bar = None
        stock.candle_range = None
        stock.atr_threshold = None
        stock.is_manipulation = False
        stock.is_red = False
        stock.proximity = ""

        stock.signal = "NO INVEST"
        stock.limit_buy = None
        stock.limit_sell = None
        stock.stop_loss = None
        stock.trading_stop_loss = None

    def run(
        self,
        date_str: str,
        window_start: datetime,
        bars_by_symbol: dict[str, list[dict]],
        atrs: dict[str, float | None],
    ) -> ReplaySummary:
        if window_start.tzinfo is None:
            raise ValueError(
                "Replay window start must include a timezone."
            )

        utc = ZoneInfo("UTC")
        eastern = ZoneInfo("America/New_York")

        window_start = window_start.astimezone(
            utc
        ).replace(
            second=0,
            microsecond=0,
        )

        indexed_bars: dict[
            str,
            dict[datetime, dict[str, Any]],
        ] = {}

        revealed_bars = {
            symbol: []
            for symbol in self.stocks
        }

        for symbol, stock in self.stocks.items():
            self._reset_stock(stock)

            indexed_bars[symbol] = {}

            for bar in bars_by_symbol.get(symbol, []):
                minute = self._bar_minute(bar)

                if minute in indexed_bars[symbol]:
                    raise RuntimeError(
                        f"{symbol}: duplicate historical bar "
                        f"for {minute.isoformat()}"
                    )

                indexed_bars[symbol][minute] = bar

        processed_bars = {
            symbol: 0
            for symbol in self.stocks
        }

        missing_bars = {
            symbol: 0
            for symbol in self.stocks
        }

        print()
        print(
            "Replaying 09:30-09:45 New York time "
            "one minute at a time..."
        )

        for minute_index in range(
            self.OPENING_MINUTES
        ):
            current_minute = (
                window_start
                + timedelta(minutes=minute_index)
            )

            time_label = (
                current_minute
                .astimezone(eastern)
                .strftime("%H:%M")
            )

            minute_count = 0

            for symbol, stock in self.stocks.items():
                bar = indexed_bars[symbol].get(
                    current_minute
                )

                if bar is None:
                    missing_bars[symbol] += 1
                    continue

                MinuteTracker.process_bar(
                    stock=stock,
                    bar=bar,
                )

                revealed_bars[symbol].append(bar)
                processed_bars[symbol] += 1
                minute_count += 1

            print(
                f"Replay minute {time_label}: "
                f"{minute_count}/{len(self.stocks)} "
                "bars processed.",
                flush=True,
            )

            is_final_minute = (
                minute_index
                == self.OPENING_MINUTES - 1
            )

            if (
                not is_final_minute
                and self.speed > 0
            ):
                self.sleep_fn(
                    60.0 / self.speed
                )

        print()
        print(
            "Virtual time reached 09:45. "
            "Building opening candles..."
        )

        for symbol, stock in self.stocks.items():
            bars = revealed_bars[symbol]
            atr = atrs.get(symbol)

            stock.atr = atr

            if len(bars) != self.OPENING_MINUTES:
                stock.signal = "NO INVEST"

                print(
                    f"{symbol}: strategy skipped because "
                    f"only {len(bars)}/15 bars were available."
                )
                continue

            opening_bar = self._build_opening_bar(
                bars
            )
            stock.opening_bar = opening_bar

            if atr is None:
                stock.signal = "NO INVEST"

                print(
                    f"{symbol}: strategy skipped because "
                    "ATR data was unavailable."
                )
                continue

            try:
                self.strategy.evaluate(
                    stock=stock,
                    opening_bar=opening_bar,
                    atr=atr,
                )
            except Exception as error:
                stock.signal = "NO INVEST"

                print(
                    f"{symbol}: replay strategy failed: "
                    f"{error}"
                )

        return ReplaySummary(
            processed_bars=processed_bars,
            missing_bars=missing_bars,
        )
