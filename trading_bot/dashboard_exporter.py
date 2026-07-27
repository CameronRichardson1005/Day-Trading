from datetime import datetime, timezone
from typing import Any

import requests

from .config import (
    DASHBOARD_INGEST_KEY,
    DASHBOARD_REQUEST_TIMEOUT,
    DASHBOARD_SITE_TOKEN,
    DASHBOARD_URL,
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

        return payload

    @classmethod
    def build_payload(
            cls,
            date_str: str,
            source: str,
            stocks: dict[str, Stock],
            processed_bars: dict[str, int],
    ) -> dict[str, Any]:
        source = source.upper()
        if source not in {"REPLAY", "LIVE"}:
            raise ValueError(
                "Dashboard source must be REPLAY or LIVE."
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
        response.raise_for_status()

        result = response.json()
        if result.get("accepted") is not True:
            raise RuntimeError(
                "Dashboard did not accept the session."
            )

        return result
