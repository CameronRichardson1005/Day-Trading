import requests
from datetime import datetime, timedelta
from typing import Any
from .indicators import calculate_wilder_atr

from .config import API_KEY, API_SECRET, BASE_URL, TICKERS
from .utils import call_with_retries


class AlpacaClient:
    def __init__(self) -> None:
        self.base_url = BASE_URL

        self.headers = {
            "accept": "application/json",
            "APCA-API-KEY-ID": API_KEY,
            "APCA-API-SECRET-KEY": API_SECRET,
        }

    def _request(
        self,
        params: dict[str, Any],
        label: str,
    ) -> dict[str, Any]:
        response = call_with_retries(
            requests.get,
            self.base_url,
            headers=self.headers,
            params=params,
            timeout=15,
            label=label,
        )

        return response.json()

    def get_1min_bars(
        self,
        symbols_csv: str,
        start_iso: str,
        end_iso: str,
    ) -> dict[str, dict | None]:
        params = {
            "symbols": symbols_csv,
            "timeframe": "1Min",
            "start": start_iso,
            "end": end_iso,
            "adjustment": "raw",
            "feed": "iex",
            "currency": "usd",
            "limit": 1000,
            "sort": "desc",
        }

        data = self._request(
            params=params,
            label="1-minute bars fetch",
        )

        bars_by_symbol = data.get("bars", {})

        return {
            symbol: (bars_by_symbol.get(symbol) or [None])[0]
            for symbol in TICKERS
        }

    def get_opening_15min_bars(
        self,
        symbols_csv: str,
        date_str: str,
    ) -> dict[str, dict | None]:
        params = {
            "symbols": symbols_csv,
            "timeframe": "15Min",
            "start": f"{date_str}T13:30:00Z",
            "end": f"{date_str}T13:45:00Z",
            "adjustment": "raw",
            "feed": "iex",
            "currency": "usd",
            "limit": 1000,
            "sort": "desc",
        }

        data = self._request(
            params=params,
            label="Opening 15-minute bars fetch",
        )

        bars_by_symbol = data.get("bars", {})

        return {
            symbol: (bars_by_symbol.get(symbol) or [None])[0]
            for symbol in TICKERS
        }

    def get_previous_day_ranges_all(
        self,
        symbols_csv: str,
        date_str: str,
    ) -> dict[str, float | None]:
        """
        Request daily bars for all symbols and calculate
        Wilder's 14-period ATR for each symbol.
        """
        end_date = datetime.strptime(
            date_str,
            "%Y-%m-%d",
        ) - timedelta(days=1)

        start_date = end_date - timedelta(days=180)

        params = {
            "symbols": symbols_csv,
            "timeframe": "1Day",
            "start": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "end": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "adjustment": "raw",
            "feed": "iex",
            "currency": "usd",
            "limit": 1000,
            "sort": "desc",
        }

        data = self._request(
            params=params,
            label="ATR daily bars fetch",
        )

        bars_by_symbol = data.get("bars", {})
        results: dict[str, float | None] = {}

        for symbol in TICKERS:
            bars = bars_by_symbol.get(symbol, [])

            results[symbol] = calculate_wilder_atr(
                bars=bars,
                period=14,
            )

        return results

    def test_connection(
        self,
        symbols_csv: str,
    ) -> dict[str, dict | None]:
        """
        Request recent daily bars to verify authentication
        and Alpaca market-data access.
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=7)

        params = {
            "symbols": symbols_csv,
            "timeframe": "1Day",
            "start": start_time.strftime("%Y-%m-%dT00:00:00Z"),
            "end": end_time.strftime("%Y-%m-%dT23:59:59Z"),
            "adjustment": "raw",
            "feed": "iex",
            "currency": "usd",
            "limit": 1000,
            "sort": "desc",
        }

        data = self._request(
            params=params,
            label="Alpaca connection test",
        )

        bars_by_symbol = data.get("bars", {})

        return {
            symbol: (bars_by_symbol.get(symbol) or [None])[0]
            for symbol in TICKERS
        }