import requests
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

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

        response.raise_for_status()

        try:
            data = response.json()
        except ValueError as error:
            raise RuntimeError(
                f"{label} returned invalid JSON."
            ) from error

        if not isinstance(data, dict):
            raise RuntimeError(
                f"{label} returned an unexpected response."
            )

        if "bars" not in data:
            message = data.get("message", "No bars object returned")
            raise RuntimeError(f"{label} failed: {message}")

        return data

    @staticmethod
    def _is_valid_bar(bar: Any) -> bool:
        if not isinstance(bar, dict):
            return False

        required_fields = ("o", "h", "l", "c", "t")

        if any(field not in bar for field in required_fields):
            return False

        try:
            open_price = float(bar["o"])
            high_price = float(bar["h"])
            low_price = float(bar["l"])
            close_price = float(bar["c"])
        except (TypeError, ValueError):
            return False

        if min(
                open_price,
                high_price,
                low_price,
                close_price,
        ) <= 0:
            return False

        if high_price < low_price:
            return False

        if not low_price <= open_price <= high_price:
            return False

        if not low_price <= close_price <= high_price:
            return False

        return True

    def _first_valid_bar(
            self,
            bars: Any,
            symbol: str,
            label: str,
    ) -> dict | None:
        if not isinstance(bars, list):
            print(f"{symbol}: malformed {label} response")
            return None

        for bar in bars:
            if self._is_valid_bar(bar):
                return bar

        print(f"{symbol}: no valid {label} bar")
        return None

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
            symbol: self._first_valid_bar(
                bars=bars_by_symbol.get(symbol, []),
                symbol=symbol,
                label="1-minute",
            )
            for symbol in TICKERS
        }

    def get_opening_15min_bars(
            self,
            symbols_csv: str,
            date_str: str,
    ) -> dict[str, dict | None]:
        eastern = ZoneInfo("America/New_York")
        utc = ZoneInfo("UTC")

        trading_date = datetime.strptime(
            date_str,
            "%Y-%m-%d",
        ).date()

        opening_start = datetime.combine(
            trading_date,
            time(hour=9, minute=30),
            tzinfo=eastern,
        ).astimezone(utc)

        opening_end = datetime.combine(
            trading_date,
            time(hour=9, minute=45),
            tzinfo=eastern,
        ).astimezone(utc)

        params = {
            "symbols": symbols_csv,
            "timeframe": "15Min",
            "start": opening_start.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "end": opening_end.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
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
            symbol: self._first_valid_bar(
                bars=bars_by_symbol.get(symbol, []),
                symbol=symbol,
                label="opening 15-minute",
            )
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
            raw_bars = bars_by_symbol.get(symbol, [])

            valid_bars = [
                bar
                for bar in raw_bars
                if self._is_valid_bar(bar)
            ]

            if len(valid_bars) < 15:
                print(
                    f"{symbol}: insufficient valid daily bars "
                    f"for ATR ({len(valid_bars)} returned)"
                )
                results[symbol] = None
                continue

            try:
                results[symbol] = calculate_wilder_atr(
                    bars=valid_bars,
                    period=14,
                )
            except Exception as error:
                print(f"{symbol}: ATR calculation failed: {error}")
                results[symbol] = None

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