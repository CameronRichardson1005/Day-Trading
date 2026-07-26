import time
from datetime import datetime, timedelta
from typing import Any

from .alpaca_client import AlpacaClient
from .models import Stock
from .sheets_client import SheetsClient


class MinuteTracker:
    TRACKING_COLUMNS = [
        "Date",
        "Symbol",
        "Running High",
        "Running Low",
        "Last Update Time",
        "Candle Color",
    ]

    def __init__(
        self,
        alpaca: AlpacaClient,
        sheets: SheetsClient,
        stocks: dict[str, Stock],
        symbols_csv: str,
    ) -> None:
        self.alpaca = alpaca
        self.sheets = sheets
        self.stocks = stocks
        self.symbols_csv = symbols_csv

        self.worksheet = self.sheets.get_or_create_worksheet(
            title="1 minute intervals",
            rows=100,
            cols=6,
        )

        self.symbol_rows: dict[str, int] = {}

    def prepare_sheet(self, date_str: str) -> None:
        """
        Guarantee exactly one tracking row per date and symbol.
        Existing duplicate keys are consolidated using their latest row.
        """
        existing_values = self.worksheet.get_all_values()

        if (
                existing_values
                and existing_values[0] != self.TRACKING_COLUMNS
        ):
            raise RuntimeError(
                "1 minute intervals has unexpected columns. "
                "The sheet was not modified."
            )

        unique_rows: dict[tuple[str, str], list] = {}

        for row in existing_values[1:]:
            if len(row) < 2 or not row[0] or not row[1]:
                continue

            normalised = list(row[:6])

            if len(normalised) < 6:
                normalised.extend(
                    [""] * (6 - len(normalised))
                )

            key = (normalised[0], normalised[1])
            unique_rows[key] = normalised

        for symbol in self.stocks:
            key = (date_str, symbol)

            if key not in unique_rows:
                unique_rows[key] = [
                    date_str,
                    symbol,
                    "",
                    "",
                    "",
                    "",
                ]

        tracking_rows = list(unique_rows.values())

        self.sheets._rewrite_table(
            worksheet=self.worksheet,
            columns=self.TRACKING_COLUMNS,
            rows=tracking_rows,
            last_column="F",
        )

        self.symbol_rows = {}

        for row_number, row in enumerate(
                tracking_rows,
                start=2,
        ):
            if row[0] == date_str and row[1] in self.stocks:
                self.symbol_rows[row[1]] = row_number

    def process_bar(
        self,
        stock: Stock,
        bar: dict[str, Any],
    ) -> tuple[bool, bool, str]:
        """
        Update one stock's in-memory state using one 1-minute bar.

        Returns:
            new_high, new_low, candle_color
        """
        minute_open = float(bar["o"])
        minute_close = float(bar["c"])
        minute_high = float(bar["h"])
        minute_low = float(bar["l"])

        candle_color = (
            "GREEN"
            if minute_close > minute_open
            else "RED"
        )

        if candle_color == "GREEN":
            stock.green_minutes += 1
        else:
            stock.red_minutes += 1

        new_high = False
        new_low = False

        if (
            stock.running_high is None
            or minute_high > stock.running_high
        ):
            stock.running_high = minute_high
            stock.new_highs += 1
            new_high = True

        if (
            stock.running_low is None
            or minute_low < stock.running_low
        ):
            stock.running_low = minute_low
            stock.new_lows += 1
            new_low = True

        return new_high, new_low, candle_color

    def track_window(
        self,
        date_str: str,
        window_start: datetime,
        window_end: datetime,
    ) -> None:
        """
        Fetch and process one completed bar per minute in real time.
        """
        self.prepare_sheet(date_str)

        current_minute = window_start

        while current_minute <= window_end:
            self.wait_for_bar_completion(current_minute)

            minute_start_iso = current_minute.strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

            minute_end_iso = (
                current_minute + timedelta(seconds=59)
            ).strftime("%Y-%m-%dT%H:%M:%SZ")

            time_label = current_minute.strftime("%H:%M")

            try:
                bars = self.alpaca.get_1min_bars(
                    symbols_csv=self.symbols_csv,
                    start_iso=minute_start_iso,
                    end_iso=minute_end_iso,
                )

            except Exception as error:
                print(
                    f"Could not fetch bars for {time_label}: {error}",
                    flush=True,
                )

                bars = {
                    symbol: None
                    for symbol in self.stocks
                }

            tracking_updates: list[dict[str, Any]] = []

            for symbol, stock in self.stocks.items():
                bar = bars.get(symbol)

                if bar is None:
                    print(
                        f"{symbol}: no bar for {time_label}",
                        flush=True,
                    )
                    continue

                new_high, new_low, candle_color = self.process_bar(
                    stock=stock,
                    bar=bar,
                )

                row_number = self.symbol_rows[symbol]

                tracking_updates.append(
                    {
                        "symbol": symbol,
                        "row": row_number,
                        "running_high": round(
                            stock.running_high,
                            4,
                        ),
                        "running_low": round(
                            stock.running_low,
                            4,
                        ),
                        "time_label": time_label,
                        "candle_color": candle_color,
                        "new_high": new_high,
                        "new_low": new_low,
                    }
                )

            if tracking_updates:
                self.sheets.update_tracking_minute(
                    worksheet=self.worksheet,
                    updates=tracking_updates,
                )

            print(
                f"1-minute update logged for {time_label}",
                flush=True,
            )

            current_minute += timedelta(minutes=1)

        print(
            "Finished real-time 1-minute tracking window.",
            flush=True,
        )

    @staticmethod
    def wait_for_bar_completion(
        bar_start: datetime,
        delay_seconds: int = 2,
    ) -> None:
        """
        Wait until the requested minute has fully completed.

        The small delay gives Alpaca time to publish the completed bar.
        """
        bar_available_time = (
            bar_start
            + timedelta(minutes=1)
            + timedelta(seconds=delay_seconds)
        )

        sleep_seconds = (
            bar_available_time - datetime.utcnow()
        ).total_seconds()

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    def test_historical_minute(
            self,
            date_str: str,
            time_str: str,
    ) -> None:
        test_minute = datetime.strptime(
            f"{date_str}T{time_str}:00",
            "%Y-%m-%dT%H:%M:%S",
        )

        minute_start_iso = test_minute.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        minute_end_iso = (
                test_minute + timedelta(seconds=59)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        self.prepare_sheet(date_str)

        bars = self.alpaca.get_1min_bars(
            symbols_csv=self.symbols_csv,
            start_iso=minute_start_iso,
            end_iso=minute_end_iso,
        )

        updates = []

        for symbol, stock in self.stocks.items():
            bar = bars.get(symbol)

            if bar is None:
                print(f"{symbol}: no historical test bar")
                continue

            new_high, new_low, candle_color = self.process_bar(
                stock=stock,
                bar=bar,
            )

            updates.append(
                {
                    "symbol": symbol,
                    "row": self.symbol_rows[symbol],
                    "running_high": round(stock.running_high, 4),
                    "running_low": round(stock.running_low, 4),
                    "time_label": time_str,
                    "candle_color": candle_color,
                    "new_high": new_high,
                    "new_low": new_low,
                }
            )

        if updates:
            self.sheets.update_tracking_minute(
                worksheet=self.worksheet,
                updates=updates,
            )

        print(f"Historical tracker test completed for {date_str} {time_str}")