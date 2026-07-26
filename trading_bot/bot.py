import time as time_module

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from .alpaca_client import AlpacaClient
from .config import TICKERS
from .models import Stock
from .sheets_client import SheetsClient
from .strategy import ManipulationStrategy
from .tracker import MinuteTracker


class TradingBot:
    def __init__(self) -> None:
        self.stocks = {
            symbol: Stock(symbol=symbol)
            for symbol in TICKERS
        }

        self.symbols_csv = ",".join(self.stocks.keys())

        self.alpaca = AlpacaClient()
        self.strategy = ManipulationStrategy()

        self.sheets = None
        self.tracker = None

    def initialise_sheets(self) -> None:
        if self.sheets is None:
            self.sheets = SheetsClient()

        if self.tracker is None:
            self.tracker = MinuteTracker(
                alpaca=self.alpaca,
                sheets=self.sheets,
                stocks=self.stocks,
                symbols_csv=self.symbols_csv,
            )

    def run(self) -> None:
        print("===================================")
        print(" Professional Day Trading Bot")
        print("===================================")
        print()

        print("Tracking")

        for stock in self.stocks.values():
            print(stock.symbol)

        print()
        print("Testing Alpaca market-data connection...")

        try:
            recent_bars = self.alpaca.test_connection(
                self.symbols_csv
            )

            successful_symbols = [
                symbol
                for symbol, bar in recent_bars.items()
                if bar is not None
            ]

            missing_symbols = [
                symbol
                for symbol, bar in recent_bars.items()
                if bar is None
            ]

            print("Alpaca connection successful.")
            print(
                "Symbols returned:",
                ", ".join(successful_symbols),
            )

            if missing_symbols:
                print(
                    "No recent bars returned for:",
                    ", ".join(missing_symbols),
                )

        except Exception as error:
            print("Alpaca connection test failed.")
            print(f"Error: {error}")
            return

        print()
        print("Testing Google Sheets connection...")

        try:
            self.initialise_sheets()

            worksheet_names = self.sheets.test_connection()

            print("Google Sheets connection successful.")
            print(
                "Worksheets:",
                ", ".join(worksheet_names),
            )

        except Exception as error:
            print("Google Sheets connection test failed.")
            print(f"Error: {error}")
            return

        print()
        print("Bot Started Successfully")

    def run_live_tracker(self) -> None:
        self.initialise_sheets()

        eastern = ZoneInfo("America/New_York")
        utc = ZoneInfo("UTC")

        today_eastern = datetime.now(eastern).date()

        market_open_eastern = datetime.combine(
            today_eastern,
            time(hour=9, minute=30),
            tzinfo=eastern,
        )

        market_end_eastern = datetime.combine(
            today_eastern,
            time(hour=9, minute=45),
            tzinfo=eastern,
        )

        window_start = market_open_eastern.astimezone(
            utc
        ).replace(tzinfo=None)

        window_end = market_end_eastern.astimezone(
            utc
        ).replace(tzinfo=None)

        date_str = today_eastern.strftime("%Y-%m-%d")

        print()
        print("Starting real-time 1-minute tracker...")
        print(
            "Tracking window:",
            market_open_eastern.strftime("%H:%M"),
            "to",
            market_end_eastern.strftime("%H:%M"),
            "New York time",
        )

        self.tracker.track_window(
            date_str=date_str,
            window_start=window_start,
            window_end=window_end,
        )

    def run_strategy_test(self) -> None:
        test_date = "2026-07-23"

        print()
        print(f"Testing strategy for {test_date}...")

        self.calculate_strategy(test_date)

        print()
        print("===== STRATEGY RESULTS =====")

        for stock in self.stocks.values():
            if stock.opening_bar is None:
                print(f"{stock.symbol}: no opening bar")
                continue

            if stock.atr is None:
                print(f"{stock.symbol}: insufficient ATR data")
                continue

            print()
            print(f"Symbol: {stock.symbol}")
            print(f"ATR: {stock.atr:.4f}")
            print(f"Opening range: {stock.candle_range:.4f}")
            print(f"ATR threshold: {stock.atr_threshold:.4f}")
            print(
                "Manipulation:",
                "YES" if stock.is_manipulation else "NO",
            )
            print(
                "Red candle:",
                "YES" if stock.is_red else "NO",
            )
            print(f"Signal: {stock.signal}")
            print(f"Limit buy: {stock.limit_buy:.4f}")
            print(f"Limit sell: {stock.limit_sell:.4f}")
            print(f"Stop loss: {stock.stop_loss:.4f}")
            print(
                "Trading stop loss:",
                f"{stock.trading_stop_loss:.4f}",
            )
            print(f"Proximity: {stock.proximity}")

        print()
        print("Strategy test completed.")

    def calculate_strategy(
            self,
            date_str: str,
    ) -> None:
        opening_bars = self.alpaca.get_opening_15min_bars(
            symbols_csv=self.symbols_csv,
            date_str=date_str,
        )

        atrs = self.alpaca.get_previous_day_ranges_all(
            symbols_csv=self.symbols_csv,
            date_str=date_str,
        )

        for symbol, stock in self.stocks.items():
            opening_bar = opening_bars.get(symbol)
            atr = atrs.get(symbol)

            stock.opening_bar = opening_bar
            stock.atr = atr

            if opening_bar is None or atr is None:
                stock.signal = "NO INVEST"

                print(
                    f"{symbol}: strategy skipped because "
                    "valid opening-bar or ATR data was unavailable."
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
                    f"{symbol}: strategy evaluation failed: "
                    f"{error}"
                )

    def run_strategy_and_write(
            self,
            date_str: str | None = None,
    ) -> None:
        if date_str is None:
            eastern = ZoneInfo("America/New_York")
            date_str = datetime.now(eastern).strftime(
                "%Y-%m-%d"
            )

        print()
        print(f"Running strategy for {date_str}...")

        self.calculate_strategy(date_str)

        invest_symbols = [
            stock.symbol
            for stock in self.stocks.values()
            if stock.signal == "INVEST"
        ]

        print(
            "INVEST signals:",
            ", ".join(invest_symbols)
            if invest_symbols
            else "None",
        )

        self.initialise_sheets()

        write_errors = []

        try:
            self.sheets.write_strategy_results(
                date_str=date_str,
                stocks=self.stocks,
            )

        except Exception as error:
            write_errors.append(
                f"Invest sheet: {error}"
            )
            print(
                "Invest sheet write failed. "
                f"Error: {error}"
            )

        try:
            self.sheets.write_orders(
                date_str=date_str,
                stocks=self.stocks,
            )

        except Exception as error:
            write_errors.append(
                f"Orders sheet: {error}"
            )
            print(
                "Orders sheet write failed. "
                f"Error: {error}"
            )

        if write_errors:
            raise RuntimeError(
                "One or more strategy writes failed: "
                + " | ".join(write_errors)
            )

        print("Strategy results written successfully.")

    def run_production(self) -> None:
        eastern = ZoneInfo("America/New_York")
        now = datetime.now(eastern)

        date_str = now.strftime("%Y-%m-%d")

        if now.weekday() >= 5:
            print()
            print("The market is closed today.")
            print("Production mode was not started.")
            return

        market_open = datetime.combine(
            now.date(),
            time(hour=9, minute=30),
            tzinfo=eastern,
        )

        strategy_time = datetime.combine(
            now.date(),
            time(hour=9, minute=45),
            tzinfo=eastern,
        ) + timedelta(seconds=15)

        print()
        print("===================================")
        print(" Production Trading Mode")
        print("===================================")
        print(f"Trading date: {date_str}")

        if now < market_open:
            wait_seconds = (
                    market_open - now
            ).total_seconds()

            print(
                "Waiting for market open at "
                "09:30 New York time..."
            )

            time_module.sleep(wait_seconds)

        elif now >= strategy_time:
            print()
            print("The opening tracking window has ended.")
            print("Skipping live tracking.")
            print("Running the strategy immediately...")

            self.run_strategy_and_write(
                date_str=date_str
            )

            print()
            print("Production workflow completed.")
            return

        else:
            print()
            print("The opening window has already started.")
            print("Starting the tracker now...")

        self.run_live_tracker()

        now = datetime.now(eastern)

        remaining_seconds = (
                strategy_time - now
        ).total_seconds()

        if remaining_seconds > 0:
            print()
            print(
                "Waiting for Alpaca to complete "
                "the opening 15-minute candle..."
            )

            time_module.sleep(remaining_seconds)

        print()
        print("Opening tracking window completed.")
        print("Calculating strategy signals...")

        self.run_strategy_and_write(
            date_str=date_str
        )

        print()
        print("Production workflow completed.")