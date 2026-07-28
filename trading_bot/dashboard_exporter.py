from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

from .config import (
    DASHBOARD_INGEST_KEY,
    DASHBOARD_REQUEST_TIMEOUT,
    DASHBOARD_SITE_TOKEN,
    DASHBOARD_URL,
    MARKET_DATA_FEED,
)
from .models import Stock


class DashboardExporter:
    """
    Sends read-only session results to the dashboard.

    This class cannot submit, modify, or cancel orders.
    """

    EXPECTED_BARS = 15

    def __init__(
            self,
            url: str = DASHBOARD_URL,
            ingest_key: str = DASHBOARD_INGEST_KEY,
            site_token: str = DASHBOARD_SITE_TOKEN,
            timeout: tuple[int, int] = (
                DASHBOARD_REQUEST_TIMEOUT
            ),
            post_fn=None,
    ) -> None:
        self.url = url
        self.ingest_key = ingest_key
        self.site_token = site_token
        self.timeout = timeout
        self.post_fn = post_fn or requests.post

    @staticmethod
    def _levels(stock: Stock) -> dict[str, float] | None:
        values = (
            stock.limit_buy,
            stock.limit_sell,
            stock.stop_loss,
            stock.trading_stop_loss,
        )

        if not all(
            isinstance(value, (int, float))
            for value in values
        ):
            return None

        return {
            "buy": float(stock.limit_buy),
            "target": float(stock.limit_sell),
            "stop": float(stock.stop_loss),
            "tradingStop": float(
                stock.trading_stop_loss
            ),
        }

    @staticmethod
    def _bar_time(bar: dict[str, Any]) -> str:
        raw_timestamp = str(bar["t"])
        normalised = raw_timestamp.replace(
            "Z",
            "+00:00",
        )

        timestamp = datetime.fromisoformat(
            normalised
        )

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(
                tzinfo=timezone.utc
            )

        return (
            timestamp
            .astimezone(
                ZoneInfo("America/New_York")
            )
            .strftime("%H:%M")
        )

    @classmethod
    def _minute_bars(
            cls,
            stock: Stock,
    ) -> list[dict[str, Any]]:
        result = []

        for bar in stock.minute_bars[
            :cls.EXPECTED_BARS
        ]:
            payload = {
                "time": cls._bar_time(bar),
                "open": float(bar["o"]),
                "high": float(bar["h"]),
                "low": float(bar["l"]),
                "close": float(bar["c"]),
            }

            volume = bar.get("v")
            if isinstance(volume, (int, float)):
                payload["volume"] = float(volume)

            result.append(payload)

        return result

    @staticmethod
    def _strategy_payload(
            stock: Stock,
    ) -> dict[str, Any]:
        opening_bar = stock.opening_bar

        return {
            "atr": float(stock.atr),
            "openingOpen": float(
                opening_bar["o"]
            ),
            "openingHigh": float(
                opening_bar["h"]
            ),
            "openingLow": float(
                opening_bar["l"]
            ),
            "openingClose": float(
                opening_bar["c"]
            ),
            "candleRange": float(
                stock.candle_range
            ),
            "atrThreshold": float(
                stock.atr_threshold
            ),
            "isManipulation": (
                stock.is_manipulation
            ),
            "isRed": stock.is_red,
        }

    @staticmethod
    def _rules(
            stock: Stock,
    ) -> list[dict[str, Any]]:
        opening_bar = stock.opening_bar

        return [
            {
                "label": "Manipulation candle",
                "passed": stock.is_manipulation,
                "actual": (
                    f"Range ${stock.candle_range:.4f}; "
                    f"ATR threshold "
                    f"${stock.atr_threshold:.4f}"
                ),
                "requirement": (
                    "Range exceeds the ATR threshold "
                    "or is within $0.0050"
                ),
            },
            {
                "label": "Red opening candle",
                "passed": stock.is_red,
                "actual": (
                    f"Open ${float(opening_bar['o']):.4f}; "
                    f"close "
                    f"${float(opening_bar['c']):.4f}"
                ),
                "requirement": (
                    "Opening close is below "
                    "the opening price"
                ),
            },
        ]

    @classmethod
    def _symbol_payload(
            cls,
            stock: Stock,
            bars_processed: int,
    ) -> dict[str, Any]:
        has_all_bars = (
            bars_processed == cls.EXPECTED_BARS
        )
        strategy_complete = (
            has_all_bars
            and stock.opening_bar is not None
            and stock.atr is not None
        )

        if not has_all_bars:
            detail = (
                f"incomplete: {bars_processed}/"
                f"{cls.EXPECTED_BARS} bars"
            )
        elif stock.opening_bar is None:
            detail = "strategy unavailable"
        elif stock.atr is None:
            detail = "ATR unavailable"
        else:
            detail = "complete"

        payload: dict[str, Any] = {
            "symbol": stock.symbol,
            "signal": (
                stock.signal
                if strategy_complete
                else "WARNING"
            ),
            "barsProcessed": bars_processed,
            "barsExpected": cls.EXPECTED_BARS,
            "detail": detail,
        }

        levels = cls._levels(stock)
        if (
            strategy_complete
            and stock.signal == "INVEST"
            and levels is not None
        ):
            payload["levels"] = levels

        if strategy_complete:
            payload["rules"] = cls._rules(stock)
            payload["strategy"] = (
                cls._strategy_payload(stock)
            )

        minute_bars = cls._minute_bars(stock)
        if minute_bars:
            payload["minuteBars"] = minute_bars

        if (
            strategy_complete
            and stock.signal == "INVEST"
            and stock.outcome is not None
        ):
            payload["outcome"] = dict(
                stock.outcome
            )

        return payload

    @classmethod
    def build_payload(
            cls,
            date_str: str,
            source: str,
            stocks: dict[str, Stock],
            processed_bars: dict[str, int],
            data_feed: str = MARKET_DATA_FEED,
    ) -> dict[str, Any]:
        source = source.upper()
        if source not in {"REPLAY", "LIVE"}:
            raise ValueError(
                "Dashboard source must be REPLAY or LIVE."
            )

        data_feed = data_feed.strip().lower()
        if data_feed not in {"iex", "sip"}:
            raise ValueError(
                "Dashboard sessions must use IEX or SIP market data."
            )

        symbols = [
            cls._symbol_payload(
                stock=stock,
                bars_processed=int(
                    processed_bars.get(symbol, 0)
                ),
            )
            for symbol, stock in stocks.items()
        ]

        status = (
            "COMPLETE"
            if all(
                symbol["detail"] == "complete"
                for symbol in symbols
            )
            else "INCOMPLETE"
        )

        updated_at = (
            datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

        return {
            "id": f"{source.lower()}-{date_str}",
            "tradingDate": date_str,
            "source": source,
            "dataFeed": data_feed.upper(),
            "status": status,
            "updatedAt": updated_at,
            "symbols": symbols,
        }

    def publish(
            self,
            date_str: str,
            source: str,
            stocks: dict[str, Stock],
            processed_bars: dict[str, int],
            data_feed: str = MARKET_DATA_FEED,
    ) -> dict[str, Any] | None:
        if not self.ingest_key:
            return None

        if not self.site_token:
            raise RuntimeError(
                "DASHBOARD_SITE_TOKEN is not configured."
            )

        payload = self.build_payload(
            date_str=date_str,
            source=source,
            stocks=stocks,
            processed_bars=processed_bars,
            data_feed=data_feed,
        )

        response = self.post_fn(
            self.url,
            headers={
                "x-dashboard-key": self.ingest_key,
                "OAI-Sites-Authorization": (
                    f"Bearer {self.site_token}"
                ),
            },
            json=payload,
            timeout=self.timeout,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise RuntimeError(
                f"Dashboard returned {response.status_code}: "
                f"{response.text}"
            ) from error

        result = response.json()
        if result.get("accepted") is not True:
            raise RuntimeError(
                "Dashboard did not accept the session."
            )

        return result
